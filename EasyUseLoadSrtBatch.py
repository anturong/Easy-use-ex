import glob
import json
import os
import random
import re

EMPTY_SRT_RESULT = ("", "", "", "", "")


class EasyStateDB:
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    self.data = json.load(file)
            except Exception:
                self.data = {}

    def get(self, category, key):
        return self.data.get(category, {}).get(key, 0)

    def set(self, category, key, value):
        if category not in self.data:
            self.data[category] = {}
        self.data[category][key] = value
        try:
            with open(self.filepath, "w", encoding="utf-8") as file:
                json.dump(self.data, file, indent=4, ensure_ascii=False)
        except Exception as exc:
            print(f"[Easy Use Ex] Warning: Could not save state file: {exc}")


def strip_speaker_tags(text: str) -> str:
    lines = str(text or "").split("\n")
    cleaned_lines = []
    for line in lines:
        cleaned_lines.append(re.sub(r"^\s*\[[^\]]+\]\s*", "", line))
    return "\n".join(cleaned_lines).strip()


def has_speaker_tag(text: str) -> bool:
    for line in str(text or "").split("\n"):
        if re.match(r"^\s*\[[^\]]+\]\s*", line):
            return True
    return False


# ==================== 新增：提取角色名函数 ====================
def extract_speaker_names(text: str) -> list:
    """从单条字幕文本中提取所有角色标签中的角色名，返回列表。"""
    names = []
    for line in str(text or "").split("\n"):
        for match in re.finditer(r"^\s*\[([^\]]+)\]\s*", line):
            names.append(match.group(1))
    return names


def extract_speaker_names_from_subtitles(subtitles: list) -> list:
    """
    从字幕列表中提取每条字幕的角色名。
    返回与 subtitles 等长的列表，每项为该条字幕中出现的角色名列表。
    """
    result = []
    for sub in subtitles:
        names = extract_speaker_names(sub)
        result.append(names)
    return result
# ============================================================


def parse_srt_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig") as file:
            content = file.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, "r", encoding="gbk") as file:
                content = file.read()
        except Exception:
            print(f"[Easy Use Ex] Error reading SRT file (encoding issue): {filepath}")
            return [], [], []   # ← 改动点：返回值数量保持3个，调用方不变

    content = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not content:
        return [], [], []

    timestamps = []
    subtitles = []
    subtitle_blocks = []

    blocks = re.split(r"\n\s*\n", content)
    for block in blocks:
        lines = [line.rstrip() for line in block.split("\n")]
        if len(lines) < 2:
            continue
        line_index = 0
        if re.fullmatch(r"\d+", lines[0].strip()):
            line_index = 1
        if line_index >= len(lines):
            continue
        time_str = lines[line_index].strip()
        if not re.fullmatch(
            r"\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}", time_str
        ):
            continue
        clean_text = "\n".join(lines[line_index + 1 :])
        clean_text = re.sub(r"<[^>]+>", "", clean_text).strip()
        if clean_text:
            timestamps.append(time_str)
            subtitles.append(clean_text)
            subtitle_blocks.append(f"{time_str}\n{clean_text}")

    return subtitles, timestamps, subtitle_blocks


class SrtBatchLoader:
    def __init__(self, directory_path, label, db, recursive=False):
        self.db = db
        self.label = label
        self.root_path = os.path.normpath(directory_path)
        self.srt_paths = []
        self.load_srts(directory_path, recursive)
        self.srt_paths.sort()

        stored_path = db.get("SrtBatchPaths", label)
        stored_recursive = db.get("SrtBatchRecursive", label)
        if stored_path != self.root_path or stored_recursive != recursive:
            self.index = 0
            db.set("SrtBatchCounters", label, 0)
            db.set("SrtBatchPaths", label, self.root_path)
            db.set("SrtBatchRecursive", label, recursive)
        else:
            self.index = db.get("SrtBatchCounters", label)

    def load_srts(self, directory_path, recursive=False):
        if recursive:
            search_pattern = os.path.join(glob.escape(directory_path), "**", "*.srt")
        else:
            search_pattern = os.path.join(glob.escape(directory_path), "*.srt")
        for file_name in glob.glob(search_pattern, recursive=recursive):
            if file_name.lower().endswith(".srt"):
                self.srt_paths.append(os.path.abspath(file_name))

    def get_srt_by_id(self, srt_id, role_mode="保留角色标签"):
        if srt_id < 0 or srt_id >= len(self.srt_paths):
            return EMPTY_SRT_RESULT
        return self._process_srt(self.srt_paths[srt_id], role_mode)

    def get_next_srt(self, role_mode="保留角色标签"):
        if not self.srt_paths:
            return EMPTY_SRT_RESULT
        if self.index >= len(self.srt_paths):
            self.index = 0
        srt_path = self.srt_paths[self.index]
        self.index += 1
        if self.index >= len(self.srt_paths):
            self.index = 0
        self.db.set("SrtBatchCounters", self.label, self.index)
        return self._process_srt(srt_path, role_mode)

    def _process_srt(self, path, role_mode="保留角色标签"):
        subtitles, timestamps, subtitle_blocks = parse_srt_file(path)
        if not subtitles:
            return EMPTY_SRT_RESULT

        filename = os.path.basename(path)
        output_path = os.path.join(
            os.path.abspath(os.path.dirname(path)), ""
        )

        # ============ 改动：用角色名JSON替代时间轴JSON ============
        # 提取每条字幕的角色名
        speaker_names = extract_speaker_names_from_subtitles(subtitles)
        speaker_json = json.dumps(speaker_names, ensure_ascii=False)
        # ===========================================================

        contains_role_tags = any(has_speaker_tag(text) for text in subtitles)

        if role_mode == "移除角色标签" and contains_role_tags:
            original_subtitles = list(subtitles)
            subtitles = [strip_speaker_tags(text) for text in original_subtitles]
            subtitle_blocks = [
                f"{timestamps[idx]}\n{strip_speaker_tags(original_subtitles[idx])}"
                for idx in range(len(original_subtitles))
            ]

        subtitle_text = "\n\n".join(subtitles)
        subtitle_text_with_time = "\n\n".join(subtitle_blocks)

        # 改动：第五个返回值从 time_json → speaker_json
        return subtitle_text, subtitle_text_with_time, filename, speaker_json, output_path


class EasyUseLoadSrtBatch:
    def __init__(self):
        self.db_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "easy_srt_state.json"
        )
        self.db = EasyStateDB(self.db_path)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模式": (["单个SRT", "顺序SRT", "随机SRT"],),
                "种子": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF},
                ),
                "索引": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                "批次标签": (
                    "STRING",
                    {"default": "字幕批次 001", "multiline": False},
                ),
                "路径": ("STRING", {"default": "", "multiline": False}),
                "字幕文本输出": (
                    ["移除时间输出", "包括时间输出"],
                    {"default": "移除时间输出"},
                ),
                "角色标签": (
                    ["保留角色标签", "移除角色标签"],
                    {"default": "保留角色标签"},
                ),
                "递归搜索": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    # ============ 改动：输出名称 "时间轴JSON" → "角色名" ============
    RETURN_NAMES = ("字幕文本", "文件名", "角色名", "输出路径")
    # ============================================================
    OUTPUT_IS_LIST = (False, False, False, False)
    FUNCTION = "load_srt_batch"
    CATEGORY = "EasyUse/文本"

    def load_srt_batch(
        self,
        路径,
        索引=0,
        模式="单个SRT",
        种子=0,
        批次标签="字幕批次 001",
        字幕文本输出="移除时间输出",
        角色标签="保留角色标签",
        递归搜索=False,
    ):
        if not os.path.exists(路径):
            print(f"[Easy Use Ex] Error: The path `{路径}` does not exist!")
            return ("", "", "", "")

        loader = SrtBatchLoader(路径, 批次标签, self.db, recursive=递归搜索)

        if 模式 == "单个SRT":
            result = loader.get_srt_by_id(索引, 角色标签)
        elif 模式 == "顺序SRT":
            result = loader.get_next_srt(角色标签)
        else:
            if not loader.srt_paths:
                return ("", "", "", "")
            random.seed(种子)
            newindex = int(random.random() * len(loader.srt_paths))
            result = loader.get_srt_by_id(newindex, 角色标签)

        if not result or len(result) != 5:
            print("[Easy Use Ex] Error: Failed to load SRT result.")
            return ("", "", "", "")

        # 改动：解构变量名 time_json → speaker_json
        sub_text, sub_text_with_time, filename, speaker_json, output_path = result

        if not sub_text and not filename and not speaker_json and not output_path:
            print("[Easy Use Ex] Error: Failed to load or parse SRT file.")
            return ("", "", "", "")

        if 字幕文本输出 == "包括时间输出":
            sub_text = sub_text_with_time

        # 改动：返回 speaker_json 替代 time_json
        return (sub_text, filename, speaker_json, output_path)

    @classmethod
    def OUTPUT_NODE(cls):
        return False

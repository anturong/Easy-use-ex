import os
import re
from typing import Dict, List, Tuple


def parse_srt_blocks(srt_text: str) -> List[Dict[str, str]]:
    content = (srt_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not content:
        return []

    blocks = re.split(r"\n\s*\n", content)
    items: List[Dict[str, str]] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        line_index = 0
        if re.fullmatch(r"\d+", lines[0].strip()):
            line_index = 1
        if line_index >= len(lines):
            continue

        time_line = lines[line_index].strip()
        if not re.fullmatch(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}", time_line):
            continue

        text = "\n".join(lines[line_index + 1:]).strip()
        if not text:
            continue

        items.append({"time": time_line, "text": text})
    return items


def split_role_label(text: str) -> Tuple[str | None, str]:
    match = re.match(r"^\s*\[([^\]]*)\]\s*(.*)$", text, flags=re.DOTALL)
    if not match:
        return None, text.strip()
    role = match.group(1).strip()
    body = match.group(2).strip()
    return role or None, body


def normalize_role_dir_name(role: str) -> str:
    value = (role or "").strip()
    if not value:
        return "未命名角色"

    safe_name = re.sub(r'[<>:"/\\|?*]+', "_", value)
    safe_name = safe_name.strip(" .")
    return safe_name or "未命名角色"


def time_to_filename(time_line: str) -> str:
    start = time_line.split("-->")[0].strip()
    return start.replace(":", "-").replace(",", "_")


class EasyUseSplitSrtByRole:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "SRT内容": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "输入目录": ("STRING", {"default": r"C:\Users\41456\Desktop\spitl", "multiline": False}),
                "文件名模式": (["按对话顺序", "按开始时间"], {"default": "按对话顺序"}),
                "起始编号": ("INT", {"default": 1, "min": 1, "max": 999999, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("保存结果", "输出目录")
    FUNCTION = "split_and_save"
    OUTPUT_NODE = True
    CATEGORY = "EasyUse/文本"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Always re-run so deleting saved files and executing again will write them back.
        return float("NaN")

    def split_and_save(self, SRT内容, 输入目录, 文件名模式="按对话顺序", 起始编号=1):
        root_dir = os.path.abspath(str(输入目录 or "").strip())
        if not os.path.isdir(root_dir):
            message = f"[Easy Use Ex] Error: 输入目录不存在: {root_dir}"
            print(message)
            return {"ui": {}, "result": (message, root_dir)}

        blocks = parse_srt_blocks(SRT内容)
        if not blocks:
            message = "[Easy Use Ex] Error: 没有可处理的 SRT 条目。"
            print(message)
            return {"ui": {}, "result": (message, root_dir)}

        counters: Dict[str, int] = {}
        saved_files: List[str] = []
        overwritten_files: List[str] = []
        ignored_blocks = 0

        for block in blocks:
            role, body = split_role_label(block["text"])
            if role is None:
                role_dir_name = "未命名角色"
            else:
                role_dir_name = normalize_role_dir_name(role)

            target_dir = os.path.join(root_dir, role_dir_name)
            os.makedirs(target_dir, exist_ok=True)

            if role_dir_name not in counters:
                counters[role_dir_name] = int(起始编号)

            if 文件名模式 == "按开始时间":
                file_stem = time_to_filename(block["time"])
            else:
                file_stem = str(counters[role_dir_name])
                counters[role_dir_name] += 1

            output_path = os.path.join(target_dir, f"{file_stem}.srt")
            if not body:
                ignored_blocks += 1
                continue

            if os.path.exists(output_path):
                overwritten_files.append(output_path)

            srt_text = f"1\n{block['time']}\n{body}\n"
            with open(output_path, "w", encoding="utf-8-sig", newline="\n") as f:
                f.write(srt_text)
            saved_files.append(output_path)

        summary_lines = [
            f"保存成功: {len(saved_files)}",
            f"已覆盖(已存在): {len(overwritten_files)}",
            f"已忽略(空文本): {ignored_blocks}",
        ]
        if saved_files:
            summary_lines.append("已保存文件:")
            summary_lines.extend(saved_files)
        if overwritten_files:
            summary_lines.append("已覆盖文件:")
            summary_lines.extend(overwritten_files)

        summary = "\n".join(summary_lines)
        print(f"[Easy Use Ex] {summary}")
        return {"ui": {"string": [summary]}, "result": (summary, root_dir)}


NODE_CLASS_MAPPINGS = {
    "Easy Use Split SRT By Role": EasyUseSplitSrtByRole,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Easy Use Split SRT By Role": "批量角色分割SRT",
}

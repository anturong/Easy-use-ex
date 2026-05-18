import glob
import json
import os
import random


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


def read_txt_file(filepath):
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(filepath, "r", encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            print(f"[Easy Use Ex] Error reading TXT file `{filepath}`: {exc}")
            return None

    print(f"[Easy Use Ex] Error: Unable to decode TXT file `{filepath}`.")
    return None


class TxtBatchLoader:
    def __init__(self, directory_path, label, db, recursive=False):
        self.db = db
        self.label = label
        self.root_path = os.path.normpath(directory_path)
        self.txt_paths = []
        self.load_txts(directory_path, recursive)
        self.txt_paths.sort()

        stored_path = db.get("TxtBatchPaths", label)
        stored_recursive = db.get("TxtBatchRecursive", label)
        if stored_path != self.root_path or stored_recursive != recursive:
            self.index = 0
            db.set("TxtBatchCounters", label, 0)
            db.set("TxtBatchPaths", label, self.root_path)
            db.set("TxtBatchRecursive", label, recursive)
        else:
            self.index = db.get("TxtBatchCounters", label)

    def load_txts(self, directory_path, recursive=False):
        if recursive:
            search_pattern = os.path.join(glob.escape(directory_path), "**", "*.txt")
        else:
            search_pattern = os.path.join(glob.escape(directory_path), "*.txt")

        for file_name in glob.glob(search_pattern, recursive=recursive):
            if file_name.lower().endswith(".txt"):
                self.txt_paths.append(os.path.abspath(file_name))

    def get_txt_by_id(self, txt_id):
        if txt_id < 0 or txt_id >= len(self.txt_paths):
            return None, None, None
        return self._process_txt(self.txt_paths[txt_id])

    def get_next_txt(self):
        if not self.txt_paths:
            return None, None, None

        if self.index >= len(self.txt_paths):
            self.index = 0

        txt_path = self.txt_paths[self.index]
        self.index += 1
        if self.index >= len(self.txt_paths):
            self.index = 0

        self.db.set("TxtBatchCounters", self.label, self.index)
        return self._process_txt(txt_path)

    def _process_txt(self, path):
        text_content = read_txt_file(path)
        if text_content is None:
            return None, None, None
        output_path = os.path.join(os.path.abspath(os.path.dirname(path)), "")
        return text_content, os.path.basename(path), output_path


class EasyUseLoadTxtBatch:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "easy_txt_state.json")
        self.db = EasyStateDB(self.db_path)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模式": (["单个TXT", "顺序TXT", "随机TXT"],),
                "种子": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "索引": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                "批次标签": ("STRING", {"default": "文本批次 001", "multiline": False}),
                "路径": ("STRING", {"default": "", "multiline": False}),
                "递归搜索": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("文本内容", "文件名", "输出路径")
    FUNCTION = "load_txt_batch"
    CATEGORY = "EasyUse/文本"

    def load_txt_batch(self, 路径, 索引=0, 模式="单个TXT", 种子=0, 批次标签="文本批次 001", 递归搜索=False):
        if not os.path.exists(路径):
            print(f"[Easy Use Ex] Error: The path `{路径}` does not exist!")
            return ("", "", "")

        loader = TxtBatchLoader(路径, 批次标签, self.db, recursive=递归搜索)

        if 模式 == "单个TXT":
            text_content, filename, output_path = loader.get_txt_by_id(索引)
        elif 模式 == "顺序TXT":
            text_content, filename, output_path = loader.get_next_txt()
        else:
            if not loader.txt_paths:
                return ("", "", "")
            random.seed(种子)
            newindex = int(random.random() * len(loader.txt_paths))
            text_content, filename, output_path = loader.get_txt_by_id(newindex)

        if text_content is None:
            print("[Easy Use Ex] Error: Failed to load TXT file.")
            return ("", "", "")

        return (text_content, filename, output_path)

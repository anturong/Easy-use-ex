import glob
import json
import os

import numpy as np
import torch
from PIL import Image, ImageOps


ALLOWED_EXT = (".jpeg", ".jpg", ".png", ".tiff", ".gif", ".bmp", ".webp")


def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


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


class ImageBatchLoader:
    def __init__(self, directory_path, label, pattern, db, recursive=False):
        self.db = db
        self.label = label
        self.root_path = os.path.normpath(directory_path)
        self.image_paths = []
        self.load_images(directory_path, pattern, recursive)
        self.image_paths.sort()

        stored_path = db.get("BatchPaths", label)
        stored_pattern = db.get("BatchPatterns", label)
        stored_recursive = db.get("BatchRecursive", label)

        if stored_path != self.root_path or stored_pattern != pattern or stored_recursive != recursive:
            self.index = 0
            db.set("BatchCounters", label, 0)
            db.set("BatchPaths", label, self.root_path)
            db.set("BatchPatterns", label, pattern)
            db.set("BatchRecursive", label, recursive)
        else:
            self.index = db.get("BatchCounters", label)

    def load_images(self, directory_path, pattern, recursive=False):
        if recursive:
            search_pattern = os.path.join(glob.escape(directory_path), "**", pattern)
        else:
            search_pattern = os.path.join(glob.escape(directory_path), pattern)

        for file_name in glob.glob(search_pattern, recursive=recursive):
            if file_name.lower().endswith(ALLOWED_EXT):
                self.image_paths.append(os.path.abspath(file_name))

    def get_image_by_id(self, image_id):
        if image_id < 0 or image_id >= len(self.image_paths):
            return None, None, None
        return self._load_image(self.image_paths[image_id])

    def get_next_image(self):
        if not self.image_paths:
            return None, None, None

        if self.index >= len(self.image_paths):
            self.index = 0

        image_path = self.image_paths[self.index]
        self.index += 1
        if self.index >= len(self.image_paths):
            self.index = 0

        self.db.set("BatchCounters", self.label, self.index)
        return self._load_image(image_path)

    def _load_image(self, path):
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        filename = os.path.basename(path)
        output_path = os.path.join(os.path.abspath(os.path.dirname(path)), "")
        return image, filename, output_path


class EasyUseLoadImageBatch:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "easy_batch_state.json")
        self.db = EasyStateDB(self.db_path)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模式": (["单张图像", "顺序图像", "随机图像"],),
                "种子": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "索引": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                "批次标签": ("STRING", {"default": "批次 001", "multiline": False}),
                "路径": ("STRING", {"default": "", "multiline": False}),
                "匹配模式": ("STRING", {"default": "*", "multiline": False}),
                "递归搜索": ("BOOLEAN", {"default": False}),
                "允许RGBA输出": (["否", "是"],),
            },
            "optional": {
                "保留扩展名": (["是", "否"],),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("图像", "文件名", "输出路径")
    FUNCTION = "load_batch_images"
    CATEGORY = "EasyUse/加载"

    def load_batch_images(
        self,
        路径,
        匹配模式="*",
        索引=0,
        模式="单张图像",
        种子=0,
        批次标签="批次 001",
        递归搜索=False,
        允许RGBA输出="否",
        保留扩展名="是",
    ):
        允许RGBA输出 = 允许RGBA输出 == "是"

        if not os.path.exists(路径):
            print(f"[Easy Use Ex] Error: The path `{路径}` does not exist!")
            return (None, "", "")

        loader = ImageBatchLoader(路径, 批次标签, 匹配模式, self.db, recursive=递归搜索)

        if 模式 == "单张图像":
            image, filename, output_path = loader.get_image_by_id(索引)
            if image is None:
                print(f"[Easy Use Ex] Error: No valid image found for index `{索引}`")
                return (None, "", "")
        elif 模式 == "顺序图像":
            image, filename, output_path = loader.get_next_image()
            if image is None:
                print("[Easy Use Ex] Error: No valid images found in directory.")
                return (None, "", "")
        else:
            if not loader.image_paths:
                return (None, "", "")
            np.random.seed(种子)
            newindex = int(np.random.random() * len(loader.image_paths))
            image, filename, output_path = loader.get_image_by_id(newindex)
            if image is None:
                return (None, "", "")

        if not 允许RGBA输出:
            image = image.convert("RGB")

        if 保留扩展名 == "否":
            filename = os.path.splitext(filename)[0]

        return (pil2tensor(image), filename, output_path)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        if kwargs.get("模式") != "单张图像":
            return float("NaN")
        return ""

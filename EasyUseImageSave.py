import json
import os
import re
import time

import folder_paths as comfy_paths
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo


ALLOWED_EXT = (".jpeg", ".jpg", ".png", ".tiff", ".gif", ".bmp", ".webp")


def parse_simple_tokens(text):
    if not text:
        return text

    def replace_time(match):
        format_code = match.group(1)
        try:
            return time.strftime(format_code, time.localtime(time.time()))
        except Exception:
            return match.group(0)

    text = re.sub(r"\[time\((.*?)\)\]", replace_time, text)
    text = text.replace("[time]", str(int(time.time())))
    return text


def resolve_output_dir(base_output_dir, output_path):
    base_output_dir = os.path.abspath(base_output_dir)
    output_path = parse_simple_tokens(output_path)
    output_path = str(output_path or "").strip().strip("\"'")

    if output_path.lower() in ["", "none", "."]:
        return base_output_dir
    if os.path.isabs(output_path):
        return os.path.abspath(output_path)
    return os.path.abspath(os.path.join(base_output_dir, output_path))


class EasyUseImageSave:
    def __init__(self):
        self.output_dir = comfy_paths.output_directory
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "图像": ("IMAGE",),
                "输出路径": ("STRING", {"default": "[time(%Y-%m-%d)]", "multiline": False}),
                "文件名前缀": ("STRING", {"default": "ComfyUI"}),
                "文件名分隔符": ("STRING", {"default": "_"}),
                "序号位数": ("INT", {"default": 4, "min": 1, "max": 9, "step": 1}),
                "序号前置": (["否", "是"],),
                "格式": (["png", "jpg", "jpeg", "gif", "tiff", "webp", "bmp"],),
                "DPI": ("INT", {"default": 300, "min": 1, "max": 2400, "step": 1}),
                "质量": ("INT", {"default": 100, "min": 1, "max": 100, "step": 1}),
                "优化图像": (["是", "否"],),
                "无损WEBP": (["否", "是"],),
                "覆盖模式": (["否", "前缀作为文件名"],),
                "显示历史": (["否", "是"],),
                "按前缀筛选历史": (["是", "否"],),
                "嵌入工作流": (["是", "否"],),
                "显示预览": (["是", "否"],),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("图像", "文件列表")
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "EasyUse/保存"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save_images(
        self,
        图像,
        输出路径="",
        文件名前缀="ComfyUI",
        文件名分隔符="_",
        格式="png",
        DPI=300,
        质量=100,
        优化图像="是",
        无损WEBP="否",
        prompt=None,
        extra_pnginfo=None,
        覆盖模式="否",
        序号位数=4,
        序号前置="否",
        显示历史="否",
        按前缀筛选历史="是",
        嵌入工作流="是",
        显示预览="是",
    ):
        分隔符 = 文件名分隔符
        无损WEBP = 无损WEBP == "是"
        优化图像 = 优化图像 == "是"

        文件名前缀 = parse_simple_tokens(文件名前缀 or "ComfyUI")
        输出路径 = resolve_output_dir(self.output_dir, 输出路径)

        if 输出路径 and not os.path.exists(输出路径):
            print(f"[Easy Use Ex] Creating directory: {输出路径}")
            os.makedirs(输出路径, exist_ok=True)

        if 序号前置 == "是":
            pattern = rf"(\d+){re.escape(分隔符)}{re.escape(文件名前缀)}"
        else:
            pattern = rf"{re.escape(文件名前缀)}{re.escape(分隔符)}(\d+)"

        existing_counters = [
            int(match.group(1))
            for filename in os.listdir(输出路径)
            for match in [re.search(pattern, filename)]
            if match
        ]
        existing_counters.sort(reverse=True)
        counter = existing_counters[0] + 1 if existing_counters else 1

        file_extension = "." + 格式
        if file_extension not in ALLOWED_EXT:
            print("[Easy Use Ex] Invalid extension, defaulting to png.")
            file_extension = ".png"

        if 格式 == "webp":
            img_exif = Image.new("RGB", (1, 1)).getexif()
            if 嵌入工作流 == "是":
                if prompt is not None:
                    img_exif[0x010F] = "Prompt:" + json.dumps(prompt)
                if extra_pnginfo is not None:
                    workflow_metadata = "\n".join(json.dumps(x) for x in extra_pnginfo.values())
                    img_exif[0x010E] = "Workflow:" + workflow_metadata
            meta = img_exif.tobytes()
        else:
            metadata = PngInfo()
            if 嵌入工作流 == "是":
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for key in extra_pnginfo:
                        metadata.add_text(key, json.dumps(extra_pnginfo[key]))
            meta = metadata

        results = []
        output_files = []

        for 单张图像 in 图像:
            array = 255.0 * 单张图像.cpu().numpy()
            img = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))

            if 覆盖模式 == "前缀作为文件名":
                filename = f"{文件名前缀}{file_extension}"
            else:
                if 序号前置 == "是":
                    filename = f"{counter:0{序号位数}}{分隔符}{文件名前缀}{file_extension}"
                else:
                    filename = f"{文件名前缀}{分隔符}{counter:0{序号位数}}{file_extension}"

                while os.path.exists(os.path.join(输出路径, filename)):
                    counter += 1
                    if 序号前置 == "是":
                        filename = f"{counter:0{序号位数}}{分隔符}{文件名前缀}{file_extension}"
                    else:
                        filename = f"{文件名前缀}{分隔符}{counter:0{序号位数}}{file_extension}"

            output_file = os.path.abspath(os.path.join(输出路径, filename))

            try:
                if 格式 in ["jpg", "jpeg"]:
                    img.save(output_file, quality=质量, optimize=优化图像, dpi=(DPI, DPI))
                elif 格式 == "webp":
                    img.save(output_file, quality=质量, lossless=无损WEBP, exif=meta)
                elif 格式 == "png":
                    img.save(output_file, pnginfo=meta, optimize=优化图像, dpi=(DPI, DPI))
                elif 格式 == "bmp":
                    img.save(output_file)
                elif 格式 == "tiff":
                    img.save(output_file, quality=质量, optimize=优化图像)
                else:
                    img.save(output_file, pnginfo=meta, optimize=优化图像, dpi=(DPI, DPI))

                output_files.append(output_file)

                if 显示历史 != "是" and 显示预览 == "是":
                    subfolder = self.get_subfolder_path(output_file, self.output_dir)
                    results.append({"filename": filename, "subfolder": subfolder, "type": self.type})
            except Exception as exc:
                print(f"[Easy Use Ex] Error saving file to: {output_file}")
                print(exc)

            if 覆盖模式 == "否":
                counter += 1

        if 显示历史 == "是" and 显示预览 == "是" and os.path.exists(输出路径):
            all_files = [f for f in os.listdir(输出路径) if f.lower().endswith(ALLOWED_EXT)]
            if 按前缀筛选历史 == "是":
                all_files = [f for f in all_files if f.startswith(文件名前缀)]

            all_files.sort(key=lambda x: os.path.getmtime(os.path.join(输出路径, x)), reverse=True)

            for filename in all_files:
                subfolder = self.get_subfolder_path(os.path.join(输出路径, filename), self.output_dir)
                results.append({"filename": filename, "subfolder": subfolder, "type": self.type})

        if 显示预览 == "是":
            return {"ui": {"images": results, "files": output_files}, "result": (图像, output_files)}
        return {"ui": {"images": []}, "result": (图像, output_files)}

    def get_subfolder_path(self, image_path, output_path):
        output_parts = output_path.strip(os.sep).split(os.sep)
        image_parts = image_path.strip(os.sep).split(os.sep)
        common_parts = os.path.commonprefix([output_parts, image_parts])
        subfolder_parts = image_parts[len(common_parts) :]
        return os.sep.join(subfolder_parts[:-1])

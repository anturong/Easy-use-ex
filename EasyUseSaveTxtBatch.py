import os

import folder_paths as comfy_paths

from .EasyUseSaveUtils import (
    build_combined_stem,
    build_output_file_path,
    resolve_output_dir,
    strip_known_extension,
)


class EasyUseSaveTxtBatch:
    def __init__(self):
        self.output_dir = comfy_paths.output_directory

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "文本内容": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "输出路径": ("STRING", {"default": "[time(%Y-%m-%d)]", "multiline": False}),
                "文件名前缀": ("STRING", {"default": "", "multiline": False}),
                "文件名": ("STRING", {"default": "", "multiline": False}),
                "文件名分隔符": ("STRING", {"default": "_"}),
                "序号位数": ("INT", {"default": 4, "min": 1, "max": 9, "step": 1}),
                "序号前置": (["否", "是"],),
                "覆盖模式": (["否", "前缀作为文件名"],),
                "显示预览": (["是", "否"],),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("文本内容", "文件路径")
    FUNCTION = "save_txt"
    OUTPUT_NODE = True
    CATEGORY = "EasyUse/文本"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save_txt(
        self,
        文本内容,
        输出路径,
        文件名前缀,
        文件名,
        文件名分隔符="_",
        序号位数=4,
        序号前置="否",
        覆盖模式="否",
        显示预览="是",
    ):
        output_dir = resolve_output_dir(self.output_dir, 输出路径)
        os.makedirs(output_dir, exist_ok=True)

        stem = build_combined_stem(
            文件名前缀,
            strip_known_extension(文件名, ".txt"),
            文件名分隔符,
            "text",
        )
        output_file = build_output_file_path(
            output_dir=output_dir,
            stem=stem,
            extension=".txt",
            delimiter=文件名分隔符,
            digits=序号位数,
            number_first=序号前置,
            overwrite_mode=覆盖模式,
        )

        try:
            with open(output_file, "w", encoding="utf-8-sig", newline="\n") as file:
                file.write(文本内容 or "")
            print(f"[Easy Use Ex] TXT saved to: {output_file}")
        except Exception as exc:
            print(f"[Easy Use Ex] Error saving TXT: {exc}")
            return {"ui": {}, "result": (文本内容, "")}

        ui = {}
        if 显示预览 == "是":
            ui = {"files": [output_file], "string": [output_file]}

        return {"ui": ui, "result": (文本内容, output_file)}

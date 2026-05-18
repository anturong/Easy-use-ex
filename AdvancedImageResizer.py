import numpy as np
import torch
from PIL import Image


class ImageResizeWithColorAndDirection:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "图像": ("IMAGE",),
                "宽度": ("INT", {"default": 1890, "min": 1, "max": 99999, "step": 1}),
                "高度": ("INT", {"default": 1417, "min": 1, "max": 99999, "step": 1}),
                "重采样方式": (["最近邻", "双线性", "双三次", "兰索斯"],),
                "相对尺寸": (["否", "是"],),
                "锚点方向": (
                    [
                        "居中",
                        "左上",
                        "上",
                        "右上",
                        "左",
                        "右",
                        "左下",
                        "下",
                        "右下",
                    ],
                ),
                "背景颜色": (["黑色", "白色", "透明", "自定义"],),
                "自定义颜色": ("COLOR", {"default": "#000000"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("图像",)
    FUNCTION = "resize_with_color_and_direction"
    CATEGORY = "EasyUse/图像"
    DESCRIPTION = "调整图像画布大小，支持锚点方向和背景颜色。"

    def resize_with_color_and_direction(
        self,
        图像,
        宽度,
        高度,
        重采样方式,
        相对尺寸,
        锚点方向,
        背景颜色,
        自定义颜色,
    ):
        if 相对尺寸 == "是":
            当前宽度 = 图像.shape[2]
            当前高度 = 图像.shape[1]
            宽度 = 当前宽度 + 宽度
            高度 = 当前高度 + 高度

        宽度 = max(1, 宽度)
        高度 = max(1, 高度)

        方向映射 = {
            "居中": (0, 0),
            "左上": (-1, -1),
            "上": (0, -1),
            "右上": (1, -1),
            "左": (-1, 0),
            "右": (1, 0),
            "左下": (-1, 1),
            "下": (0, 1),
            "右下": (1, 1),
        }
        dx, dy = 方向映射[锚点方向]

        颜色映射 = {
            "黑色": (0, 0, 0),
            "白色": (255, 255, 255),
            "透明": (0, 0, 0, 0),
        }

        背景值 = 颜色映射.get(背景颜色, 自定义颜色)
        使用透明背景 = 背景颜色 == "透明"
        输出图像 = []

        for 图像张量 in 图像:
            数组 = 255.0 * 图像张量.cpu().numpy()
            PIL图像 = Image.fromarray(np.clip(数组, 0, 255).astype(np.uint8))
            原图含透明通道 = PIL图像.mode == "RGBA"

            if 使用透明背景:
                PIL图像 = PIL图像.convert("RGBA")
                新图像 = Image.new("RGBA", (宽度, 高度), (0, 0, 0, 0))
            else:
                PIL图像 = PIL图像.convert("RGB")
                填充值 = self._resolve_color(背景值)
                新图像 = Image.new("RGB", (宽度, 高度), 填充值)

            当前宽度 = PIL图像.width
            当前高度 = PIL图像.height

            偏移X = (宽度 - 当前宽度) * (dx + 1) // 2
            偏移Y = (高度 - 当前高度) * (dy + 1) // 2

            粘贴X = max(0, 偏移X)
            粘贴Y = max(0, 偏移Y)

            裁切X = max(0, -偏移X)
            裁切Y = max(0, -偏移Y)
            裁切宽度 = min(当前宽度 - 裁切X, 宽度 - 粘贴X)
            裁切高度 = min(当前高度 - 裁切Y, 高度 - 粘贴Y)

            if 裁切宽度 > 0 and 裁切高度 > 0:
                裁切图 = PIL图像.crop((裁切X, 裁切Y, 裁切X + 裁切宽度, 裁切Y + 裁切高度))
                if 使用透明背景:
                    新图像.paste(裁切图, (粘贴X, 粘贴Y), 裁切图)
                else:
                    新图像.paste(裁切图, (粘贴X, 粘贴Y))

            if 原图含透明通道 or 使用透明背景:
                输出 = 新图像.convert("RGBA")
            else:
                输出 = 新图像.convert("RGB")

            输出图像.append(np.array(输出).astype(np.float32) / 255.0)

        return (torch.from_numpy(np.array(输出图像)),)

    def _resolve_color(self, 值):
        if isinstance(值, str) and 值.startswith("#") and len(值) == 7:
            return tuple(int(值[i : i + 2], 16) for i in (1, 3, 5))
        if isinstance(值, (tuple, list)) and len(值) >= 3:
            return tuple(int(通道) for 通道 in 值[:3])
        return (0, 0, 0)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")


NODE_CLASS_MAPPINGS = {
    "ImageResizeWithColorAndDirection": ImageResizeWithColorAndDirection,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageResizeWithColorAndDirection": "高级画布调整",
}

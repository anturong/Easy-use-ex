import numpy as np
import torch
from PIL import Image, ImageFilter


def hex_to_rgb(hex_str: str):
    value = hex_str.strip().strip('"').strip("'").lstrip("#")
    if len(value) == 3:
        value = value[0] * 2 + value[1] * 2 + value[2] * 2
    if len(value) != 6:
        raise ValueError(f"Invalid HEX color: {hex_str!r}")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
    )


def compute_dist(image, target):
    target_tensor = torch.tensor(target[:3], device=image.device, dtype=image.dtype)
    diff = image[..., :3] - target_tensor
    return torch.sqrt(torch.sum(diff * diff, dim=-1))


def post_mask(mask, blur=0, dilate=0, erode=0, invert=False):
    if blur == 0 and dilate == 0 and erode == 0 and not invert:
        return mask

    device = mask.device
    dtype = mask.dtype
    processed = []

    for i in range(mask.shape[0]):
        array = (mask[i].cpu().numpy() * 255).astype(np.uint8)
        pil_mask = Image.fromarray(array, "L")
        if erode > 0:
            pil_mask = pil_mask.filter(ImageFilter.MinFilter(size=2 * erode + 1))
        if dilate > 0:
            pil_mask = pil_mask.filter(ImageFilter.MaxFilter(size=2 * dilate + 1))
        if blur > 0:
            pil_mask = pil_mask.filter(ImageFilter.GaussianBlur(radius=blur))
        if invert:
            pil_mask = Image.eval(pil_mask, lambda x: 255 - x)
        processed.append(np.array(pil_mask).astype(np.float32) / 255.0)

    return torch.from_numpy(np.stack(processed)).to(device=device, dtype=dtype)


class ColorID2Mask:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "hex_color": ("STRING", {"default": "#FF0000"}),
                "threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 0.5, "step": 0.005}),
                "blur_radius": ("INT", {"default": 0, "min": 0, "max": 30, "step": 1}),
                "dilate": ("INT", {"default": 0, "min": 0, "max": 20, "step": 1}),
                "erode": ("INT", {"default": 0, "min": 0, "max": 20, "step": 1}),
                "invert": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("mask",)
    FUNCTION = "run"
    CATEGORY = "EasyUse/Mask"

    def run(self, image, hex_color, threshold, blur_radius, dilate, erode, invert):
        target = hex_to_rgb(hex_color)
        dist = compute_dist(image, target)
        mask = (dist <= threshold).float()
        mask = post_mask(mask, blur_radius, dilate, erode, invert)
        return (mask,)


class ColorID2MaskBatch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "hex_color_list": ("STRING", {"default": "#FF0000\n#00FF00\n#0000FF", "multiline": True}),
                "threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 0.5, "step": 0.005}),
                "blur_radius": ("INT", {"default": 0, "min": 0, "max": 30, "step": 1}),
                "dilate": ("INT", {"default": 0, "min": 0, "max": 20, "step": 1}),
                "erode": ("INT", {"default": 0, "min": 0, "max": 20, "step": 1}),
                "invert": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("mask",)
    FUNCTION = "run"
    CATEGORY = "EasyUse/Mask"

    def run(self, image, hex_color_list, threshold, blur_radius, dilate, erode, invert):
        lines = [line.strip().strip('"').strip("'") for line in str(hex_color_list or "").split("\n") if line.strip()]
        combined = torch.zeros((image.shape[0], image.shape[1], image.shape[2]), device=image.device, dtype=image.dtype)
        for line in lines:
            try:
                target = hex_to_rgb(line)
            except Exception:
                continue
            dist = compute_dist(image, target)
            mask = (dist <= threshold).float()
            combined = torch.maximum(combined, mask)

        combined = post_mask(combined, blur_radius, dilate, erode, invert)
        return (combined,)


NODE_CLASS_MAPPINGS = {
    "ColorID2Mask": ColorID2Mask,
    "ColorID2MaskBatch": ColorID2MaskBatch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ColorID2Mask": "ColorID to Mask",
    "ColorID2MaskBatch": "ColorID Batch to Mask",
}

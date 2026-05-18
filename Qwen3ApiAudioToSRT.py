import json
import os
import re

import folder_paths
import numpy as np
import torch
from huggingface_hub import snapshot_download


def ensure_rope_scaling_factor(model_path):
    config_path = os.path.join(model_path, "config.json")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        need_save = False
        thinker_config = config.get("thinker_config", {})
        text_config = thinker_config.get("text_config", {})
        rope_scaling = text_config.get("rope_scaling")

        if rope_scaling and "factor" not in rope_scaling:
            rope_scaling["factor"] = 1.0
            text_config["rope_scaling"] = rope_scaling
            thinker_config["text_config"] = text_config
            config["thinker_config"] = thinker_config
            need_save = True

        if "rope_scaling" in config and "factor" not in config["rope_scaling"]:
            config["rope_scaling"]["factor"] = 1.0
            need_save = True

        if need_save:
            print(f"[EasyUse Qwen3-ASR] 自动修补配置: 为 {model_path} 添加缺失的 rope_scaling.factor = 1.0")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"[EasyUse Qwen3-ASR] 警告: 修补 config.json 时出错: {exc}")


ASR_UI_TO_MODEL_LANGUAGE = {
    "自动": "Auto",
    "中文": "Chinese",
    "英文": "English",
    "粤语": "Cantonese",
    "阿拉伯语": "Arabic",
    "德语": "German",
    "法语": "French",
    "西班牙语": "Spanish",
    "葡萄牙语": "Portuguese",
    "印尼语": "Indonesian",
    "意大利语": "Italian",
    "韩语": "Korean",
    "俄语": "Russian",
    "泰语": "Thai",
    "越南语": "Vietnamese",
    "日语": "Japanese",
    "土耳其语": "Turkish",
    "印地语": "Hindi",
    "马来语": "Malay",
    "荷兰语": "Dutch",
    "瑞典语": "Swedish",
    "丹麦语": "Danish",
    "芬兰语": "Finnish",
    "波兰语": "Polish",
    "捷克语": "Czech",
    "菲律宾语": "Filipino",
    "波斯语": "Persian",
    "希腊语": "Greek",
    "罗马尼亚语": "Romanian",
    "匈牙利语": "Hungarian",
    "马其顿语": "Macedonian",
}

ALIGNER_UI_TO_MODEL_LANGUAGE = {
    "中文": "Chinese",
    "英文": "English",
    "粤语": "Cantonese",
    "法语": "French",
    "德语": "German",
    "意大利语": "Italian",
    "日语": "Japanese",
    "韩语": "Korean",
    "葡萄牙语": "Portuguese",
    "俄语": "Russian",
    "西班牙语": "Spanish",
}

MODEL_TO_UI_LANGUAGE = {value: key for key, value in ASR_UI_TO_MODEL_LANGUAGE.items()}

ASR_MODELS = {
    "Qwen3-ASR-1.7B": "Qwen/Qwen3-ASR-1.7B",
    "Qwen3-ASR-0.6B": "Qwen/Qwen3-ASR-0.6B",
}

ALIGNER_MODELS = {
    "Qwen3-ForcedAligner-0.6B": "Qwen/Qwen3-ForcedAligner-0.6B",
}


def prepare_audio_input(audio):
    waveform = audio["waveform"]
    sample_rate = audio["sample_rate"]

    if isinstance(waveform, torch.Tensor):
        waveform = waveform.cpu().numpy()

    if waveform.ndim == 3:
        waveform = waveform[0]

    if waveform.ndim == 2:
        waveform = np.mean(waveform, axis=0)

    return waveform.astype(np.float32), sample_rate


class EasyUseQwen3ASR:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模型名称": (list(ASR_MODELS.keys()), {"default": "Qwen3-ASR-1.7B"}),
                "音频": ("AUDIO",),
                "语言": (list(ASR_UI_TO_MODEL_LANGUAGE.keys()), {"default": "自动"}),
            },
        }

    RETURN_TYPES = ("QWEN3ASR_MODEL", "STRING", "STRING")
    RETURN_NAMES = ("模型", "文本", "语言")
    FUNCTION = "transcribe"
    CATEGORY = "EasyUse/语音"

    def transcribe(self, 模型名称, 音频, 语言="自动"):
        from qwen_asr import Qwen3ASRModel

        models_dir = folder_paths.models_dir
        local_model_path = os.path.join(models_dir, "Qwen3-ASR", 模型名称)

        if not os.path.exists(local_model_path) or not os.listdir(local_model_path):
            print(f"[EasyUse Qwen3-ASR] Model not found, downloading: {模型名称}")
            os.makedirs(local_model_path, exist_ok=True)
            snapshot_download(
                repo_id=ASR_MODELS[模型名称],
                local_dir=local_model_path,
                local_dir_use_symlinks=False,
            )
            print(f"[EasyUse Qwen3-ASR] Model downloaded: {local_model_path}")
        else:
            print(f"[EasyUse Qwen3-ASR] Using local model: {local_model_path}")

        ensure_rope_scaling_factor(local_model_path)

        model = Qwen3ASRModel.from_pretrained(
            local_model_path,
            dtype=torch.bfloat16,
            device_map="cuda:0",
            max_inference_batch_size=32,
            max_new_tokens=512,
        )
        print(f"[EasyUse Qwen3-ASR] Model loaded: {模型名称}")

        waveform, sample_rate = prepare_audio_input(音频)
        model_language = ASR_UI_TO_MODEL_LANGUAGE.get(语言, "Auto")
        language_param = None if model_language == "Auto" else model_language

        results = model.transcribe(
            audio=(waveform, sample_rate),
            language=language_param,
            return_time_stamps=False,
        )

        result = results[0]
        text = result.text
        detected_language = MODEL_TO_UI_LANGUAGE.get(result.language, result.language)

        print(f"[EasyUse Qwen3-ASR] Detected language: {result.language}")
        print(f"[EasyUse Qwen3-ASR] Transcribed text: {text}")
        return (model, text, detected_language)


class EasyUseQwen3ForcedAlignerLoader:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模型名称": (list(ALIGNER_MODELS.keys()), {"default": "Qwen3-ForcedAligner-0.6B"}),
            },
        }

    RETURN_TYPES = ("QWEN3_ALIGNER",)
    RETURN_NAMES = ("对齐器",)
    FUNCTION = "load_model"
    CATEGORY = "EasyUse/语音"

    def load_model(self, 模型名称):
        from qwen_asr import Qwen3ForcedAligner

        models_dir = folder_paths.models_dir
        local_model_path = os.path.join(models_dir, "Qwen3-ASR", 模型名称)

        if not os.path.exists(local_model_path) or not os.listdir(local_model_path):
            print(f"[EasyUse Qwen3-ASR] Aligner not found, downloading: {模型名称}")
            os.makedirs(local_model_path, exist_ok=True)
            snapshot_download(
                repo_id=ALIGNER_MODELS[模型名称],
                local_dir=local_model_path,
                local_dir_use_symlinks=False,
            )
            print(f"[EasyUse Qwen3-ASR] Aligner downloaded: {local_model_path}")
        else:
            print(f"[EasyUse Qwen3-ASR] Using local aligner: {local_model_path}")

        ensure_rope_scaling_factor(local_model_path)

        aligner = Qwen3ForcedAligner.from_pretrained(
            local_model_path,
            dtype=torch.bfloat16,
            device_map="cuda:0",
        )
        print(f"[EasyUse Qwen3-ASR] ForcedAligner loaded: {模型名称}")
        return (aligner,)


class EasyUseQwen3ForcedAlign:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "对齐器": ("QWEN3_ALIGNER",),
                "音频": ("AUDIO",),
                "文本": ("STRING", {"multiline": True}),
                "语言": (list(ALIGNER_UI_TO_MODEL_LANGUAGE.keys()), {"default": "中文"}),
                "按句分段": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("时间戳", "文本列表", "开始时间", "结束时间")
    FUNCTION = "align"
    CATEGORY = "EasyUse/语音"

    def align(self, 对齐器, 音频, 文本, 语言, 按句分段=True):
        waveform, sample_rate = prepare_audio_input(音频)
        model_language = ALIGNER_UI_TO_MODEL_LANGUAGE[语言]
        results = 对齐器.align(
            audio=(waveform, sample_rate),
            text=文本,
            language=model_language,
        )

        items = results[0]
        texts, starts, ends = [], [], []

        if 按句分段:
            segments = [segment for segment in re.split(r"[。？！，、；.?!,;\s]+", 文本) if segment]
            item_idx = 0
            for segment in segments:
                seg_start = None
                seg_end = None
                matched = ""
                while item_idx < len(items) and len(matched) < len(segment):
                    if seg_start is None:
                        seg_start = items[item_idx].start_time
                    seg_end = items[item_idx].end_time
                    matched += items[item_idx].text
                    item_idx += 1
                if seg_start is not None:
                    texts.append(segment)
                    starts.append(f"{seg_start:.3f}")
                    ends.append(f"{seg_end:.3f}")
        else:
            for item in items:
                texts.append(item.text)
                starts.append(f"{item.start_time:.3f}")
                ends.append(f"{item.end_time:.3f}")

        timestamps_str = "\n".join(f"{t}\t{s}\t{e}" for t, s, e in zip(texts, starts, ends))
        print(f"[EasyUse Qwen3-ASR] Alignment completed, {len(texts)} segments")
        return (timestamps_str, "\n".join(texts), "\n".join(starts), "\n".join(ends))


NODE_CLASS_MAPPINGS = {
    "EasyUseQwen3ASR": EasyUseQwen3ASR,
    "EasyUseQwen3ForcedAlignerLoader": EasyUseQwen3ForcedAlignerLoader,
    "EasyUseQwen3ForcedAlign": EasyUseQwen3ForcedAlign,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EasyUseQwen3ASR": "Qwen3 API 音频 to SRT",
    "EasyUseQwen3ForcedAlignerLoader": "Qwen3 强制对齐器加载",
    "EasyUseQwen3ForcedAlign": "Qwen3 文本音频对齐",
}

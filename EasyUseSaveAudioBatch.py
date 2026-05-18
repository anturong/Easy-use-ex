import os
import shutil
import subprocess
import tempfile

import folder_paths as comfy_paths
import soundfile as sf
import torch
import torchaudio

from .EasyUseSaveUtils import (
    build_combined_stem,
    build_output_file_path,
    resolve_output_dir,
    strip_known_extension,
)


class EasyUseSaveAudioBatch:
    def __init__(self):
        self.output_dir = comfy_paths.output_directory

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "音频": ("AUDIO",),
                "采样率": ("INT", {"default": 44100, "min": 8000, "max": 192000, "step": 1}),
                "输出路径": ("STRING", {"default": "[time(%Y-%m-%d)]", "multiline": False}),
                "文件名前缀": ("STRING", {"default": "ComfyUI_Audio"}),
                "文件名": ("STRING", {"default": "", "multiline": False}),
                "文件名分隔符": ("STRING", {"default": "_"}),
                "序号位数": ("INT", {"default": 4, "min": 1, "max": 9, "step": 1}),
                "序号前置": (["否", "是"],),
                "格式": (["wav", "flac", "ogg", "mp3", "m4a", "aac", "wma", "ac3", "aiff", "opus", "m4b", "caf", "dts", "amr"],),
                "覆盖模式": (["否", "前缀作为文件名"],),
                "显示预览": (["是", "否"],),
            }
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("音频", "文件路径")
    FUNCTION = "save_audio"
    OUTPUT_NODE = True
    CATEGORY = "EasyUse/音频"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    _FFMPEG_CODEC_ARGS = {
        "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
        "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
        "wav": ["-c:a", "pcm_s16le"],
        "flac": ["-c:a", "flac"],
        "m4a": ["-c:a", "aac", "-b:a", "192k"],
        "aac": ["-c:a", "aac"],
        "wma": ["-c:a", "wmav2"],
        "ac3": ["-c:a", "ac3"],
        "aiff": ["-c:a", "pcm_s16be"],
        "opus": ["-c:a", "libopus"],
        "m4b": ["-c:a", "aac", "-b:a", "128k"],
        "caf": ["-c:a", "pcm_s16le"],
        "dts": ["-c:a", "dca", "-strict", "-2"],
        "amr": ["-c:a", "libopencore_amrnb", "-ar", "8000", "-b:a", "12.2k", "-ac", "1"],
    }

    @staticmethod
    def _normalize_audio_for_save(waveform):
        if not isinstance(waveform, torch.Tensor):
            waveform = torch.as_tensor(waveform)

        waveform = waveform.detach()

        if waveform.ndim == 0:
            raise ValueError("Unsupported scalar audio tensor.")

        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        elif waveform.ndim == 2:
            # If shape looks like [time, channels], transpose to [channels, time].
            if waveform.shape[1] <= 8 and waveform.shape[0] > waveform.shape[1]:
                waveform = waveform.transpose(0, 1)
        elif waveform.ndim == 3:
            # Common ComfyUI shape is [batch, channels, time] or [batch, time, channels].
            if waveform.shape[0] == 1:
                waveform = waveform.squeeze(0)
            elif waveform.shape[2] == 1 or waveform.shape[2] <= 8:
                waveform = waveform[0].transpose(0, 1)
            else:
                waveform = waveform[0]
        else:
            raise ValueError(f"Unsupported audio tensor shape: {tuple(waveform.shape)}")

        if waveform.ndim != 2:
            raise ValueError(f"Unsupported audio tensor shape after normalization: {tuple(waveform.shape)}")

        waveform = waveform.to(device="cpu", dtype=torch.float32).contiguous()
        waveform = torch.nan_to_num(waveform, nan=0.0, posinf=1.0, neginf=-1.0)
        waveform = waveform.clamp(-1.0, 1.0)
        return waveform

    @staticmethod
    def _write_temp_wav(waveform, sample_rate):
        audio_data = waveform.transpose(0, 1).cpu().numpy()
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_file.close()
        sf.write(temp_file.name, audio_data, sample_rate, subtype="PCM_16")
        return temp_file.name

    @classmethod
    def _save_audio_with_ffmpeg(cls, waveform, sample_rate, output_file, audio_format):
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise RuntimeError("FFmpeg is not available in PATH.")

        codec_args = cls._FFMPEG_CODEC_ARGS.get(audio_format.lower())
        if not codec_args:
            raise RuntimeError(f"Unsupported FFmpeg audio format: {audio_format}")

        temp_wav = cls._write_temp_wav(waveform, sample_rate)
        try:
            command = [
                ffmpeg_path,
                "-y",
                "-i",
                temp_wav,
                *codec_args,
                output_file,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError((result.stderr or result.stdout).strip())
        finally:
            try:
                os.unlink(temp_wav)
            except OSError:
                pass

    @classmethod
    def _save_audio_file(cls, waveform, sample_rate, output_file, audio_format):
        audio_format = audio_format.lower()

        if audio_format in {"wav", "flac", "aiff", "caf"}:
            audio_data = waveform.transpose(0, 1).cpu().numpy()
            subtype_map = {
                "wav": "PCM_16",
                "flac": None,
                "aiff": "PCM_16",
                "caf": "PCM_16",
            }
            subtype = subtype_map[audio_format]
            sf.write(output_file, audio_data, sample_rate, subtype=subtype)
            return

        cls._save_audio_with_ffmpeg(waveform, sample_rate, output_file, audio_format)

    def save_audio(
        self,
        音频,
        采样率,
        输出路径,
        文件名前缀,
        文件名,
        文件名分隔符="_",
        序号位数=4,
        序号前置="否",
        格式="wav",
        覆盖模式="否",
        显示预览="是",
    ):
        output_dir = resolve_output_dir(self.output_dir, 输出路径)
        os.makedirs(output_dir, exist_ok=True)

        if isinstance(音频, dict):
            waveform = 音频["waveform"]
            audio_sample_rate = 音频.get("sample_rate", 采样率)
        else:
            waveform = 音频
            audio_sample_rate = 采样率

        try:
            waveform = self._normalize_audio_for_save(waveform)
            audio_sample_rate = int(audio_sample_rate)
        except Exception as exc:
            print(f"[Easy Use Ex] Error: {exc}")
            return {"ui": {}, "result": (音频, "")}

        stem = build_combined_stem(
            文件名前缀,
            strip_known_extension(文件名, f".{格式}"),
            文件名分隔符,
            "audio",
        )

        output_file = build_output_file_path(
            output_dir=output_dir,
            stem=stem,
            extension=格式,
            delimiter=文件名分隔符,
            digits=序号位数,
            number_first=序号前置,
            overwrite_mode=覆盖模式,
        )

        try:
            self._save_audio_file(waveform, audio_sample_rate, output_file, 格式)
            print(f"[Easy Use Ex] Audio saved to: {output_file}")
        except Exception as exc:
            print(
                f"[Easy Use Ex] Error saving audio: {exc} | "
                f"shape={tuple(waveform.shape)} dtype={waveform.dtype} sample_rate={audio_sample_rate}"
            )
            return {"ui": {}, "result": (音频, "")}

        ui = {}
        if 显示预览 == "是":
            ui = {"files": [output_file], "string": [output_file]}

        return {"ui": ui, "result": (音频, output_file)}

import glob
import json
import os
import shutil
import subprocess
import tempfile

import soundfile as sf
import torch
import torchaudio


AUDIO_EXTENSIONS = (
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".aac",
    ".m4a",
    ".wma",
    ".ac3",
    ".aiff",
    ".opus",
    ".m4b",
    ".caf",
    ".dts",
    ".amr",
)


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


class AudioBatchLoader:
    def __init__(self, directory_path, label, pattern, db, recursive=False):
        self.db = db
        self.root_path = os.path.abspath(os.path.normpath(directory_path))
        self.audio_paths = []
        self.label = label
        self.load_audios(self.root_path, pattern, recursive)
        self.audio_paths.sort()

        stored_path = db.get("AudioBatchPaths", label)
        stored_pattern = db.get("AudioBatchPatterns", label)
        stored_recursive = db.get("AudioBatchRecursive", label)
        if stored_path != self.root_path or stored_pattern != pattern or stored_recursive != recursive:
            self.index = 0
            db.set("AudioBatchCounters", label, 0)
            db.set("AudioBatchPaths", label, self.root_path)
            db.set("AudioBatchPatterns", label, pattern)
            db.set("AudioBatchRecursive", label, recursive)
        else:
            self.index = db.get("AudioBatchCounters", label)

    def load_audios(self, directory_path, pattern, recursive=False):
        if recursive:
            search_pattern = os.path.join(glob.escape(directory_path), "**", pattern)
        else:
            search_pattern = os.path.join(glob.escape(directory_path), pattern)

        for file_name in glob.glob(search_pattern, recursive=recursive):
            if file_name.lower().endswith(AUDIO_EXTENSIONS):
                self.audio_paths.append(os.path.abspath(file_name))

    @staticmethod
    def _load_audio_with_ffmpeg(path):
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise RuntimeError("FFmpeg is not available in PATH.")

        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_file.close()
        try:
            command = [
                ffmpeg_path,
                "-y",
                "-i",
                path,
                "-vn",
                "-c:a",
                "pcm_s16le",
                temp_file.name,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError((result.stderr or result.stdout).strip())

            waveform, sample_rate = sf.read(temp_file.name, dtype="float32", always_2d=True)
            tensor = torch.from_numpy(waveform.T)
            return tensor, sample_rate
        finally:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

    def get_audio_by_id(self, audio_id):
        if audio_id < 0 or audio_id >= len(self.audio_paths):
            return None, None, None, None
        return self._load_audio_file(self.audio_paths[audio_id])

    def get_next_audio(self):
        if not self.audio_paths:
            return None, None, None, None

        if self.index >= len(self.audio_paths):
            self.index = 0

        audio_path = self.audio_paths[self.index]
        self.index += 1
        if self.index >= len(self.audio_paths):
            self.index = 0

        self.db.set("AudioBatchCounters", self.label, self.index)
        return self._load_audio_file(audio_path)

    def _load_audio_file(self, path):
        try:
            waveform, sample_rate = torchaudio.load(path)
            audio_tensor = waveform.unsqueeze(0)
            filename = os.path.basename(path)
            output_path = os.path.join(os.path.abspath(os.path.dirname(path)), "")
            return audio_tensor, sample_rate, filename, output_path
        except Exception as exc:
            try:
                waveform, sample_rate = self._load_audio_with_ffmpeg(path)
                audio_tensor = waveform.unsqueeze(0)
                filename = os.path.basename(path)
                output_path = os.path.join(os.path.abspath(os.path.dirname(path)), "")
                print(f"[Easy Use Ex] Audio loaded through FFmpeg fallback: {path}")
                return audio_tensor, sample_rate, filename, output_path
            except Exception as ffmpeg_exc:
                print(f"[Easy Use Ex] Error loading audio {path}: {exc}")
                print(f"[Easy Use Ex] FFmpeg fallback also failed: {ffmpeg_exc}")
                return None, None, None, None


class EasyUseLoadAudioBatch:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "easy_audio_state.json")
        self.db = EasyStateDB(self.db_path)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模式": (["单个音频", "顺序音频", "随机音频"],),
                "种子": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "索引": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                "批次标签": ("STRING", {"default": "音频批次 001", "multiline": False}),
                "路径": ("STRING", {"default": "", "multiline": False}),
                "匹配模式": (["*.wav", "*.mp3", "*.flac", "*.ogg", "*.aac", "*.m4a", "*.wma", "*.ac3", "*.aiff", "*.opus", "*.m4b", "*.caf", "*.dts", "*.amr", "*"],),
                "递归搜索": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "保留扩展名": (["是", "否"],),
            },
        }

    RETURN_TYPES = ("AUDIO", "INT", "STRING", "STRING")
    RETURN_NAMES = ("音频", "采样率", "文件名", "输出路径")
    FUNCTION = "load_audio_batch"
    CATEGORY = "EasyUse/音频"

    def load_audio_batch(self, 模式, 种子, 索引, 批次标签, 路径, 匹配模式, 递归搜索, 保留扩展名="是"):
        empty_audio = {"waveform": torch.zeros(1, 2, 44100), "sample_rate": 44100}

        if not os.path.exists(路径):
            print(f"[Easy Use Ex] Error: The path `{路径}` does not exist!")
            return (empty_audio, 44100, "", "")

        loader = AudioBatchLoader(路径, 批次标签, 匹配模式, self.db, recursive=递归搜索)

        if 模式 == "单个音频":
            audio, sample_rate, filename, output_path = loader.get_audio_by_id(索引)
        elif 模式 == "顺序音频":
            audio, sample_rate, filename, output_path = loader.get_next_audio()
        else:
            if not loader.audio_paths:
                return (empty_audio, 44100, "", "")
            torch.manual_seed(种子)
            newindex = int(torch.rand(1).item() * len(loader.audio_paths))
            audio, sample_rate, filename, output_path = loader.get_audio_by_id(newindex)

        if audio is None:
            print("[Easy Use Ex] Error: Failed to load audio.")
            return (empty_audio, 44100, "", "")

        if 保留扩展名 == "否":
            filename = os.path.splitext(filename)[0]

        return ({"waveform": audio, "sample_rate": sample_rate}, sample_rate, filename, output_path)

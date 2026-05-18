import torch


MAX_AUDIO_SLOTS = 10


class EasyUseDubbingAutomation:
    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "触发路径": (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": "输入触发路径，可以是文件夹路径，也可以是包含文件名的完整路径。",
                },
            ),
            "匹配模式": (
                ["文件夹匹配", "完全一致", "包含", "前缀匹配", "后缀匹配"],
                {
                    "default": "文件夹匹配",
                    "tooltip": "文件夹匹配只比较目录并忽略结尾斜杠；其余模式按字符串方式匹配触发路径。",
                },
            ),
            "文件夹路径列表": (
                "STRING",
                {
                    "multiline": True,
                    "default": "",
                    "placeholder": "dir /s /b /ad\nC:\\Users\\41456\\Desktop\\spitl\\角色分解\\A\nC:\\Users\\41456\\Desktop\\spitl\\角色分解\\B\nC:\\Users\\41456\\Desktop\\spitl\\角色分解\\C",
                    "tooltip": "每行输入一个文件夹路径，并与下方对应序号的配音音频一一匹配。可先在命令行运行 dir /s /b /ad 获取目录列表。",
                },
            ),
        }

        optional = {}
        for index in range(1, MAX_AUDIO_SLOTS + 1):
            optional[f"配音{index}_音频"] = (
                "AUDIO",
                {
                    "tooltip": f"第 {index} 组音频，对应文件夹路径列表中的第 {index} 行。",
                },
            )

        optional["兜底音频"] = (
            "AUDIO",
            {"tooltip": "没有命中任何路径时返回的默认音频。"},
        )

        return {
            "required": required,
            "optional": optional,
        }

    RETURN_TYPES = ("AUDIO", "STRING", "BOOLEAN")
    RETURN_NAMES = ("匹配音频", "匹配路径", "是否命中")
    FUNCTION = "dubbing_automation"
    CATEGORY = "EasyUse/音频"
    OUTPUT_NODE = False

    _MODE_MAP = {
        "文件夹匹配": "folder",
        "完全一致": "exact",
        "包含": "contains",
        "前缀匹配": "starts_with",
        "后缀匹配": "ends_with",
    }

    @classmethod
    def _normalize_folder_path(cls, value):
        return str(value or "").replace("\\", "/").rstrip("/").lower()

    @classmethod
    def _path_matches(cls, path, match_path, mode):
        if not match_path:
            return False

        internal_mode = cls._MODE_MAP.get(mode, "folder")

        if internal_mode == "folder":
            normalized_match = cls._normalize_folder_path(match_path)
            normalized_path = cls._normalize_folder_path(path)

            if normalized_path == normalized_match:
                return True

            return normalized_path.startswith(normalized_match + "/")

        path = str(path or "")
        match_path = str(match_path)

        if internal_mode == "exact":
            return path == match_path
        if internal_mode == "contains":
            return match_path in path
        if internal_mode == "starts_with":
            return path.startswith(match_path)
        if internal_mode == "ends_with":
            return path.endswith(match_path)
        return False

    def dubbing_automation(self, 触发路径, 匹配模式="文件夹匹配", 文件夹路径列表="", **kwargs):
        folder_paths = [
            line.strip()
            for line in str(文件夹路径列表 or "").splitlines()
            if line.strip()
        ]

        for index, folder_path in enumerate(folder_paths, start=1):
            audio = kwargs.get(f"配音{index}_音频")
            if audio is None:
                continue

            if self._path_matches(触发路径, folder_path, 匹配模式):
                print(f"[Easy Use Ex] Dubbing automation matched slot {index}: {folder_path}")
                return (audio, folder_path, True)

        default_audio = kwargs.get("兜底音频")
        if default_audio is not None:
            print("[Easy Use Ex] Dubbing automation fallback audio used.")
            return (default_audio, "", False)

        silent_audio = {
            "waveform": torch.zeros(1, 1, 1),
            "sample_rate": 44100,
        }
        print("[Easy Use Ex] Dubbing automation found no match; returning silent audio.")
        return (silent_audio, "", False)


NODE_CLASS_MAPPINGS = {
    "Easy Use Dubbing Automation": EasyUseDubbingAutomation,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Easy Use Dubbing Automation": "配音自动化",
}

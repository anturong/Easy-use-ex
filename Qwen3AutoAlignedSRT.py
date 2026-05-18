import json
import os
import tempfile
import time

import numpy as np
import requests
import soundfile as sf
import torch


DEFAULT_QWEN3_ASR_SERVICE_URL = os.environ.get("QWEN3_ASR_SERVICE_URL", "http://127.0.0.1:8770")

LANGUAGE_OPTIONS = [
    "自动",
    "中文",
    "英文",
    "粤语",
    "阿拉伯语",
    "德语",
    "法语",
    "西班牙语",
    "葡萄牙语",
    "印尼语",
    "意大利语",
    "韩语",
    "俄语",
    "泰语",
    "越南语",
    "日语",
    "土耳其语",
    "印地语",
    "马来语",
    "荷兰语",
    "瑞典语",
    "丹麦语",
    "芬兰语",
    "波兰语",
    "捷克语",
    "菲律宾语",
    "波斯语",
    "希腊语",
    "罗马尼亚语",
    "匈牙利语",
    "马其顿语",
]

DIARIZATION_MODE_OPTIONS = [
    "独占分离（推荐）",
    "普通分离",
]

EMPTY_RESULT = ("", "", "", "[]", "{}")
SERVICE_IDLE_WAIT_SECONDS = 300
HEALTH_CHECK_TIMEOUT_SECONDS = 30
TRANSCRIBE_CONNECT_TIMEOUT_SECONDS = 30
TRANSCRIBE_READ_TIMEOUT_SECONDS = 3600
HEALTH_POLL_INTERVAL_SECONDS = 1.5
TRANSCRIBE_SUBMIT_RETRY_COUNT = 3


def prepare_audio_input(audio):
    waveform = audio["waveform"]
    sample_rate = audio["sample_rate"]

    if isinstance(waveform, torch.Tensor):
        waveform = waveform.detach().cpu().numpy()

    if waveform.ndim == 3:
        waveform = waveform[0]

    if waveform.ndim == 2:
        waveform = np.mean(waveform, axis=0)

    waveform = np.asarray(waveform, dtype=np.float32)
    return waveform, sample_rate


def normalize_service_url(service_url: str) -> str:
    url = (service_url or "").strip() or DEFAULT_QWEN3_ASR_SERVICE_URL
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url.rstrip("/")


def map_diarization_mode(label: str) -> str:
    if label == "普通分离":
        return "standard"
    return "exclusive"


def build_error_result(message: str):
    print(message)
    return {"ui": {"string": [message]}, "result": EMPTY_RESULT}


def wait_for_service_idle(session: requests.Session, health_url: str, service_url: str) -> None:
    deadline = time.time() + SERVICE_IDLE_WAIT_SECONDS
    last_error = None

    while time.time() < deadline:
        try:
            response = session.get(health_url, timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
            progress = payload.get("progress") or {}
            if not progress.get("active"):
                print(f"[Easy Use Ex] QWEN3_ASR 已空闲 | 连接={service_url}")
                return

            stage = progress.get("stage", "unknown")
            percent = progress.get("percent", 0)
            message = progress.get("message", "")
            busy_owner = payload.get("busy_owner") or "unknown"
            print(
                f"[Easy Use Ex] QWEN3_ASR 等待中 | 连接={service_url} | "
                f"持有者={busy_owner} | 进度={percent}% | 阶段={stage} | {message}"
            )
            last_error = None
        except requests.RequestException as exc:
            last_error = exc
            print(f"[Easy Use Ex] QWEN3_ASR 等待中 | 连接={service_url} | health重试 | {exc}")

        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)

    if last_error is not None:
        raise requests.RequestException(
            f"QWEN3_ASR service did not become ready in time and last health check failed: {last_error}"
        )
    raise requests.RequestException(
        f"QWEN3_ASR service stayed busy for more than {SERVICE_IDLE_WAIT_SECONDS} seconds: {service_url}"
    )


def submit_transcribe_with_retry(session: requests.Session, transcribe_url: str, health_url: str, service_url: str, payload: dict):
    last_http_error = None

    for attempt in range(1, TRANSCRIBE_SUBMIT_RETRY_COUNT + 1):
        response = session.post(
            transcribe_url,
            json=payload,
            timeout=(TRANSCRIBE_CONNECT_TIMEOUT_SECONDS, TRANSCRIBE_READ_TIMEOUT_SECONDS),
        )

        if response.status_code != 409:
            response.raise_for_status()
            return response

        detail = {}
        try:
            detail = response.json().get("detail") or {}
        except Exception:
            detail = {}

        progress = detail.get("progress") or {}
        busy_owner = detail.get("busy_owner") or "unknown"
        print(
            f"[Easy Use Ex] QWEN3_ASR 重试中 | 连接={service_url} | "
            f"第{attempt}/{TRANSCRIBE_SUBMIT_RETRY_COUNT}次 | 持有者={busy_owner} | "
            f"进度={progress.get('percent', 0)}% | 阶段={progress.get('stage', 'unknown')} | "
            f"{progress.get('message', '')}"
        )

        last_http_error = requests.HTTPError(
            f"QWEN3_ASR service busy: owner={busy_owner}",
            response=response,
        )

        if attempt >= TRANSCRIBE_SUBMIT_RETRY_COUNT:
            break

        wait_for_service_idle(session, health_url, service_url)

    if last_http_error is not None:
        raise last_http_error
    raise requests.RequestException(f"QWEN3_ASR submit failed unexpectedly: {service_url}")


def call_qwen3_asr_api(service_url: str, payload: dict) -> dict:
    health_url = f"{service_url}/health"
    transcribe_url = f"{service_url}/transcribe"
    headers = {
        "Connection": "close",
        "Content-Type": "application/json",
    }

    with requests.Session() as session:
        session.headers.update(headers)
        wait_for_service_idle(session, health_url, service_url)
        response = submit_transcribe_with_retry(session, transcribe_url, health_url, service_url, payload)
        data = response.json()

    return {
        "service_url": service_url,
        "health_url": health_url,
        "transcribe_url": transcribe_url,
        "data": data,
    }


class EasyUseRoleAlignedSRT:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "音频": ("AUDIO",),
                "API地址": ("STRING", {"default": DEFAULT_QWEN3_ASR_SERVICE_URL}),
                "语言": (LANGUAGE_OPTIONS, {"default": "中文"}),
                "说话人分离模式": (DIARIZATION_MODE_OPTIONS, {"default": "独占分离（推荐）"}),
                "说话人数": ("INT", {"default": 2, "min": 1, "max": 16, "step": 1}),
                "每行最大秒数": ("FLOAT", {"default": 4.5, "min": 0.5, "max": 30.0, "step": 0.1}),
                "每行最大字数": ("INT", {"default": 28, "min": 1, "max": 300, "step": 1}),
                "断句标点": ("STRING", {"default": "，。！；：、,.!?;…"}),
            },
            "optional": {
                "角色映射": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("角色SRT", "开始时间列表", "结束时间列表", "角色字幕JSON", "调试信息")
    FUNCTION = "build_srt"
    CATEGORY = "EasyUse/语音"
    OUTPUT_NODE = True

    def build_srt(
        self,
        音频,
        API地址,
        语言,
        说话人分离模式,
        说话人数=2,
        每行最大秒数=4.5,
        每行最大字数=28,
        断句标点="，。！；：、,.!?;…",
        角色映射="",
    ):
        waveform, sample_rate = prepare_audio_input(音频)
        temp_path = None
        service_url = normalize_service_url(API地址)

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                temp_path = tmp.name
            sf.write(temp_path, waveform, sample_rate)

            payload = {
                "audio_path": temp_path,
                "model": "Qwen3-ASR-0.6B",
                "language": 语言,
                "device": "auto",
                "max_line_seconds": float(每行最大秒数),
                "max_line_chars": int(每行最大字数),
                "punctuation": 断句标点,
                "use_speaker_labels": True,
                "speaker_count": int(说话人数),
                "role_map": 角色映射.strip() or None,
                "diarization_mode": map_diarization_mode(说话人分离模式),
            }

            api_result = call_qwen3_asr_api(service_url, payload)
            health_url = api_result["health_url"]
            transcribe_url = api_result["transcribe_url"]
            data = api_result["data"]

            srt_content = data.get("srt_content", "")
            role_subtitles = data.get("role_subtitles", [])
            alignment_info = data.get("alignment_info", {})

            if not srt_content:
                return build_error_result(
                    f"[Easy Use Ex] Error: QWEN3_ASR 服务未返回 SRT 内容 | API地址={service_url}"
                )

            role_json = json.dumps(role_subtitles, ensure_ascii=False, indent=2)
            start_list = "\n".join(f"{item.get('start', 0):.3f}" for item in role_subtitles)
            end_list = "\n".join(f"{item.get('end', 0):.3f}" for item in role_subtitles)
            debug_info = json.dumps(
                {
                    "service_url": service_url,
                    "health_url": health_url,
                    "transcribe_url": transcribe_url,
                    "alignment_info": alignment_info,
                },
                ensure_ascii=False,
                indent=2,
            )

            summary = (
                f"QWEN3_ASR API 调用完成: {len(role_subtitles)} 条角色字幕 | "
                f"连接={service_url} | "
                f"角色: {', '.join(alignment_info.get('detected_roles', [])) or '无'}"
            )
            print(f"[Easy Use Ex] {summary}")
            return {"ui": {"string": [summary]}, "result": (srt_content, start_list, end_list, role_json, debug_info)}

        except requests.HTTPError as exc:
            detail = ""
            response_obj = getattr(exc, "response", None)
            if response_obj is not None:
                try:
                    detail = response_obj.text.strip()
                except Exception:
                    detail = ""
            message = (
                f"[Easy Use Ex] Error: QWEN3_ASR API HTTP失败 | "
                f"连接={service_url} | 状态={getattr(response_obj, 'status_code', 'unknown')} | {detail or exc}"
            )
            return build_error_result(message)
        except requests.RequestException as exc:
            return build_error_result(f"[Easy Use Ex] Error: 调用 QWEN3_ASR API 失败 | 连接={service_url} | {exc}")
        except Exception as exc:
            return build_error_result(f"[Easy Use Ex] Error: 节点执行失败 | 连接={service_url} | {type(exc).__name__}: {exc}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


NODE_CLASS_MAPPINGS = {
    "Easy Use Role Aligned SRT": EasyUseRoleAlignedSRT,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Easy Use Role Aligned SRT": "Qwen3自动精确对齐SRT",
}

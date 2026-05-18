import json
import os
import re
from datetime import datetime, timezone
from aiohttp import web
from server import PromptServer


DEBUG_LOG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "subcast_debug_logs")


def parse_character(raw_text: str) -> dict | None:
    patterns = [
        r"^\s*\[([^\]]+)\]\s*([\s\S]*)",
        r"^\s*\(([^)]+)\)\s*([\s\S]*)",
        r"^\s*([^:\n]{1,20})[:：]\s*([\s\S]*)",
    ]
    for pattern in patterns:
        match = re.match(pattern, raw_text)
        if match and match[1].strip():
            return {"character": match[1].strip(), "text": match[2].strip()}
    return None


def parse_srt(text: str) -> list:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    blocks = text.strip().split("\n\n") if text.strip() else []
    result = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        tm = re.match(
            r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})",
            lines[1].strip(),
        )
        if not tm:
            continue
        start_raw = tm.group(1)
        end_raw = tm.group(2)
        raw_text = "\n".join(lines[2:]).strip()
        parsed = parse_character(raw_text)
        result.append(
            {
                "index": idx,
                "startRaw": start_raw,
                "endRaw": end_raw,
                "start": start_raw.replace(",", "."),
                "end": end_raw.replace(",", "."),
                "character": parsed["character"] if parsed else "",
                "text": parsed["text"] if parsed else raw_text,
                "rawText": raw_text,
            }
        )
    return result


def write_debug_log(session_id: str, event: str, payload: dict | None = None) -> str:
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    safe_session_id = re.sub(r"[^a-zA-Z0-9._-]", "_", str(session_id or "unknown"))
    filepath = os.path.join(DEBUG_LOG_DIR, f"{safe_session_id}.jsonl")
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "payload": payload or {},
    }
    with open(filepath, "a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")

    files = sorted(
        (
            os.path.join(DEBUG_LOG_DIR, name)
            for name in os.listdir(DEBUG_LOG_DIR)
            if name.endswith(".jsonl")
        ),
        key=os.path.getmtime,
        reverse=True,
    )
    for stale_file in files[5:]:
        try:
            os.remove(stale_file)
        except OSError:
            pass
    return filepath


class EasyUseSubCastEditor:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "srt_text": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "SRT subtitle text",
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("srt_text",)
    FUNCTION = "process"
    CATEGORY = "EasyUse/文本"
    OUTPUT_NODE = True

    def process(self, srt_text: str = ""):
        return (srt_text or "",)


@PromptServer.instance.routes.post("/easyuse/subcast/parse")
async def easyuse_subcast_parse(request):
    data = await request.json()
    srt_text = data.get("srt_text", "")
    subs = parse_srt(srt_text)
    return web.json_response({"subtitles": subs, "count": len(subs)})


@PromptServer.instance.routes.post("/easyuse/subcast/upload")
async def easyuse_subcast_upload(request):
    reader = await request.multipart()
    field = await reader.next()
    if field is None:
        return web.json_response({"error": "No file"}, status=400)
    content = await field.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="ignore")
    subs = parse_srt(text)
    return web.json_response({"subtitles": subs, "count": len(subs), "filename": field.filename})


@PromptServer.instance.routes.post("/easyuse/subcast/debug_log")
async def easyuse_subcast_debug_log(request):
    data = await request.json()
    session_id = data.get("session_id", "unknown")
    event = data.get("event", "unknown")
    payload = data.get("payload", {})
    filepath = write_debug_log(session_id=session_id, event=event, payload=payload)
    return web.json_response({"ok": True, "path": filepath})

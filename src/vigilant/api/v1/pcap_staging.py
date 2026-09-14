from __future__ import annotations

import base64
import binascii
import os
import re
import uuid
from pathlib import Path
from typing import Final

from fastapi import APIRouter, HTTPException
from fastapi import Path as FastAPIPath
from fastapi.responses import FileResponse

from vigilant.api.v1.chat_schema import ChatMessage, FilePart, ImagePart, TextPart

pcap_router = APIRouter()


@pcap_router.get("/files/{file_id}")
async def get_file_info(
    file_id: str = FastAPIPath(..., description="The unique ID of the staged file (e.g., the pcap_ref)"),
) -> dict[str, object]:
    """Check if a staged file exists."""
    file_path = STAGING_ROOT / file_id / "attachment.bin"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in staging.")

    return {"file_id": file_id, "exists": True, "path": str(file_path)}


@pcap_router.get("/files/{file_id}/content")
async def get_file_content(
    file_id: str = FastAPIPath(..., description="The unique ID of the staged file"),
) -> FileResponse:
    """Retrieve the raw bytes of a staged file."""
    file_path = STAGING_ROOT / file_id / "attachment.bin"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in staging.")

    return FileResponse(file_path)


STAGING_ROOT: Final[Path] = Path(os.environ.get("VIGILANT_STAGING_DIR", "/var/lib/vigilant/staging"))
OPEN_WEBUI_UPLOADS_ROOT: Final[Path] = Path(
    os.environ.get("OPEN_WEBUI_UPLOADS_DIR", "/var/lib/open-webui/data/uploads")
)


_PCAP_MIME_HINTS: Final[frozenset[str]] = frozenset(
    {"application/vnd.tcpdump.pcap", "application/x-pcapng", "application/octet-stream"}
)
_PCAP_EXTENSIONS: Final[frozenset[str]] = frozenset({".pcap", ".pcapng", ".cap"})
_UUID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


def _looks_like_pcap(filename: str | None, mime_hint: str | None) -> bool:
    if filename is not None and Path(filename).suffix.lower() in _PCAP_EXTENSIONS:
        return True
    if mime_hint is not None:
        mime = mime_hint.split(";", 1)[0].strip().lower()
        return mime in _PCAP_MIME_HINTS
    return False


def _decode_data_uri(data_uri: str) -> bytes | None:
    """Extract raw bytes from a `data:<mime>;base64,<...>` URI. Returns
    None if the URI is not base64-encoded data we can decode."""
    if not data_uri.startswith("data:") or ";base64," not in data_uri:
        return None
    _, encoded = data_uri.split(";base64,", 1)
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None


def _stage_bytes(data: bytes) -> str:
    """Write raw bytes to a fresh staging entry and return its ref id."""
    ref = uuid.uuid4().hex
    entry_dir = STAGING_ROOT / ref
    entry_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    (entry_dir / "attachment.bin").write_bytes(data)
    return ref


def _read_open_webui_file(file_id: str) -> tuple[str, bytes] | None:
    """Resolve an Open WebUI file ID from the shared uploads directory."""
    try:
        uuid.UUID(file_id)
    except (ValueError, AttributeError):
        return None

    matches = list(OPEN_WEBUI_UPLOADS_ROOT.glob(f"{file_id}_*"))
    if len(matches) != 1 or not matches[0].is_file():
        return None

    filename = matches[0].name.removeprefix(f"{file_id}_")
    return filename, matches[0].read_bytes()


def _stage_pcap_ids_in_text(text: str) -> str:
    """Replace PCAP file IDs embedded in Open WebUI's text payload."""
    staged = text
    for file_id in dict.fromkeys(_UUID_PATTERN.findall(text)):
        resolved = _read_open_webui_file(file_id)
        if resolved is None:
            continue
        filename, data = resolved
        if not _looks_like_pcap(filename, None):
            continue
        ref = _stage_bytes(data)
        staged += f"\n[pcap attachment staged: pcap_ref={ref}, filename={filename}]"
    return staged


def stage_pcap_attachments(messages: list[ChatMessage]) -> list[dict[str, object]]:
    """
    Scan messages for pcap-like attachments, write their raw bytes to the
    staging directory, and replace those content parts with a short text
    note the LLM can read and act on directly (no transcription needed).

    Returns plain dicts ready to forward to Hermes (mirrors the previous
    `message.model_dump()` shape used by the router).
    """
    result: list[dict[str, object]] = []

    for message in messages:
        if isinstance(message.content, str):
            result.append({"role": message.role, "content": _stage_pcap_ids_in_text(message.content)})
            continue

        new_parts: list[object] = []
        for part in message.content:
            if isinstance(part, FilePart):
                filename = part.file.filename
                data: bytes | None = None
                filename = part.file.filename
                if part.file.file_data is not None:
                    data = _decode_data_uri(part.file.file_data)
                elif part.file.file_id is not None:
                    resolved = _read_open_webui_file(part.file.file_id)
                    if resolved is not None:
                        filename, data = resolved
                if data is not None and _looks_like_pcap(filename, None):
                    ref = _stage_bytes(data)
                    new_parts.append(
                        {
                            "type": "text",
                            "text": f"[pcap attachment staged: pcap_ref={ref}, filename={filename or 'unknown'}]",
                        }
                    )
                    continue
                new_parts.append(part.model_dump())
            elif isinstance(part, ImagePart):
                data = _decode_data_uri(part.image_url.url)
                mime_hint = part.image_url.url.split(";", 1)[0].removeprefix("data:") if data else None
                if data is not None and _looks_like_pcap(None, mime_hint):
                    ref = _stage_bytes(data)
                    new_parts.append({"type": "text", "text": f"[pcap attachment staged: pcap_ref={ref}]"})
                    continue
                new_parts.append(part.model_dump())
            elif isinstance(part, TextPart):
                new_parts.append(part.model_dump())

        result.append({"role": message.role, "content": new_parts})

    return result

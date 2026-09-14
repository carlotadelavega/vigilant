"""
Ingestion tool for VIGILANT: resolves a `pcap_ref` (assigned by
vigilant-backend when it staged an attachment from the incoming chat
request) against the shared staging directory, validates the content,
and materializes it in the quarantine directory for analysis.

The LLM never handles raw pcap bytes at any point: vigilant-backend writes
them to STAGING_ROOT/<ref>/attachment.bin before Hermes ever sees the
message (see vigilant.api.v1.pcap_staging), and this tool is the only
thing that reads them back out.

Requires: pip install scapy --break-system-packages
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Final, TypedDict

from scapy.utils import PcapReader

STAGING_ROOT: Final[Path] = Path(os.environ.get("VIGILANT_STAGING_DIR", "/var/lib/vigilant/staging"))
QUARANTINE_ROOT: Final[Path] = Path(os.environ.get("VIGILANT_QUARANTINE_DIR", "/var/lib/vigilant/quarantine"))
MAX_PCAP_BYTES: Final[int] = 500 * 1024 * 1024

_PCAP_MAGICS: Final[frozenset[bytes]] = frozenset(
    {
        b"\xa1\xb2\xc3\xd4",
        b"\xd4\xc3\xb2\xa1",
        b"\xa1\xb2\x3c\x4d",
        b"\x4d\x3c\xb2\xa1",
    }
)
_PCAPNG_MAGIC: Final[bytes] = b"\x0a\x0d\x0d\x0a"


class IngestError(TypedDict):
    ok: bool
    reason: str


class IngestResult(TypedDict):
    ok: bool
    quarantined_path: str
    size_bytes: int
    packet_count_sampled: int


def _validate_magic(data: bytes) -> bool:
    if len(data) < 4:
        return False
    head = data[:4]
    return head in _PCAP_MAGICS or head == _PCAPNG_MAGIC


def _is_safe_ref(pcap_ref: str) -> bool:
    """Reject anything that isn't a plain uuid4 hex token — no path
    separators, no traversal, no surprises from a ref an LLM echoed back."""
    try:
        uuid.UUID(hex=pcap_ref)
    except ValueError:
        return False
    return True


async def ingest_pcap_ref(pcap_ref: str) -> IngestResult | IngestError:
    """
    Resolve a staged attachment by its `pcap_ref` and materialize a
    validated copy in the quarantine directory.

    pcap_ref: the short reference emitted by vigilant-backend when it
    staged the attachment (e.g. "pcap_ref=..." text the LLM read from the
    conversation and is passing through verbatim). This is never a
    filesystem path and never raw content.
    """
    if not _is_safe_ref(pcap_ref):
        return IngestError(ok=False, reason="invalid_ref")

    staged_path = STAGING_ROOT / pcap_ref / "attachment.bin"
    if not staged_path.is_file():
        return IngestError(ok=False, reason="ref_not_found")

    data = staged_path.read_bytes()
    shutil.rmtree(staged_path.parent, ignore_errors=True)

    if len(data) == 0:
        return IngestError(ok=False, reason="empty_content")
    if len(data) > MAX_PCAP_BYTES:
        return IngestError(ok=False, reason=f"exceeds_max_size:{MAX_PCAP_BYTES}")
    if not _validate_magic(data):
        return IngestError(ok=False, reason="invalid_magic_bytes")

    request_dir = QUARANTINE_ROOT / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    target_path = request_dir / "capture.pcap"
    target_path.write_bytes(data)
    target_path.chmod(0o600)

    packet_count_sampled = 0
    try:
        with PcapReader(str(target_path)) as reader:
            for _ in range(5):
                pkt = reader.read_packet()
                if pkt is None:
                    break
                packet_count_sampled += 1
    except Exception as exc:  # noqa: BLE001
        target_path.unlink(missing_ok=True)
        request_dir.rmdir()
        return IngestError(ok=False, reason=f"structurally_invalid: {exc}")

    return IngestResult(
        ok=True,
        quarantined_path=str(target_path),
        size_bytes=len(data),
        packet_count_sampled=packet_count_sampled,
    )

"""
C32 — Evidence download MIME type, extension, and safe filename helpers.

Authoritative mapping for serving evidence files. Prefer stored path suffix,
then file-signature sniffing, then a conservative octet-stream fallback.
Never maps SNAPSHOT/CLIP/DOCUMENT labels to extensions directly.
"""

from __future__ import annotations

import re
from pathlib import Path

# MIME ↔ extension (supported portal evidence formats only).
MIME_BY_EXTENSION: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}

EXTENSION_BY_MIME: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/x-msvideo": ".avi",
    "video/quicktime": ".mov",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}

_UUID_PREFIX = re.compile(
    r"^(?P<uuid>[0-9a-f]{32})_(?P<rest>.+)$", re.IGNORECASE
)
_DET_PREFIX = re.compile(
    r"^det\d+_(?P<uuid>[0-9a-f]{32})(?P<ext>\.[A-Za-z0-9]+)?$",
    re.IGNORECASE,
)
_UNSAFE_NAME = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]+')


def extension_for_mime(mime: str | None) -> str | None:
    if not mime:
        return None
    return EXTENSION_BY_MIME.get(mime.strip().lower().split(";")[0].strip())


def mime_for_extension(suffix: str | None) -> str | None:
    if not suffix:
        return None
    s = suffix if suffix.startswith(".") else f".{suffix}"
    return MIME_BY_EXTENSION.get(s.lower())


def sniff_mime_from_bytes(head: bytes) -> str | None:
    """Trusted server-side magic-byte detection for common evidence formats."""
    if len(head) < 12:
        # Still enough for several signatures
        pass
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"BM"):
        return "image/bmp"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    # Plain text heuristic: printable / whitespace only in first chunk
    if head and all(
        (32 <= b <= 126) or b in (9, 10, 13) for b in head[: min(64, len(head))]
    ):
        return "text/plain"
    return None


def sniff_mime_from_path(path: Path) -> str | None:
    try:
        with path.open("rb") as fh:
            head = fh.read(64)
    except OSError:
        return None
    return sniff_mime_from_bytes(head)


def resolve_evidence_media_type(path: Path) -> str:
    """
    Resolve Content-Type for an evidence file on disk.

    Priority: path suffix → magic bytes → application/octet-stream.
    """
    by_ext = mime_for_extension(path.suffix.lower())
    if by_ext:
        return by_ext
    sniffed = sniff_mime_from_path(path)
    if sniffed:
        return sniffed
    return "application/octet-stream"


def sanitize_download_basename(name: str, *, max_len: int = 180) -> str:
    """Basename only; strip path segments and unsafe characters."""
    base = Path(str(name or "").replace("\\", "/")).name.strip()
    base = _UNSAFE_NAME.sub("_", base).strip(" .")
    if not base or base in {".", ".."}:
        return ""
    if len(base) > max_len:
        stem = Path(base).stem[: max_len - 12]
        ext = Path(base).suffix[:12]
        base = f"{stem}{ext}" if ext else stem
    return base


def preferred_download_filename(
    *,
    evidence_id: int,
    stored_path: Path,
    media_type: str,
) -> str:
    """
    Build a safe Content-Disposition filename.

    Prefer the human original name when stored as ``{uuid}_{original}``.
    Detection-auto names (``detN_{uuid}.ext``) become ``evidence-{id}.ext``.
    Always ensure a correct extension for the resolved media type.
    """
    raw_name = stored_path.name
    candidate = ""

    m = _UUID_PREFIX.match(raw_name)
    if m:
        candidate = sanitize_download_basename(m.group("rest"))
    else:
        det = _DET_PREFIX.match(raw_name)
        if det:
            candidate = ""
        else:
            candidate = sanitize_download_basename(raw_name)

    ext = extension_for_mime(media_type)
    if not ext:
        # Keep genuine unknown binaries from inventing a fake type.
        path_ext = stored_path.suffix.lower()
        ext = path_ext if path_ext and path_ext != ".bin" else ".bin"

    if candidate:
        # Force extension to match resolved MIME (e.g. uploaded .jpeg → .jpg).
        stem = Path(candidate).stem or f"evidence-{evidence_id}"
        # Avoid double extensions when stem already ends oddly
        return f"{sanitize_download_basename(stem)}{ext}"

    return f"evidence-{evidence_id}{ext}"

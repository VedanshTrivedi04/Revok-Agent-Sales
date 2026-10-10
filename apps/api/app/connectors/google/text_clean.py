"""Text cleaning and normalization for Gmail messages.

Features:
- Prefers text/plain over text/html
- Converts HTML to clean plain text
- Strips quoted replies (e.g., 'On ... wrote:', '-----Original Message-----', lines starting with '>')
- Strips signatures (e.g., standard '-- ', signoffs 'Best regards,', 'Sent from my iPhone')
- Trims text to 20 KB (20,480 characters)
"""

from __future__ import annotations

import base64
import html
import re
from typing import Any

MAX_BODY_CHARS = 20480

# Quoted reply headers
RE_QUOTE_HEADERS = [
    re.compile(r"(?im)^On\s+.+?\s+(?:wrote|wrote\s*:)\s*$", re.MULTILINE),
    re.compile(r"(?im)^On\s+.+?at\s+.+?wrote:\s*$", re.MULTILINE),
    re.compile(r"(?im)^-----\s*Original Message\s*-----.*$", re.MULTILINE | re.DOTALL),
    re.compile(r"(?im)^_{10,}.*$", re.MULTILINE | re.DOTALL),
    re.compile(r"(?im)^From:\s*.+?\n(?:Sent|Date):\s*.+?\n(?:To|Subject):.*$", re.MULTILINE | re.DOTALL),
]

# Signature markers
RE_SIG_DELIMITER = re.compile(r"(?m)^--\s*$", re.MULTILINE)
RE_SIGNOFFS = re.compile(
    r"(?im)^(?:Best regards|Warm regards|Kind regards|Regards|Thanks and regards|Thanks|Thank you|Sincerely|Cheers|Yours truly)[,\s]*\n.*$",
    re.MULTILINE | re.DOTALL,
)
RE_MOBILE_SIGS = re.compile(
    r"(?im)^(?:Sent from my (?:iPhone|iPad|Galaxy|phone|Android|device)|Get Outlook for (?:iOS|Android)).*$",
    re.MULTILINE | re.DOTALL,
)


def html_to_text(html_content: str) -> str:
    """Convert HTML string to clean plain text."""
    if not html_content:
        return ""

    # Remove script and style elements
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", "", html_content)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", "", text)

    # Convert block elements and breaks to newlines
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"(?i)<(?:p|div|tr|li|h[1-6])[^>]*>", "\n", text)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Unescape HTML entities
    text = html.unescape(text)

    # Normalize whitespace
    lines = [line.strip() for line in text.split("\n")]
    result: list[str] = []
    consecutive_empty = 0
    for line in lines:
        if not line:
            consecutive_empty += 1
            if consecutive_empty <= 1:
                result.append("")
        else:
            consecutive_empty = 0
            result.append(line)

    return "\n".join(result).strip()


def strip_quoted_replies(text: str) -> str:
    """Strip quoted reply text from an email body."""
    if not text:
        return ""

    # 1. Truncate at standard quote headers
    earliest_idx = len(text)
    for pat in RE_QUOTE_HEADERS:
        m = pat.search(text)
        if m and m.start() < earliest_idx:
            earliest_idx = m.start()

    if earliest_idx < len(text):
        text = text[:earliest_idx].rstrip()

    # 2. Strip lines starting with '>'
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        if line.strip().startswith(">"):
            continue
        clean_lines.append(line)

    return "\n".join(clean_lines).rstrip()


def strip_signatures(text: str) -> str:
    """Strip signatures and signoff blocks from an email body."""
    if not text:
        return ""

    # 1. Split at '-- ' delimiter
    m_delim = RE_SIG_DELIMITER.search(text)
    if m_delim:
        text = text[: m_delim.start()].rstrip()

    # 2. Split at mobile signatures
    m_mob = RE_MOBILE_SIGS.search(text)
    if m_mob:
        text = text[: m_mob.start()].rstrip()

    # 3. Check common signoffs if they appear near the end of the text
    m_sign = RE_SIGNOFFS.search(text)
    if m_sign:
        # Only treat as signature if in last 60% of message
        if m_sign.start() >= len(text) * 0.4:
            text = text[: m_sign.start()].rstrip()

    return text.strip()


def _decode_part_data(data_str: str) -> str:
    """Decode base64url data safely."""
    try:
        # Pad base64 string
        padded = data_str + "=" * (-len(data_str) % 4)
        raw_bytes = base64.urlsafe_b64decode(padded)
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_plain_text(payload: dict[str, Any]) -> str:
    """Extract plain text from Gmail message payload, preferring text/plain."""
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def _walk_parts(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")

        if data:
            decoded = _decode_part_data(data)
            if mime == "text/plain":
                plain_parts.append(decoded)
            elif mime == "text/html":
                html_parts.append(decoded)

        subparts = part.get("parts") or []
        for sp in subparts:
            _walk_parts(sp)

    _walk_parts(payload)

    if plain_parts:
        return "\n\n".join(plain_parts)
    elif html_parts:
        return html_to_text("\n\n".join(html_parts))

    # Fallback to snippet if present
    return str(payload.get("snippet") or "")


def clean_email_body(content: dict[str, Any] | str) -> str:
    """Extract and clean email text from payload dict or raw string.
    
    Prefers text/plain, converts HTML to text, strips quoted replies and signatures,
    and trims to 20 KB.
    """
    if isinstance(content, dict):
        raw_text = extract_plain_text(content)
    else:
        raw_text = str(content)

    # If raw_text looks like raw HTML, convert it
    if "<html" in raw_text.lower() or "<div" in raw_text.lower() or "<p>" in raw_text.lower():
        raw_text = html_to_text(raw_text)

    # 1. Strip quoted replies
    unquoted = strip_quoted_replies(raw_text)

    # 2. Strip signatures
    cleaned = strip_signatures(unquoted)

    # 3. Trim to 20 KB
    if len(cleaned) > MAX_BODY_CHARS:
        cleaned = cleaned[:MAX_BODY_CHARS]

    return cleaned.strip()

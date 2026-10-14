"""Step 1: read the exported .txt file and split it into messages.

WhatsApp's "Export chat" produces slightly different text depending on the
phone and its language settings. The three layouts handled here:

    Android:  17/09/2026 14:32 - Ana Souza: quero 2
    iPhone:   [17/09/2026, 14:32:10] Ana Souza: quero 2
    12-hour:  9/17/26, 2:32 PM - Ana Souza: quero 2

A message can span several lines. Any line that does not start with a
date belongs to the message above it.
"""

import re
from dataclasses import dataclass
from datetime import datetime

# One pattern covering all three layouts. Named groups make it readable.
LINE_START = re.compile(
    r"^\[?"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)"
    r"(?:\s*(?P<ampm>[AaPp])\.?\s?[Mm]\.?)?"
    r"\]?\s*(?:-\s*)?"
    r"(?P<rest>.*)$"
)

# Text WhatsApp inserts where a photo/video was (Portuguese and English).
MEDIA_MARKERS = re.compile(
    r"<m[ií]dia oculta>|<media omitted>|<arquivo de m[ií]dia oculto>"
    r"|<anexado:[^>]*>|<attached:[^>]*>"
    r"|\S+\.(?:jpg|jpeg|png|webp|mp4|opus)\s*\((?:arquivo anexado|file attached)\)"
    r"|(?:imagem|v[ií]deo|figurinha) ocultad[ao]|(?:image|video|sticker|gif) omitted",
    re.IGNORECASE,
)

# Invisible direction marks and odd spaces WhatsApp sprinkles into exports.
INVISIBLE = re.compile("[\u200e\u200f\u202a-\u202e\ufeff]")


@dataclass
class Message:
    timestamp: datetime
    sender: str
    text: str            # media markers already removed
    has_media: bool


def clean(line: str) -> str:
    line = INVISIBLE.sub("", line)
    return line.replace("\u202f", " ").replace("\u00a0", " ").rstrip("\n")


def parse_timestamp(date: str, time: str, ampm: str | None, day_first: bool) -> datetime:
    a, b, year = (int(x) for x in date.split("/"))
    day, month = (a, b) if day_first else (b, a)
    if year < 100:
        year += 2000
    pieces = [int(x) for x in time.split(":")]
    hour, minute = pieces[0], pieces[1]
    second = pieces[2] if len(pieces) > 2 else 0
    if ampm:
        is_pm = ampm.lower() == "p"
        if is_pm and hour != 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
    return datetime(year, month, day, hour, minute, second)


def parse_chat(lines, day_first: bool = True) -> list[Message]:
    """Turn raw lines into Message objects. System notices are dropped."""
    messages: list[Message] = []
    current: Message | None = None

    for raw in lines:
        line = clean(raw)
        match = LINE_START.match(line)

        if match:
            try:
                stamp = parse_timestamp(match["date"], match["time"],
                                        match["ampm"], day_first)
            except ValueError:
                match = None            # looked like a date but was not one

        if not match:
            if current is not None:     # continuation of a multi-line message
                current.text += "\n" + line
            continue

        rest = match["rest"]
        if ": " not in rest and not rest.endswith(":"):
            current = None              # system notice ("Ana joined the group")
            continue

        sender, _, text = rest.partition(":")
        current = Message(stamp, sender.strip(), text.strip(), has_media=False)
        messages.append(current)

    for msg in messages:                # finalize: detect and strip media markers
        if MEDIA_MARKERS.search(msg.text):
            msg.has_media = True
            msg.text = MEDIA_MARKERS.sub("", msg.text)
        msg.text = msg.text.strip()
    return messages


def parse_chat_file(path: str, day_first: bool = True) -> list[Message]:
    with open(path, encoding="utf-8-sig") as f:
        return parse_chat(f, day_first=day_first)

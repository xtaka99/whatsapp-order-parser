"""Step 2: work out which messages are product posts and which are orders.

The flow in a sales group:
    1. The seller posts a photo with a caption (name, price, maybe a #code).
    2. Customers answer "quero", "quero 2", "2 pra mim", "reserva 1 #A12"...
    3. Sometimes a customer backs out: "desisto", "cancela o meu".

IMPORTANT LIMIT: an exported chat does not record which message a customer
was replying to. So an order is matched to a product by:
    a) a product code written in the order ("quero 2 #A12"), else
    b) the most recent product the seller posted.
When rule (b) is used and several products were posted close together, the
order is flagged for human review instead of being trusted blindly.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .chat_parser import Message

PRICE = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)")
CODE = re.compile(r"#\s?([A-Za-z]{0,3}\d{1,4})\b")

# Checked on text that is already lowercase with accents removed.
CANCEL = re.compile(r"\b(nao quero|nao vou querer|desisto|desisti|cancela\w*|pode tirar)\b")
WANT = re.compile(
    r"\b(quero|qro|kero|vou querer|vou levar|pra mim|para mim|p mim"
    r"|reserva\w*|separa\w*|fico com)\b"
)
NUMBER_WORDS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
}
MAX_QUANTITY = 50
CAPTION_GAP = timedelta(minutes=3)      # photo first, caption right after


@dataclass
class Product:
    number: int                 # 1, 2, 3... in posting order
    posted_at: datetime
    name: str
    price: float | None = None
    code: str | None = None

    @property
    def label(self) -> str:
        return f"#{self.code} {self.name}" if self.code else self.name


@dataclass
class Order:
    timestamp: datetime
    customer: str
    product: Product
    quantity: int
    original_text: str
    review_reason: str = ""     # empty = confident match

    @property
    def needs_review(self) -> bool:
        return bool(self.review_reason)


@dataclass
class Result:
    products: list[Product] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    cancelled: list[Order] = field(default_factory=list)
    unmatched: list[Message] = field(default_factory=list)   # "quero" with no product


def normalize(text: str) -> str:
    """Lowercase and strip accents: 'Não QUERO' -> 'nao quero'."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def parse_price(text: str) -> float | None:
    m = PRICE.search(text)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def parse_code(text: str) -> str | None:
    m = CODE.search(text)
    return m.group(1).upper() if m else None


def parse_quantity(normalized_text: str) -> int:
    """'quero 2' -> 2, 'quero duas' -> 2, 'quero' -> 1. Codes/prices ignored."""
    text = CODE.sub(" ", normalized_text)
    text = re.sub(r"r\$\s*[\d.,]+", " ", text)
    m = re.search(r"\b(\d{1,2})\s*(?:x|un|unid\w*)?\b", text)
    if m and 1 <= int(m.group(1)) <= MAX_QUANTITY:
        return int(m.group(1))
    for word in text.split():
        if word in NUMBER_WORDS and word not in ("um", "uma"):
            return NUMBER_WORDS[word]
    return 1


def product_name_from(text: str) -> str:
    """First meaningful caption line, without the price or code."""
    for line in text.splitlines():
        line = PRICE.sub("", CODE.sub("", line)).strip(" -–|:*_")
        if len(line) >= 3:
            return line[:80]
    return ""


def detect(messages: list[Message], sellers: list[str],
           review_window_minutes: int = 3) -> Result:
    seller_names = {normalize(s) for s in sellers}
    window = timedelta(minutes=review_window_minutes)
    result = Result()
    awaiting_caption: Product | None = None

    for msg in messages:
        from_seller = normalize(msg.sender) in seller_names

        # ---------- seller: product posts ----------
        if from_seller:
            is_post = msg.has_media or parse_price(msg.text) is not None
            caption_for_photo = (
                awaiting_caption is not None and not msg.has_media and msg.text
                and msg.timestamp - awaiting_caption.posted_at <= CAPTION_GAP
            )
            if caption_for_photo:
                awaiting_caption.name = product_name_from(msg.text) or awaiting_caption.name
                awaiting_caption.price = parse_price(msg.text)
                awaiting_caption.code = parse_code(msg.text)
                awaiting_caption = None
            elif is_post:
                product = Product(
                    number=len(result.products) + 1,
                    posted_at=msg.timestamp,
                    name=product_name_from(msg.text) or f"Photo {msg.timestamp:%H:%M}",
                    price=parse_price(msg.text),
                    code=parse_code(msg.text),
                )
                result.products.append(product)
                awaiting_caption = product if not msg.text else None
            continue                      # sellers never place orders

        # ---------- customer messages ----------
        text = normalize(msg.text)
        code = parse_code(msg.text)
        by_code = next((p for p in reversed(result.products) if code and p.code == code), None)

        if CANCEL.search(text):
            mine = [o for o in result.orders if o.customer == msg.sender
                    and (by_code is None or o.product is by_code)]
            if mine:
                result.orders.remove(mine[-1])
                result.cancelled.append(mine[-1])
            continue

        if not (WANT.search(text) or (code and by_code)):
            continue                      # normal chatter: "que lindo!", "tem azul?"

        if not result.products:
            result.unmatched.append(msg)
            continue

        reason = ""
        if by_code:
            product = by_code
        else:
            product = result.products[-1]
            if code:
                reason = f"code #{code} not found; assumed latest product"
            else:
                recent = [p for p in result.products if msg.timestamp - p.posted_at <= window]
                if len(recent) > 1:
                    reason = f"{len(recent)} products posted within {review_window_minutes} min"

        result.orders.append(Order(msg.timestamp, msg.sender, product,
                                   parse_quantity(text), msg.text, reason))
    return result

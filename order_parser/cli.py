"""Command-line interface.

    python -m order_parser chat.txt --seller "Store Name" --out buy_list.xlsx
"""

import argparse
import sys
from datetime import datetime

from .chat_parser import parse_chat_file
from .detector import detect, normalize
from .report import print_summary, write_output


def parse_since(value: str) -> datetime:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("use DD/MM/YYYY or 'DD/MM/YYYY HH:MM'")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="order_parser",
        description="Build a buy list from an exported WhatsApp sales-group chat.")
    p.add_argument("chat_file", help="the .txt from WhatsApp > Export chat > Without media")
    p.add_argument("--seller", action="append", required=True,
                   help="name of the account posting products, exactly as it appears "
                        "in the export (repeat the flag for several sellers)")
    p.add_argument("--out", help="output file: .xlsx (one file) or .csv (three files)")
    p.add_argument("--since", type=parse_since,
                   help="ignore everything before this moment, e.g. '17/09/2026 14:00'")
    p.add_argument("--month-first", action="store_true",
                   help="dates in the export are MM/DD (US phones). Default is DD/MM")
    p.add_argument("--review-window", type=int, default=3,
                   help="minutes; orders are flagged when more than one product was "
                        "posted within this window (default 3)")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        messages = parse_chat_file(args.chat_file, day_first=not args.month_first)
    except FileNotFoundError:
        print(f"Error: file not found: {args.chat_file}", file=sys.stderr)
        return 1

    if not messages:
        print("Error: no messages recognized. Is this a WhatsApp export? "
              "If the phone uses US dates, try --month-first.", file=sys.stderr)
        return 1

    if args.since:
        messages = [m for m in messages if m.timestamp >= args.since]

    senders = {m.sender for m in messages}
    known = {normalize(s) for s in senders}
    missing = [s for s in args.seller if normalize(s) not in known]
    if missing:
        print(f"Warning: seller name(s) not found in the chat: {', '.join(missing)}",
              file=sys.stderr)
        print(f"Names in this chat: {', '.join(sorted(senders))}", file=sys.stderr)

    result = detect(messages, args.seller, args.review_window)
    print_summary(result)

    if args.out:
        for written in write_output(result, args.out):
            print(f"Saved: {written}")
    return 0

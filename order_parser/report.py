"""Step 3: summarize orders and write them to the terminal, CSV or Excel."""

import csv
from collections import defaultdict
from pathlib import Path

from .detector import Order, Product, Result


def buy_list(result: Result) -> list[dict]:
    """One row per product: how many to buy and for whom."""
    per_product: dict[int, list[Order]] = defaultdict(list)
    for order in result.orders:
        per_product[order.product.number].append(order)

    rows = []
    for product in result.products:
        orders = per_product.get(product.number, [])
        if not orders:
            continue
        per_customer: dict[str, int] = defaultdict(int)
        for o in orders:
            per_customer[o.customer] += o.quantity
        quantity = sum(per_customer.values())
        rows.append({
            "code": product.code or "",
            "product": product.name,
            "price_brl": product.price if product.price is not None else "",
            "quantity": quantity,
            "revenue_brl": round(product.price * quantity, 2) if product.price else "",
            "customers": ", ".join(f"{name} ({q})" for name, q in per_customer.items()),
            "to_review": sum(1 for o in orders if o.needs_review),
        })
    return rows


def by_customer(result: Result) -> list[dict]:
    """One row per customer: what they claimed and what they owe."""
    grouped: dict[str, list[Order]] = defaultdict(list)
    for order in result.orders:
        grouped[order.customer].append(order)

    rows = []
    for customer in sorted(grouped):
        orders = grouped[customer]
        priced = [o for o in orders if o.product.price is not None]
        rows.append({
            "customer": customer,
            "items": "; ".join(f"{o.quantity}x {o.product.label}" for o in orders),
            "units": sum(o.quantity for o in orders),
            "total_brl": round(sum(o.product.price * o.quantity for o in priced), 2),
            "has_unpriced_items": "yes" if len(priced) < len(orders) else "",
        })
    return rows


def all_orders(result: Result) -> list[dict]:
    """Every order line, so a human can audit the parser's decisions."""
    rows = []
    for status, orders in (("active", result.orders), ("cancelled", result.cancelled)):
        for o in orders:
            rows.append({
                "time": o.timestamp.strftime("%d/%m/%Y %H:%M"),
                "customer": o.customer,
                "product": o.product.label,
                "quantity": o.quantity,
                "status": status,
                "review": o.review_reason,
                "message": o.original_text.replace("\n", " "),
            })
    rows.sort(key=lambda r: r["time"])
    return rows


def print_summary(result: Result) -> None:
    rows = buy_list(result)
    print(f"\nProducts posted: {len(result.products)}   "
          f"Orders: {len(result.orders)}   Cancelled: {len(result.cancelled)}")
    print("\nBUY LIST")
    print("-" * 78)
    for r in rows:
        flag = f"  [review {r['to_review']}]" if r["to_review"] else ""
        code = f"#{r['code']} " if r["code"] else ""
        print(f"{r['quantity']:>3} x {code}{r['product'][:40]:<42}{flag}")
        print(f"      {r['customers']}")
    print("-" * 78)
    print(f"Total units to buy: {sum(r['quantity'] for r in rows)}")
    if result.unmatched:
        print(f"Orders before any product was posted: {len(result.unmatched)} (see output file)")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:   # -sig: Excel reads accents
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_output(result: Result, out_path: str) -> list[str]:
    """Writes .xlsx (three sheets) or .csv (three files). Returns files written."""
    path = Path(out_path)
    sheets = {
        "Buy list": buy_list(result),
        "By customer": by_customer(result),
        "All orders": all_orders(result),
    }

    if path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            print("openpyxl is not installed; writing CSV files instead.")
            path = path.with_suffix(".csv")
        else:
            book = Workbook()
            book.remove(book.active)
            for title, rows in sheets.items():
                sheet = book.create_sheet(title)
                if not rows:
                    continue
                sheet.append(list(rows[0]))
                for cell in sheet[1]:
                    cell.font = Font(bold=True)
                for row in rows:
                    sheet.append(list(row.values()))
                    if row.get("review") or row.get("to_review"):
                        for cell in sheet[sheet.max_row]:
                            cell.fill = PatternFill("solid", start_color="FFF2CC")
                for column in sheet.columns:
                    width = max(len(str(c.value or "")) for c in column)
                    sheet.column_dimensions[column[0].column_letter].width = min(width + 2, 60)
                sheet.freeze_panes = "A2"
            book.save(path)
            return [str(path)]

    written = []
    for title, rows in sheets.items():
        target = path.with_name(f"{path.stem}_{title.lower().replace(' ', '_')}.csv")
        _write_csv(target, rows)
        written.append(str(target))
    return written

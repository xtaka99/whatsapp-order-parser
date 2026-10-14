# whatsapp-order-parser

![tests](https://github.com/xtaka99/whatsapp-order-parser/actions/workflows/tests.yml/badge.svg)

Turns an exported WhatsApp sales-group chat into a **buy list**: what to buy,
how many, and for which customer.

## The problem

My family's import business sells through a WhatsApp group. We post a product
photo, customers answer *"quero"* ("I want it"), *"quero 2"*, *"3 pra mim"*.
Seeing other people claim an item is what drives sales, so orders have to stay
in the group. The cost is that someone then scrolls through hundreds of
messages and copies every order by hand into a shopping list before going back
to the store. It is slow and orders get missed.

## Why it reads an export instead of being a live bot

I looked into a bot first. WhatsApp's official Groups API is restricted to
verified Official Business Accounts and caps groups at 8 participants, and
unofficial automation libraries break WhatsApp's terms of service and risk
getting the business number banned. WhatsApp's own **Export chat** feature is
fully allowed, takes ten seconds, and gives this tool everything it needs.

## What it does

- Parses Android, iPhone and US 12-hour export layouts, including multi-line captions and media markers
- Recognizes **product posts** from the seller: name, `R$` price, optional `#code`
- Recognizes **orders** in informal Brazilian Portuguese: `quero`, `qro`, `quero duas`, `3 pra mim`, `reserva 1 #A12`
- Handles **cancellations**: `desisto`, `não quero mais`, `cancela`
- Ignores chatter (`que linda!`, `qual o prazo?`)
- **Flags uncertain matches for review** instead of guessing silently
- Outputs an Excel file with three sheets: *Buy list*, *By customer* (with totals owed), *All orders* (audit trail, uncertain rows highlighted)

## Example

```
$ python -m order_parser examples/sample_chat.txt --seller "Magic Imports" --out buy_list.xlsx

Products posted: 4   Orders: 10   Cancelled: 1

BUY LIST
------------------------------------------------------------------------------
  3 x #A1 Caneca Minnie Halloween 2026
      Juliana Prado (2), Renata Lima (1)
  3 x #A2 Pelúcia Stitch 30cm
      Carla Mendes (2), Juliana Prado (1)
  4 x #A3 Orelha Minnie lantejoula rosa               [review 1]
      Beatriz Rocha (1), Patrícia Alves (3)
  7 x #B7 Kit Kat Matcha Japão (pacote 12un)          [review 1]
      Fernanda Dias (2), Beatriz Rocha (1), Patrícia Alves (3), Renata Lima (1)
------------------------------------------------------------------------------
Total units to buy: 17
Saved: buy_list.xlsx
```

The sample chat is fictional. All names are made up.

## Setup

Requires Python 3.10+.

```bash
git clone https://github.com/xtaka99/whatsapp-order-parser.git
cd whatsapp-order-parser
pip install -r requirements.txt
python -m order_parser examples/sample_chat.txt --seller "Magic Imports" --out buy_list.xlsx
```

### Using it on a real group

1. In WhatsApp, open the group > menu > **More > Export chat > Without media**, and send the `.txt` to yourself.
2. Save it in a `chats/` folder inside this project (that folder is git-ignored).
3. Run:

```bash
python -m order_parser chats/group.txt --seller "Your Store Name" \
       --since "17/09/2026 14:00" --out buy_list.xlsx
```

| Option | Purpose |
|---|---|
| `--seller` | Name of the account posting products, as shown in the export. Repeat for several sellers |
| `--since` | Only process messages after this moment (the latest sales round) |
| `--month-first` | The phone exports US-style `MM/DD` dates |
| `--review-window` | Minutes used to decide when an order is ambiguous (default 3) |

## How matching works, and its limit

An exported chat **does not record which message a customer replied to**. So
each order is matched like this:

1. If the order includes a product code (`quero 2 #A2`), use that product.
2. Otherwise, use the most recent product the seller posted.
3. If rule 2 was used and more than one product was posted within the review window, the order is **flagged** so a person checks it.

Putting a `#code` in each caption and asking customers to repeat it makes
matching exact. Without codes the tool still works, and it is honest about
which rows it is unsure of.

## How the code is organized

| File | Job |
|---|---|
| `order_parser/chat_parser.py` | Regex-based parsing of the export into `Message` objects |
| `order_parser/detector.py` | Product detection, order intent, quantities, cancellations, matching rules |
| `order_parser/report.py` | Aggregation and Excel/CSV output with `openpyxl` |
| `order_parser/cli.py` | `argparse` interface and helpful warnings (for example a mistyped seller name) |
| `tests/` | 41 pytest tests, including an end-to-end run over the sample chat |

## Privacy

Real exports contain customer names, phone numbers and purchases. The
`.gitignore` blocks `chats/` and every `.txt`, `.xlsx` and `.csv` except the
fictional sample, so customer data cannot be committed by accident.

## What I learned

- Regular expressions with named groups for messy, real-world text
- Unicode normalization to match Portuguese text with or without accents
- Designing for uncertainty: flagging low-confidence results instead of hiding them
- Generating formatted Excel reports with `openpyxl`
- Parametrized tests in pytest

## Known limits / next steps

- A number unrelated to quantity in an order message (`quero, pago dia 15`) is read as a quantity. The *All orders* sheet shows the original message for auditing
- Next: a small web page to upload the export and download the Excel, so non-technical family members can use it

## License

MIT

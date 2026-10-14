from datetime import datetime, timedelta

import pytest

from order_parser.chat_parser import Message
from order_parser.detector import (detect, normalize, parse_code, parse_price,
                                   parse_quantity)

START = datetime(2026, 9, 17, 14, 0)
SELLER = "Loja"


def msg(minute, sender, text, media=False):
    return Message(START + timedelta(minutes=minute), sender, text, media)


def post(minute, caption):
    return msg(minute, SELLER, caption, media=True)


@pytest.mark.parametrize("text,expected", [
    ("R$ 189,90", 189.90), ("R$1.249,00", 1249.00), ("por R$ 50", 50.0), ("sem preço", None),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("quero", 1), ("quero 2", 2), ("Quero 2!!", 2), ("3 pra mim", 3),
    ("quero duas", 2), ("quero tres", 3), ("entao quero uma", 1),
    ("quero 2 #a12", 2),            # the code's digits are not a quantity
    ("quero #a12", 1),
    ("quero a de r$ 249,00", 1),    # the price is not a quantity
    ("quero 2x", 2),
])
def test_parse_quantity(text, expected):
    assert parse_quantity(text) == expected


def test_normalize_and_code():
    assert normalize("Não QUERO três") == "nao quero tres"
    assert parse_code("quero 2 #a12") == "A12"
    assert parse_code("quero 2") is None


def test_simple_order_goes_to_latest_product():
    r = detect([post(0, "Caneca Minnie R$ 100,00"), msg(1, "Ana", "quero 2")], [SELLER])
    assert len(r.orders) == 1
    order = r.orders[0]
    assert (order.customer, order.quantity, order.product.name) == ("Ana", 2, "Caneca Minnie")
    assert order.product.price == 100.0
    assert not order.needs_review


def test_code_beats_recency():
    r = detect([post(0, "Caneca #A1 R$ 10,00"), post(10, "Stitch #A2 R$ 20,00"),
                msg(11, "Ana", "quero 1 #A1")], [SELLER])
    assert r.orders[0].product.code == "A1"
    assert not r.orders[0].needs_review


def test_two_products_close_together_flags_review():
    r = detect([post(0, "Caneca #A1"), post(1, "Stitch #A2"), msg(2, "Ana", "quero")], [SELLER])
    assert r.orders[0].product.code == "A2"
    assert r.orders[0].needs_review


def test_unknown_code_is_flagged_not_dropped():
    r = detect([post(0, "Caneca #A1"), msg(1, "Ana", "quero #Z9")], [SELLER])
    assert r.orders[0].needs_review and "Z9" in r.orders[0].review_reason


def test_photo_then_separate_caption():
    r = detect([msg(0, SELLER, "", media=True),
                msg(1, SELLER, "Pelúcia Stitch #A2 - R$ 249,00"),
                msg(2, "Ana", "quero")], [SELLER])
    assert len(r.products) == 1
    assert r.products[0].name == "Pelúcia Stitch"
    assert r.products[0].price == 249.0 and r.products[0].code == "A2"


def test_cancellation_removes_the_order():
    r = detect([post(0, "Caneca #A1"), msg(1, "Ana", "quero 2"), msg(2, "Bia", "quero"),
                msg(3, "Ana", "desisto, desculpa")], [SELLER])
    assert [o.customer for o in r.orders] == ["Bia"]
    assert [o.customer for o in r.cancelled] == ["Ana"]


def test_nao_quero_is_a_cancellation_not_an_order():
    r = detect([post(0, "Caneca #A1"), msg(1, "Ana", "quero"),
                msg(2, "Ana", "não quero mais")], [SELLER])
    assert r.orders == [] and len(r.cancelled) == 1


def test_chatter_and_seller_messages_are_ignored():
    r = detect([post(0, "Caneca #A1"), msg(1, "Ana", "que linda! tem azul?"),
                msg(2, SELLER, "quem quero reservar avisa"),
                msg(3, "Bia", "qual o prazo?")], [SELLER])
    assert r.orders == []


def test_order_before_any_product_is_unmatched():
    r = detect([msg(0, "Ana", "quero")], [SELLER])
    assert r.orders == [] and len(r.unmatched) == 1


def test_seller_name_match_ignores_case_and_accents():
    r = detect([msg(0, "LOJÁ", "Caneca R$ 10,00", media=True), msg(1, "Ana", "quero")], ["loja"])
    assert len(r.products) == 1 and len(r.orders) == 1

from datetime import datetime

from order_parser.chat_parser import parse_chat


def test_android_layout():
    msgs = parse_chat(["17/09/2026 14:32 - Ana Souza: quero 2"])
    assert msgs[0].sender == "Ana Souza"
    assert msgs[0].text == "quero 2"
    assert msgs[0].timestamp == datetime(2026, 9, 17, 14, 32)


def test_iphone_layout_with_brackets_and_seconds():
    msgs = parse_chat(["[17/09/2026, 14:32:10] Ana Souza: quero 2"])
    assert msgs[0].timestamp == datetime(2026, 9, 17, 14, 32, 10)
    assert msgs[0].text == "quero 2"


def test_us_12_hour_layout():
    msgs = parse_chat(["9/17/26, 2:32\u202fPM - Ana: quero", "9/17/26, 12:05 AM - Ana: oi"],
                      day_first=False)
    assert msgs[0].timestamp == datetime(2026, 9, 17, 14, 32)
    assert msgs[1].timestamp == datetime(2026, 9, 17, 0, 5)      # 12 AM is midnight


def test_multiline_message_is_joined():
    msgs = parse_chat([
        "17/09/2026 14:02 - Loja: Caneca Minnie",
        "R$ 189,90",
        "Poucas unidades!",
        "17/09/2026 14:03 - Ana: quero",
    ])
    assert len(msgs) == 2
    assert msgs[0].text == "Caneca Minnie\nR$ 189,90\nPoucas unidades!"


def test_system_notices_are_dropped():
    msgs = parse_chat([
        "17/09/2026 13:55 - As mensagens são protegidas com criptografia.",
        "17/09/2026 13:56 - Ana Souza entrou usando o link de convite",
        "17/09/2026 14:03 - Ana Souza: quero",
    ])
    assert [m.sender for m in msgs] == ["Ana Souza"]


def test_media_markers_are_detected_and_removed():
    msgs = parse_chat([
        "17/09/2026 14:02 - Loja: IMG-20260917-WA0001.jpg (arquivo anexado)",
        "Caneca #A1 R$ 10,00",
        "17/09/2026 14:05 - Loja: <Mídia oculta>",
        "[17/09/2026, 14:06:00] Loja: \u200e<anexado: 0001-PHOTO.jpg>",
        "17/09/2026 14:07 - Ana: quero",
    ])
    assert [m.has_media for m in msgs] == [True, True, True, False]
    assert msgs[0].text == "Caneca #A1 R$ 10,00"
    assert msgs[1].text == ""


def test_colon_inside_message_does_not_break_sender():
    msgs = parse_chat(["17/09/2026 14:32 - Ana: horário: 15:30 pode ser?"])
    assert msgs[0].sender == "Ana"
    assert msgs[0].text == "horário: 15:30 pode ser?"

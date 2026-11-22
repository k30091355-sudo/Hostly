import pytest

from hostly import codes, console, motd, pricing


@pytest.mark.parametrize("days,holz,eisen,diamant", [
    (1, 10, 30, 50), (2, 19, 58, 98), (7, 65, 195, 325), (15, 127, 382, 637),
    (30, 210, 630, 1050), (50, 250, 750, 1250), (100, 500, 1500, 2500),
])
def test_price_examples_from_concept(days, holz, eisen, diamant):
    assert pricing.rent_price(days, 10).final == holz
    assert pricing.rent_price(days, 30).final == eisen
    assert pricing.rent_price(days, 50).final == diamant


def test_promo_adds_and_is_capped():
    assert pricing.rent_price(30, 50, promo_percent=20).final == 750   # 30 % + 20 %
    p = pricing.rent_price(60, 50, promo_percent=30)                   # 50 % + 30 % → 75 %
    assert p.discount == 75 and p.final == 750


def test_refund_full_days_rounded_down():
    assert pricing.refund(10, 650, 7) == 928   # 10 × 92,857… → 928
    assert pricing.refund(0, 650, 7) == 0


@pytest.mark.parametrize("cmd", ["stop", "/stop", "minecraft:stop", "STOP", "  /Minecraft:Stop  ", "restart",
                                 "spigot:restart", "bukkit:restart", "reload", "rl", "bukkit:reload", "bukkit:rl",
                                 "minecraft:reload", "reload confirm", "/RL", "end", ""])
def test_blocked_commands(cmd):
    assert console.is_blocked(cmd)


@pytest.mark.parametrize("cmd", ["say hallo", "op Steve", "whitelist add Alex", "time set day", "stopsound @a",
                                 "list", "weather clear"])
def test_allowed_commands(cmd):
    assert not console.is_blocked(cmd)


def test_code_format_and_normalize():
    c = codes.generate()
    assert len(c) == 19 and c.count("-") == 3
    assert all(ch in "23456789abcdefghjkmnpqrstuvwxyz-" for ch in c)
    assert codes.normalize("ABCD EFGH-jkmn pqrs") == "abcd-efgh-jkmn-pqrs"
    assert codes.normalize("abcdefghjkmnpqrs") == "abcd-efgh-jkmn-pqrs"


def test_motd_html_is_escaped():
    html = str(motd.to_html("§cRot <script>\n§lFett"))
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "#FF5555" in html and "<br>" in html and "bold" in html
    assert motd.check("a\nb\nc") is not None
    assert motd.check("§a" + "x" * 60) is None
    assert motd.check("x" * 61) is not None

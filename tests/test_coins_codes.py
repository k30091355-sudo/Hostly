import re

from hostly import coins, db

from .conftest import conn, csrf_of, logout, register


def admin_create_code(client, coins_amount=100, max_uses=1, count=1, expires=""):
    token = csrf_of(client, "/admin/codes")
    r = client.post("/admin/codes", data={"coins": coins_amount, "max_uses": max_uses, "count": count,
                                          "expires": expires, "csrf": token})
    return re.findall(r'<code class="mono">([0-9a-z-]{19})</code>', r.text)


def redeem(client, code):
    token = csrf_of(client, "/code")
    return client.post("/code", data={"code": code, "csrf": token})


def test_code_flow(client):
    register(client, "admin")
    new = admin_create_code(client, 100, max_uses=2)
    code = new[0]
    r = redeem(client, code.upper().replace("-", ""))
    assert "+100 Coins gutgeschrieben" in r.text
    assert "Code bereits eingelöst" in redeem(client, code).text
    logout(client)
    register(client, "bob")
    assert "+100" in redeem(client, code).text
    logout(client)
    register(client, "carl")
    assert "Code aufgebraucht" in redeem(client, code).text
    assert "Code ungültig" in redeem(client, "aaaa-bbbb-cccc-dddd").text
    hist = client.get("/einstellungen/coins").text
    assert "Noch keine Buchungen" in hist


def test_code_limits_and_deactivate(client):
    register(client, "admin")
    assert admin_create_code(client, 49) == []          # unter 50
    assert admin_create_code(client, 1001) == []        # über 1000
    many = admin_create_code(client, 50, count=5)
    assert len(set(many)) == 5
    c = conn()
    code_id = c.execute("SELECT id FROM codes WHERE code = ?", (many[0],)).fetchone()[0]
    token = csrf_of(client, "/admin/codes")
    client.post(f"/admin/codes/{code_id}", data={"action": "toggle", "csrf": token})
    assert "Code deaktiviert" in redeem(client, many[0]).text
    c.execute("UPDATE codes SET expires_at = '2000-01-01 00:00:00' WHERE code = ?", (many[1],))
    assert "Code abgelaufen" in redeem(client, many[1]).text


def test_balance_never_negative(client):
    register(client, "admin")
    c = conn()
    with db.transaction(c):
        coins.book(c, 1, 100, "admin")
    try:
        with db.transaction(c):
            coins.book(c, 1, -150, "kauf")
        raise AssertionError("hätte fehlschlagen müssen")
    except coins.NotEnoughCoins:
        pass
    assert coins.balance(c, 1) == 100


def test_admin_user_menu(client):
    register(client, "admin")
    logout(client)
    register(client, "bob")
    logout(client)
    from .conftest import login
    login(client, "admin")
    token = csrf_of(client, "/admin/user/2")
    r = client.post("/admin/user/2/coins", data={"amount": 250, "note": "Geschenk", "csrf": token})
    assert "Gebucht" in r.text
    assert client.post("/admin/user/2/coins", data={"amount": -999, "csrf": token}).status_code == 400
    r = client.post("/admin/user/2/passwort", data={"csrf": token})
    pw = re.search(r'<code class="mono big">([A-Za-z0-9]+)</code>', r.text).group(1)
    logout(client)
    assert login(client, "bob", pw).status_code == 303
    assert client.get("/", follow_redirects=False).headers["location"] == "/einstellungen"
    assert coins.balance(conn(), 2) == 250

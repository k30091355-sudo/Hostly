"""Preisberechnung (KONZEPT.md Kapitel 12). Immer abrunden – zugunsten des Spielers."""
from dataclasses import dataclass

MAX_DAY_DISCOUNT = 50
MAX_TOTAL_DISCOUNT = 75


def day_discount(days: int) -> int:
    """Tage = Rabatt in %, ab 2 Tagen, höchstens 50 %."""
    return min(days, MAX_DAY_DISCOUNT) if days >= 2 else 0


@dataclass
class Price:
    days: int
    original: int        # ohne Rabatt
    discount: int        # Gesamtrabatt in %
    day_discount: int
    promo_discount: int
    final: int           # zu zahlen


def rent_price(days: int, price_per_day: int, promo_percent: int = 0) -> Price:
    dd = day_discount(days)
    total = min(dd + promo_percent, MAX_TOTAL_DISCOUNT)
    original = days * price_per_day
    final = original * (100 - total) // 100   # ganzzahlig = exakt abgerundet
    return Price(days, original, total, dd, promo_percent, final)


def refund(full_rest_days: int, paid_total: int, paid_days: int) -> int:
    """Erstattung beim Löschen: volle Resttage × tatsächlich bezahlter Tagespreis (abgerundet)."""
    if full_rest_days <= 0 or paid_days <= 0:
        return 0
    return full_rest_days * paid_total // paid_days

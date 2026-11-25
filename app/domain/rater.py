from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.domain.facts import (
    Fact,
    agreed,
    license_is_expired,
    prior_is_lapsed,
    values,
    years_licensed,
)

OfferStatus = Literal["quoted", "provisional", "declined"]


@dataclass(frozen=True)
class Carrier:
    name: str
    factor: float
    point_load: float
    young_load: float
    lapse_load: float
    needs_points: bool


CARRIERS = (
    Carrier("Cobble Hill Auto", 0.97, 0.02, 0.0, 0.10, False),
    Carrier("Mill Pond Casualty", 1.02, 0.03, 0.05, 0.0, True),
    Carrier("Red Lantern Mutual", 1.04, 0.01, 0.18, 0.05, False),
    Carrier("Fairweather Preferred", 0.99, 0.04, 0.0, 0.22, False),
    Carrier("Paper Street Indemnity", 1.06, 0.02, 0.08, 0.0, True),
    Carrier("Northglass Auto", 0.90, 0.09, 0.04, 0.12, False),
)


@dataclass(frozen=True)
class Offer:
    carrier: str
    premium: float | None
    status: OfferStatus
    reason: str


@dataclass(frozen=True)
class RateSheet:
    offers: tuple[Offer, ...]
    best: Offer | None
    blocked: tuple[str, ...]


def money(amount: float) -> float:
    """Cents, half up. The extra nudge keeps a binary halfway value on the high side."""
    return round(amount + 1e-9, 2)


def shop(facts: Sequence[Fact], today: date) -> RateSheet:
    blocks = _blocks(facts, today)
    if blocks:
        reason = " ".join(blocks)
        offers = tuple(
            Offer(carrier.name, None, "declined", reason)
            for carrier in CARRIERS
        )
        return RateSheet(offers, None, tuple(blocks))

    years = years_licensed(facts, today)
    assert years.years is not None
    point_values = values(facts, "sdip_points")
    points_missing = len(set(point_values)) != 1
    points = 0 if points_missing else int(point_values[0])
    experienced = years.years >= 6
    lapsed = prior_is_lapsed(facts, today)
    base = 820.0 if experienced else 1180.0
    base *= 1 + ((0.15 if experienced else 0.075) * points)
    if lapsed:
        base *= 1.20
    vehicle_year = agreed(facts, "vehicle_year")
    if vehicle_year and int(vehicle_year) <= today.year - 15:
        base *= 1.06

    offers = []
    for carrier in CARRIERS:
        if points_missing and carrier.needs_points:
            offers.append(Offer(
                carrier.name,
                None,
                "declined",
                "This carrier will not rate without the merit points.",
            ))
            continue
        amount = base * carrier.factor
        amount += base * carrier.point_load * points
        if not experienced:
            amount *= 1 + carrier.young_load
        if lapsed:
            amount *= 1 + carrier.lapse_load
        status: OfferStatus = "quoted"
        reason = "Firm quote from the file."
        if points_missing:
            amount *= 1.08
            status = "provisional"
            reason = "Points are missing. Premium includes an 8 percent contingency."
        if years.estimated:
            reason = "Years licensed are a floor taken from the prior policy expiration. " + reason
        offers.append(Offer(carrier.name, money(amount), status, reason))

    firm = [offer for offer in offers if offer.status == "quoted"]
    pool = firm or [offer for offer in offers if offer.status == "provisional"]
    best = min(pool, key=lambda offer: offer.premium or 0) if pool else None
    return RateSheet(tuple(offers), best, ())


def _blocks(facts: Sequence[Fact], today: date) -> list[str]:
    blocks = []
    if license_is_expired(facts, today):
        blocks.append("The license is expired. None of the six will bind it.")
    if not values(facts, "vin"):
        blocks.append("The VIN is not in the file. A plate is not enough to identify the car.")
    if not values(facts, "license_number"):
        blocks.append("The license number is not in the file.")
    if not values(facts, "insured_name"):
        blocks.append("The insured's name is not in the file.")
    years = years_licensed(facts, today)
    if years.years is None:
        if values(facts, "license_issued_on") or values(facts, "prior_policy_expires_on"):
            blocks.append("Years licensed cannot be priced from conflicting dates.")
        else:
            blocks.append(
                "There is no license issue date and no prior policy expiration to estimate years licensed."
            )
    return blocks

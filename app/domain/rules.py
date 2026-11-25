from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.domain.facts import (
    Conflict,
    Fact,
    agreed,
    conflicts,
    license_is_expired,
    prior_is_lapsed,
    values,
    years_licensed,
)

RecommendationName = Literal["quote", "refer", "decline", "incomplete", "out_of_scope"]


@dataclass(frozen=True)
class Recommendation:
    recommendation: RecommendationName
    reasons: tuple[str, ...]
    missing: tuple[str, ...]
    conflicts: tuple[Conflict, ...]


def recommend(facts: Sequence[Fact], today: date) -> Recommendation:
    found = conflicts(facts)
    lines = values(facts, "line_of_business")
    if lines and "auto" not in lines and not values(facts, "vin"):
        named = agreed(facts, "line_of_business") or "not auto"
        return Recommendation(
            "out_of_scope",
            (f"The line on file is {named}, and there is no VIN.",),
            (),
            found,
        )
    if license_is_expired(facts, today):
        when = agreed(facts, "license_expires_on")
        sentence = f"The license expired on {when}." if when else "The license is expired."
        return Recommendation("decline", (sentence,), (), found)

    if not lines or agreed(facts, "line_of_business") == "auto":
        missing = _missing_auto(facts)
        if missing:
            names = ", ".join(missing)
            return Recommendation(
                "incomplete",
                (f"The auto file is missing {names}.",),
                missing,
                found,
            )

    refer = _refer_reasons(facts, today, found)
    floor = _floor_reason(facts, today)
    if refer:
        if floor:
            refer.append(floor)
        missing = ("sdip_points",) if not values(facts, "sdip_points") else ()
        return Recommendation("refer", tuple(refer), missing, found)

    reasons = (floor,) if floor else ("The file supports a quote.",)
    return Recommendation("quote", reasons, (), found)


def _missing_auto(facts: Sequence[Fact]) -> tuple[str, ...]:
    missing = []
    for name in ("insured_name", "license_number", "vin"):
        if not values(facts, name):
            missing.append(name)
    if not values(facts, "license_issued_on") and not values(facts, "prior_policy_expires_on"):
        missing.append("license_issued_on")
        missing.append("prior_policy_expires_on")
    return tuple(missing)


def _refer_reasons(facts: Sequence[Fact], today: date, found: tuple[Conflict, ...]) -> list[str]:
    reasons = []
    for conflict in found:
        reasons.append(f"{conflict.field} is cited with different values.")
    if prior_is_lapsed(facts, today):
        when = agreed(facts, "prior_policy_expires_on")
        reasons.append(f"The prior policy expired on {when}.")
    if not values(facts, "sdip_points"):
        reasons.append("SDIP points are not in the file.")
    else:
        points = agreed(facts, "sdip_points")
        if points is not None and int(points) >= 4:
            reasons.append(f"SDIP points are {points}.")
    return reasons


def _floor_reason(facts: Sequence[Fact], today: date) -> str | None:
    years = years_licensed(facts, today)
    if not years.estimated or years.years is None:
        return None
    return (
        "Years licensed are a floor of "
        f"{years.years} from the prior policy expiration."
    )

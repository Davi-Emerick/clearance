from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Fact:
    name: str
    value: str
    document_id: str
    quote: str


@dataclass(frozen=True)
class ConflictValue:
    value: str
    document_id: str
    quote: str


@dataclass(frozen=True)
class Conflict:
    field: str
    values: tuple[ConflictValue, ...]


@dataclass(frozen=True)
class YearsLicensed:
    years: int | None
    estimated: bool


def completed_years(start: date, end: date) -> int:
    """Whole years from start to end. The last year counts on the anniversary."""
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(years, 0)


def values(facts: Sequence[Fact], name: str) -> tuple[str, ...]:
    return tuple(fact.value.strip() for fact in facts if fact.name == name and fact.value.strip())


def agreed(facts: Sequence[Fact], name: str) -> str | None:
    found = values(facts, name)
    if len(set(found)) != 1:
        return None
    return found[0]


def agreed_date(facts: Sequence[Fact], name: str) -> date | None:
    raw = agreed(facts, name)
    if raw is None:
        return None
    return date.fromisoformat(raw)


def agreed_int(facts: Sequence[Fact], name: str) -> int | None:
    raw = agreed(facts, name)
    if raw is None:
        return None
    return int(raw)


def conflicts(facts: Sequence[Fact]) -> tuple[Conflict, ...]:
    grouped: dict[str, list[Fact]] = {}
    for fact in facts:
        if not fact.value.strip():
            continue
        grouped.setdefault(fact.name, []).append(fact)
    found = []
    for name, group in grouped.items():
        distinct = {fact.value.strip() for fact in group}
        if len(distinct) < 2:
            continue
        found.append(Conflict(
            field=name,
            values=tuple(
                ConflictValue(fact.value.strip(), fact.document_id, fact.quote)
                for fact in group
            ),
        ))
    return tuple(found)


def license_is_expired(facts: Sequence[Fact], today: date) -> bool:
    dates = [date.fromisoformat(value) for value in values(facts, "license_expires_on")]
    if not dates:
        return False
    return all(day <= today for day in dates)


def prior_is_lapsed(facts: Sequence[Fact], today: date) -> bool:
    expires = agreed_date(facts, "prior_policy_expires_on")
    return expires is not None and expires <= today


def years_licensed(facts: Sequence[Fact], today: date) -> YearsLicensed:
    """Completed years from the license issue date.

    When that date is missing and the prior-policy expiration is on file,
    the same count runs from the expiration date and is only a floor.
    """
    if values(facts, "license_issued_on") and agreed(facts, "license_issued_on") is None:
        return YearsLicensed(None, False)
    issued = agreed_date(facts, "license_issued_on")
    if issued is not None:
        return YearsLicensed(completed_years(issued, today), False)
    if values(facts, "prior_policy_expires_on") and agreed(facts, "prior_policy_expires_on") is None:
        return YearsLicensed(None, False)
    prior = agreed_date(facts, "prior_policy_expires_on")
    if prior is None:
        return YearsLicensed(None, False)
    return YearsLicensed(completed_years(prior, today), True)

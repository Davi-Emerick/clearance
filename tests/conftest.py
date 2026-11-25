import pytest

from app.domain.facts import Fact


def build_file(**changes: str | list[tuple[str, str]] | None) -> tuple[Fact, ...]:
    base: dict[str, str | list[tuple[str, str]] | None] = {
        "insured_name": "Marcus Hale",
        "license_number": "S10000023",
        "license_issued_on": "2014-03-01",
        "license_expires_on": "2028-03-01",
        "vin": "1FAKE0HALE0CAR001",
        "plate": "MA 4KTP92",
        "vehicle_year": "2018",
        "prior_policy_expires_on": "2027-03-01",
        "sdip_points": "0",
        "line_of_business": "auto",
    }
    for name, value in changes.items():
        base[name] = value
    facts = []
    for name, value in base.items():
        if value is None:
            continue
        entries = value if isinstance(value, list) else [(value, "folder")]
        for text, document_id in entries:
            facts.append(Fact(name, text, document_id, text))
    return tuple(facts)


@pytest.fixture
def filed():
    return build_file

from datetime import date

import pytest

from app.domain.rater import shop
from app.domain.rules import recommend

TODAY = date(2026, 6, 15)


def _by_carrier(sheet):
    return {offer.carrier: offer for offer in sheet.offers}


def test_northglass_premium_is_738(filed):
    sheet = shop(filed(), TODAY)
    offers = _by_carrier(sheet)
    assert sheet.best is not None
    assert sheet.best.carrier == "Northglass Auto"
    assert sheet.best.premium == 738.00
    assert sheet.best.status == "quoted"
    assert offers["Cobble Hill Auto"].premium == 795.40
    assert offers["Mill Pond Casualty"].premium == 836.40
    assert offers["Red Lantern Mutual"].premium == 852.80
    assert offers["Fairweather Preferred"].premium == 811.80
    assert offers["Paper Street Indemnity"].premium == 869.20
    assert len(sheet.offers) == 6
    assert sheet.blocked == ()


def test_plate_conflict_with_the_same_vin_still_rates(filed):
    sheet = shop(
        filed(plate=[("MA 4KTP92", "registration"), ("MA 8RNP41", "note")]),
        TODAY,
    )
    assert sheet.best is not None
    assert sheet.best.carrier == "Northglass Auto"
    assert sheet.best.premium == 738.00
    assert sheet.best.status == "quoted"


@pytest.mark.parametrize(
    "changes",
    [
        {"license_expires_on": "2024-01-01"},
        {"vin": None},
        {"license_number": None},
        {"insured_name": None},
        {"license_issued_on": None, "prior_policy_expires_on": None},
    ],
)
def test_rating_block_declines_every_carrier(filed, changes):
    sheet = shop(filed(**changes), TODAY)
    assert sheet.best is None
    assert sheet.blocked
    assert len(sheet.offers) == 6
    assert all(offer.premium is None and offer.status == "declined" for offer in sheet.offers)


def test_missing_points_are_provisional(filed):
    facts = filed(sdip_points=None)
    assert recommend(facts, TODAY).recommendation == "refer"
    sheet = shop(facts, TODAY)
    assert all(offer.status != "quoted" for offer in sheet.offers)
    offers = _by_carrier(sheet)
    assert offers["Mill Pond Casualty"].status == "declined"
    assert offers["Mill Pond Casualty"].premium is None
    assert offers["Paper Street Indemnity"].status == "declined"
    assert offers["Northglass Auto"].status == "provisional"
    assert offers["Northglass Auto"].premium == 797.04
    assert sheet.best is not None
    assert sheet.best.carrier == "Northglass Auto"
    assert sheet.best.status == "provisional"


def test_four_points_still_receive_a_firm_price(filed):
    facts = filed(sdip_points="4")
    assert recommend(facts, TODAY).recommendation == "refer"
    offer = _by_carrier(shop(facts, TODAY))["Northglass Auto"]
    assert offer.status == "quoted"
    assert offer.premium == 1653.12


def test_lapse_load_uses_the_carrier_factor(filed):
    sheet = shop(filed(prior_policy_expires_on="2026-01-01"), TODAY)
    offers = _by_carrier(sheet)
    assert offers["Northglass Auto"].premium == 991.87
    assert offers["Mill Pond Casualty"].premium == 1003.68
    assert offers["Northglass Auto"].status == "quoted"


def test_vehicle_fifteen_years_old_takes_the_age_load(filed):
    old = shop(filed(vehicle_year="2011"), TODAY)
    newer = shop(filed(vehicle_year="2012"), TODAY)
    assert _by_carrier(old)["Northglass Auto"].premium == 782.28
    assert _by_carrier(newer)["Northglass Auto"].premium == 738.00


def test_inexperienced_driver_uses_the_young_base_and_point_load(filed):
    sheet = shop(filed(license_issued_on="2024-03-01", sdip_points="2"), TODAY)
    offer = _by_carrier(sheet)["Northglass Auto"]
    assert offer.premium == 1524.18
    assert offer.status == "quoted"


def test_years_floor_is_rated_and_recorded(filed):
    sheet = shop(filed(license_issued_on=None, prior_policy_expires_on="2027-03-01"), TODAY)
    offer = _by_carrier(sheet)["Northglass Auto"]
    assert offer.premium == 1104.48
    assert offer.status == "quoted"
    assert offer.reason.startswith("Years licensed are a floor")

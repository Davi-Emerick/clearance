from datetime import date

from app.domain.facts import completed_years
from app.domain.rules import recommend

TODAY = date(2026, 6, 15)


def test_completed_years_waits_for_the_anniversary():
    assert completed_years(date(2014, 3, 1), TODAY) == 12
    assert completed_years(date(2014, 8, 1), TODAY) == 11
    assert completed_years(date(2020, 6, 15), TODAY) == 6
    assert completed_years(date(2020, 6, 16), TODAY) == 5


def test_homeowners_with_no_vin_is_out_of_scope(filed):
    result = recommend(filed(line_of_business="homeowners", vin=None), TODAY)
    assert result.recommendation == "out_of_scope"
    assert result.missing == ()
    assert "homeowners" in result.reasons[0]
    assert "VIN" in result.reasons[0]


def test_life_with_no_vin_is_out_of_scope(filed):
    result = recommend(filed(line_of_business="life", vin=None), TODAY)
    assert result.recommendation == "out_of_scope"
    assert "life" in result.reasons[0]


def test_missing_line_and_missing_vin_is_incomplete(filed):
    result = recommend(filed(line_of_business=None, vin=None), TODAY)
    assert result.recommendation == "incomplete"
    assert "vin" in result.missing


def test_missing_line_on_a_firm_auto_file_is_quote(filed):
    result = recommend(filed(line_of_business=None), TODAY)
    assert result.recommendation == "quote"


def test_expired_license_is_declined(filed):
    result = recommend(filed(license_expires_on="2024-01-01"), TODAY)
    assert result.recommendation == "decline"
    assert result.reasons == ("The license expired on 2024-01-01.",)


def test_license_that_expires_today_is_declined(filed):
    result = recommend(filed(license_expires_on="2026-06-15"), TODAY)
    assert result.recommendation == "decline"


def test_license_that_expires_tomorrow_can_be_quoted(filed):
    result = recommend(filed(license_expires_on="2026-06-16"), TODAY)
    assert result.recommendation == "quote"


def test_missing_vin_is_incomplete(filed):
    result = recommend(filed(vin=None), TODAY)
    assert result.recommendation == "incomplete"
    assert result.missing == ("vin",)


def test_missing_name_is_incomplete(filed):
    result = recommend(filed(insured_name=None), TODAY)
    assert result.recommendation == "incomplete"
    assert result.missing == ("insured_name",)


def test_missing_license_number_is_incomplete(filed):
    result = recommend(filed(license_number=None), TODAY)
    assert result.recommendation == "incomplete"
    assert result.missing == ("license_number",)


def test_out_of_scope_wins_over_an_expired_license(filed):
    result = recommend(
        filed(line_of_business="homeowners", vin=None, license_expires_on="2024-01-01"),
        TODAY,
    )
    assert result.recommendation == "out_of_scope"


def test_expired_license_and_missing_vin_is_declined(filed):
    result = recommend(filed(license_expires_on="2024-01-01", vin=None), TODAY)
    assert result.recommendation == "decline"


def test_both_dates_missing_is_incomplete(filed):
    result = recommend(
        filed(license_issued_on=None, prior_policy_expires_on=None),
        TODAY,
    )
    assert result.recommendation == "incomplete"
    assert result.missing == ("license_issued_on", "prior_policy_expires_on")


def test_plate_conflict_with_zero_points_is_refer(filed):
    result = recommend(
        filed(plate=[("MA 4KTP92", "registration"), ("MA 8RNP41", "note")]),
        TODAY,
    )
    assert result.recommendation == "refer"
    assert result.conflicts[0].field == "plate"
    assert [item.value for item in result.conflicts[0].values] == ["MA 4KTP92", "MA 8RNP41"]


def test_missing_points_is_refer(filed):
    result = recommend(filed(sdip_points=None), TODAY)
    assert result.recommendation == "refer"
    assert result.missing == ("sdip_points",)


def test_four_points_is_refer(filed):
    result = recommend(filed(sdip_points="4"), TODAY)
    assert result.recommendation == "refer"
    assert "4" in result.reasons[0]


def test_three_points_is_quote(filed):
    result = recommend(filed(sdip_points="3"), TODAY)
    assert result.recommendation == "quote"


def test_lapsed_prior_policy_is_refer(filed):
    result = recommend(filed(prior_policy_expires_on="2026-06-15"), TODAY)
    assert result.recommendation == "refer"
    assert "2026-06-15" in result.reasons[0]


def test_prior_policy_still_in_force_is_quote(filed):
    result = recommend(filed(prior_policy_expires_on="2026-06-16"), TODAY)
    assert result.recommendation == "quote"


def test_years_floor_stays_on_quote(filed):
    result = recommend(filed(license_issued_on=None, prior_policy_expires_on="2027-03-01"), TODAY)
    assert result.recommendation == "quote"
    assert result.reasons == (
        "Years licensed are a floor of 0 from the prior policy expiration.",
    )


def test_firm_auto_file_is_quote(filed):
    result = recommend(filed(), TODAY)
    assert result.recommendation == "quote"
    assert result.missing == ()
    assert result.conflicts == ()

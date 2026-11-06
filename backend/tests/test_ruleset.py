from datetime import date

from app.rules.ruleset import CURRENT, RULESETS, ruleset_for


def test_current_limit_is_24_hours():
    assert CURRENT.off_campus_weekly_limit_hours == 24
    assert CURRENT.weekly_limit_minutes == 1440


def test_ruleset_lookup_by_date():
    assert ruleset_for(date(2026, 11, 6)) is CURRENT
    assert ruleset_for(date(2024, 11, 8)) is CURRENT
    assert ruleset_for(date(2024, 11, 7)) is None  # older rules aren't modelled


def test_every_rule_cites_an_official_source():
    for ruleset in RULESETS:
        assert ruleset.rules
        for rule in ruleset.rules:
            assert rule.sources, rule.id
            for source in rule.sources:
                assert source.url.startswith(("https://www.canada.ca/", "https://ircc.canada.ca/")), source.url


def test_rule_ids_are_unique():
    ids = [rule.id for rule in CURRENT.rules]
    assert len(ids) == len(set(ids))

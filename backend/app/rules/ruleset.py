"""Work-hour rules for international students in Canada, each tied to its official source.

Rules change over time, so they are stored as dated rule sets. To update the app after
an IRCC change, add a new RuleSet with a later `effective_from` and its sources —
existing history keeps being checked against the rules that applied at the time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

OFF_CAMPUS_PAGE = "https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/work/work-off-campus.html"
BREAKS_FAQ = "https://ircc.canada.ca/english/helpcentre/answer.asp?qnum=499&top=15"
NOV_2024_REGULATIONS = (
    "https://www.canada.ca/en/immigration-refugees-citizenship/news/2024/11/"
    "new-international-student-program-regulations-take-effect.html"
)


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    checked_on: date  # when this rule was last verified against the source


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    summary: str
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class RuleSet:
    version: str
    effective_from: date
    off_campus_weekly_limit_hours: float
    warning_threshold: float  # share of the limit at which to warn, e.g. 0.9
    rules: tuple[Rule, ...] = field(default_factory=tuple)

    @property
    def weekly_limit_minutes(self) -> int:
        return int(self.off_campus_weekly_limit_hours * 60)


_CHECKED = date(2026, 11, 6)
_OFF_CAMPUS = Source("Work off campus as an international student (IRCC)", OFF_CAMPUS_PAGE, _CHECKED)
_BREAKS = Source("Can I continue to work during scheduled school breaks? (IRCC Help Centre)", BREAKS_FAQ, _CHECKED)
_REGS = Source("New International Student Program regulations take effect (IRCC, Nov 2024)", NOV_2024_REGULATIONS, _CHECKED)

RULESETS: tuple[RuleSet, ...] = (
    RuleSet(
        version="2024-11-08",
        effective_from=date(2024, 11, 8),
        off_campus_weekly_limit_hours=24,
        warning_threshold=0.9,
        rules=(
            Rule(
                id="off_campus_weekly_limit",
                title="24 hours per week off campus during academic sessions",
                summary="Eligible students can work up to 24 hours per week off campus while classes are in session. "
                "Working more is a violation of study permit conditions.",
                sources=(_OFF_CAMPUS, _REGS),
            ),
            Rule(
                id="what_counts_as_hours",
                title="Hours = time spent earning wages or commission",
                summary="Any time spent earning wages or collecting a commission counts, across all off-campus jobs "
                "combined. For delivery and other gig work, log the time you were earning, not time logged into the app.",
                sources=(_OFF_CAMPUS,),
            ),
            Rule(
                id="scheduled_breaks",
                title="No weekly limit during scheduled breaks",
                summary="During breaks scheduled by your school (e.g. winter and summer holidays, reading week) you can "
                "work full-time. The 24-hour limit applies again once classes restart.",
                sources=(_OFF_CAMPUS, _BREAKS),
            ),
            Rule(
                id="on_campus",
                title="On-campus work has no weekly limit",
                summary="On-campus work isn't counted toward the off-campus weekly limit, as long as you meet the "
                "on-campus work requirements.",
                sources=(_BREAKS,),
            ),
            Rule(
                id="week_definition",
                title="How Within24 counts a 'week'",
                summary="IRCC doesn't define when a week starts. To stay on the safe side, Within24 checks both "
                "calendar weeks and every rolling 7-day window, and warns if either goes over.",
                sources=(_OFF_CAMPUS,),
            ),
        ),
    ),
)


def ruleset_for(day: date) -> RuleSet | None:
    """Return the rule set in effect on `day`, or None if it predates the rules we support."""
    applicable = [rs for rs in RULESETS if rs.effective_from <= day]
    return max(applicable, key=lambda rs: rs.effective_from) if applicable else None


CURRENT = RULESETS[-1]

from tests.conftest import register


def setup_data(client, headers):
    store = client.post("/jobs", json={"name": "Café — Downtown", "job_type": "off_campus"}, headers=headers).json()["id"]
    library = client.post("/jobs", json={"name": "Library", "job_type": "on_campus"}, headers=headers).json()["id"]
    for day in ("2026-11-02", "2026-11-03", "2026-11-04"):  # 3 x 9 h = 27 h -> over the limit
        client.post(
            "/shifts",
            json={"job_id": store, "starts_at": f"{day}T09:00:00-05:00", "ends_at": f"{day}T18:00:00-05:00"},
            headers=headers,
        )
    client.post(
        "/shifts",
        json={"job_id": library, "starts_at": "2026-11-05T22:00:00-05:00", "ends_at": "2026-11-06T02:00:00-05:00"},
        headers=headers,
    )
    client.post("/breaks", json={"name": "Reading week", "start_date": "2026-10-12", "end_date": "2026-10-16"}, headers=headers)


def test_pdf_report(client, auth_headers):
    setup_data(client, auth_headers)
    response = client.get("/reports/hours.pdf", params={"start": "2026-10-12", "end": "2026-11-08"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="within24-hours-2026-10-12-to-2026-11-08.pdf"' in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")


def test_pdf_shows_local_times(client, auth_headers):
    from app.services import report

    captured = {}
    original = report.HoursPDF.table

    def spy(self, headers, widths, rows, aligns, red_rows=()):
        captured[headers[0]] = rows
        return original(self, headers, widths, rows, aligns, red_rows)

    setup_data(client, auth_headers)
    report.HoursPDF.table = spy
    try:
        client.get("/reports/hours.pdf", params={"start": "2026-11-02", "end": "2026-11-08"}, headers=auth_headers)
    finally:
        report.HoursPDF.table = original
    shifts = captured["Date"]
    assert shifts[0][:2] == ["Mon Nov 02", "09:00 - 18:00"]
    assert shifts[-1][1:2] == ["22:00 - 02:00 (+1)"] and shifts[-1][-1] == "no limit"
    assert captured["Week (Mon-Sun)"][0][-1] == "Over limit"


def test_weekly_summary_numbers():
    # The numbers behind the PDF, checked without parsing the PDF itself.
    from datetime import date, datetime, timezone
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from app.models import JobType
    from app.rules.engine import Break
    from app.rules.ruleset import CURRENT
    from app.services.report import summarize

    utc = timezone.utc

    def shift(job_type, start, end):
        job = SimpleNamespace(job_type=job_type, name="x")
        return SimpleNamespace(starts_at=start, ends_at=end, earning_minutes=None, job=job,
                               counted_minutes=int((end - start).total_seconds() // 60))

    shifts = [
        shift(JobType.OFF_CAMPUS, datetime(2026, 11, 2, 14, tzinfo=utc), datetime(2026, 11, 2, 23, tzinfo=utc)),
        shift(JobType.ON_CAMPUS, datetime(2026, 11, 3, 14, tzinfo=utc), datetime(2026, 11, 3, 18, tzinfo=utc)),
        shift(JobType.OFF_CAMPUS, datetime(2026, 11, 10, 14, tzinfo=utc), datetime(2026, 11, 10, 20, tzinfo=utc)),
    ]
    weeks, rows = summarize(
        shifts, [Break(date(2026, 11, 9), date(2026, 11, 15))], ZoneInfo("America/Toronto"), CURRENT,
        date(2026, 11, 2), date(2026, 11, 15),
    )
    assert [(w.counted, w.on_campus, w.in_break) for w in weeks] == [(540, 240, 0), (0, 0, 360)]
    assert [r.counted for r in rows] == [540, None, 0]


def test_report_validation(client, auth_headers):
    bad = client.get("/reports/hours.pdf", params={"start": "2026-11-08", "end": "2026-11-01"}, headers=auth_headers)
    assert bad.status_code == 422
    too_long = client.get("/reports/hours.pdf", params={"start": "2025-01-06", "end": "2026-11-01"}, headers=auth_headers)
    assert too_long.status_code == 422
    empty = client.get("/reports/hours.pdf", headers=register(client, "new@example.com"))
    assert empty.status_code == 200
    assert client.get("/reports/hours.pdf").status_code == 401

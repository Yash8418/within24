import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import CheckShift from "../components/CheckShift.jsx";
import { JOB_TYPES } from "./JobsPage.jsx";
import { addDays, startOfWeek, toDateInput } from "./ShiftsPage.jsx";

const hours = (minutes) => {
  const h = minutes / 60;
  return Number.isInteger(h) ? `${h}` : h.toFixed(1);
};

const STATUS_TEXT = {
  ok: "You're within the limit.",
  warning: "You're close to the limit.",
  over: "You're over the limit.",
};

const dayFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const parseDate = (iso) => new Date(`${iso}T00:00:00`);

function WeekMeter({ week }) {
  const used = Math.min(week.minutes / week.limit_minutes, 1);
  return (
    <div className={`meter meter--${week.status}`}>
      <div className="meter__numbers">
        <span className="meter__big">{hours(week.remaining_minutes)}</span>
        <span className="meter__unit">{week.remaining_minutes === 60 ? "hour" : "hours"} left this week</span>
      </div>
      <div
        className="meter__bar"
        role="progressbar"
        aria-label="Off-campus hours used this week"
        aria-valuemin={0}
        aria-valuemax={week.limit_minutes / 60}
        aria-valuenow={Number(hours(week.minutes))}
      >
        <span style={{ width: `${used * 100}%` }} />
      </div>
      <p className="meter__caption">
        <strong>{hours(week.minutes)}</strong> of {hours(week.limit_minutes)} off-campus hours used ·{" "}
        {STATUS_TEXT[week.status]}
      </p>
    </div>
  );
}

function RecentWeeks({ weeks, limit }) {
  const max = Math.max(limit, ...weeks.map((w) => w.minutes));
  return (
    <ol className="recent">
      {weeks.map((week) => (
        <li key={week.week_start} title={`Week of ${dayFmt.format(parseDate(week.week_start))}: ${hours(week.minutes)} h`}>
          <span className="recent__value">{hours(week.minutes)}</span>
          <span className="recent__track">
            <span className={`recent__bar recent__bar--${week.status}`} style={{ height: `${(week.minutes / max) * 100}%` }} />
            <span className="recent__limit" style={{ bottom: `${(limit / max) * 100}%` }} />
          </span>
          <span className="recent__label">{dayFmt.format(parseDate(week.week_start))}</span>
        </li>
      ))}
    </ol>
  );
}

export default function DashboardPage() {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [summary, setSummary] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    api.listJobs().then(setJobs).catch(() => {});
  }, []);

  useEffect(() => {
    setError("");
    api
      .summary(toDateInput(weekStart), 8)
      .then(setSummary)
      .catch((err) => setError(err.message));
  }, [weekStart, refresh]);

  const isThisWeek = toDateInput(weekStart) === toDateInput(startOfWeek(new Date()));
  const peak = summary?.rolling_peak;
  const peakWarning = peak && peak.status !== "ok" && peak.minutes > (summary?.week.minutes ?? 0);

  return (
    <>
      <div className="week-nav week-nav--page">
        <button type="button" className="button" onClick={() => setWeekStart(addDays(weekStart, -7))} aria-label="Previous week">
          ←
        </button>
        <h1>{isThisWeek ? "This week" : `Week of ${dayFmt.format(weekStart)}`}</h1>
        <button type="button" className="button" onClick={() => setWeekStart(addDays(weekStart, 7))} aria-label="Next week">
          →
        </button>
      </div>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!summary && !error && <p className="muted">Loading…</p>}

      {summary && (
        <div className="dashboard">
          <section className="card dashboard__main" aria-label="Hours this week">
            <WeekMeter week={summary.week} />
            {summary.breaks.map((b) => (
              <p key={b.id} className="callout callout--break">
                <strong>{b.name}</strong> runs {dayFmt.format(parseDate(b.start_date))} –{" "}
                {dayFmt.format(parseDate(b.end_date))}. Off-campus hours on those days don't count toward the limit.
              </p>
            ))}
            {peakWarning && (
              <p className={`callout callout--${peak.status}`}>
                Between {dayFmt.format(new Date(peak.window_start))} and {dayFmt.format(new Date(peak.window_end))} you
                worked <strong>{hours(peak.minutes)} hours</strong> in 7 days. IRCC doesn't say when a week starts, so
                it's safest to stay under {hours(summary.week.limit_minutes)} hours in <em>any</em> 7-day stretch.
              </p>
            )}

            <h2>By job</h2>
            {summary.by_job.length === 0 ? (
              <p className="muted">
                No shifts this week. <Link to="/shifts">Log a shift</Link>
              </p>
            ) : (
              <ul className="list">
                {summary.by_job.map((job) => (
                  <li key={job.job_id} className="list__item">
                    <span>
                      {job.name}
                      <span className={`tag tag--${job.job_type}`}>{JOB_TYPES[job.job_type].label}</span>
                    </span>
                    <span>
                      <strong>{hours(job.minutes)} h</strong>
                      {!job.counts_toward_limit && <span className="muted"> · not counted</span>}
                      {job.minutes_in_break > 0 && (
                        <span className="muted"> + {hours(job.minutes_in_break)} h during break, not counted</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <h2>Last 8 weeks</h2>
            <RecentWeeks weeks={summary.recent_weeks} limit={summary.week.limit_minutes} />
            <p className="hint">Off-campus hours per calendar week. The dashed line is the {hours(summary.week.limit_minutes)}-hour limit. Days in a scheduled break aren't counted.</p>
          </section>

          <CheckShift jobs={jobs} onSaved={() => setRefresh((n) => n + 1)} />
        </div>
      )}
    </>
  );
}

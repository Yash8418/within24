import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import HoursRecord from "../components/HoursRecord.jsx";
import ImportShifts from "../components/ImportShifts.jsx";
import { JOB_TYPES } from "./JobsPage.jsx";

export function startOfWeek(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // Monday
  return d;
}

export function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

export const toDateInput = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

// Local date + times -> ISO strings. An end time at or before the start is the next day (overnight shift).
export function shiftTimes(date, start, end) {
  const startsAt = new Date(`${date}T${start}`);
  let endsAt = new Date(`${date}T${end}`);
  if (endsAt <= startsAt) endsAt = addDays(endsAt, 1);
  return { starts_at: startsAt.toISOString(), ends_at: endsAt.toISOString() };
}

const formatHours = (minutes) => `${(minutes / 60).toFixed(minutes % 60 ? 1 : 0)} h`;
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" });

export default function ShiftsPage() {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [jobs, setJobs] = useState([]);
  const [shifts, setShifts] = useState(null);
  const [form, setForm] = useState({ job_id: "", date: toDateInput(new Date()), start: "09:00", end: "17:00", earning: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api
      .listJobs()
      .then((list) => {
        setJobs(list);
        if (list.length) setForm((f) => ({ ...f, job_id: f.job_id || String(list[0].id) }));
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setShifts(null);
    api
      .listShifts({ start: weekStart.toISOString(), end: addDays(weekStart, 7).toISOString() })
      .then(setShifts)
      .catch((err) => setError(err.message));
  }, [weekStart, reloadKey]);

  const jobById = Object.fromEntries(jobs.map((j) => [j.id, j]));
  const selectedJob = jobById[form.job_id];
  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function addShift(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const shift = await api.createShift({
        job_id: Number(form.job_id),
        ...shiftTimes(form.date, form.start, form.end),
        earning_minutes: selectedJob?.job_type === "gig" && form.earning !== "" ? Math.round(Number(form.earning) * 60) : null,
      });
      const inWeek = new Date(shift.starts_at) >= weekStart && new Date(shift.starts_at) < addDays(weekStart, 7);
      if (inWeek) setShifts([...shifts, shift].sort((a, b) => a.starts_at.localeCompare(b.starts_at)));
      setForm({ ...form, earning: "" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeShift(shift) {
    try {
      await api.deleteShift(shift.id);
      setShifts(shifts.filter((s) => s.id !== shift.id));
    } catch (err) {
      setError(err.message);
    }
  }

  const weekLabel = `${dayFmt.format(weekStart)} – ${dayFmt.format(addDays(weekStart, 6))}`;

  return (
    <>
      <h1>Shifts</h1>
      <div className="two-column">
        <section aria-labelledby="week-heading">
          <div className="week-nav">
            <button type="button" className="button" onClick={() => setWeekStart(addDays(weekStart, -7))} aria-label="Previous week">
              ←
            </button>
            <h2 id="week-heading">{weekLabel}</h2>
            <button type="button" className="button" onClick={() => setWeekStart(addDays(weekStart, 7))} aria-label="Next week">
              →
            </button>
          </div>
          {shifts === null && !error && <p className="muted">Loading…</p>}
          {shifts?.length === 0 && <p className="muted">No shifts logged this week.</p>}
          <ul className="list">
            {shifts?.map((shift) => {
              const job = jobById[shift.job_id];
              return (
                <li key={shift.id} className="list__item">
                  <div>
                    <strong>{dayFmt.format(new Date(shift.starts_at))}</strong>{" "}
                    <span className="muted">
                      {timeFmt.format(new Date(shift.starts_at))} – {timeFmt.format(new Date(shift.ends_at))}
                    </span>
                    <div>
                      {job?.name ?? "Job"} · <strong>{formatHours(shift.counted_minutes)}</strong>
                      {job && job.job_type !== "off_campus" && (
                        <span className={`tag tag--${job.job_type}`}>{JOB_TYPES[job.job_type].label}</span>
                      )}
                    </div>
                  </div>
                  <button type="button" className="link-button link-button--danger" onClick={() => removeShift(shift)}>
                    Delete
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        {jobs.length === 0 ? (
          <div className="card">
            <h2>Add a job first</h2>
            <p className="muted">
              Shifts belong to a job. <Link to="/jobs">Add your jobs</Link> and come back here to log hours.
            </p>
          </div>
        ) : (
          <div className="stack">
            <form className="card stack" onSubmit={addShift}>
              <h2>Log a shift</h2>
              <label>
                Job
                <select value={form.job_id} onChange={update("job_id")}>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Date
                <input type="date" value={form.date} onChange={update("date")} required />
              </label>
              <div className="row">
                <label>
                  Start
                  <input type="time" value={form.start} onChange={update("start")} required />
                </label>
                <label>
                  End
                  <input type="time" value={form.end} onChange={update("end")} required />
                </label>
              </div>
              <span className="hint">An end time earlier than the start counts as an overnight shift.</span>
              {selectedJob?.job_type === "gig" && (
                <label>
                  Hours spent earning <span className="optional">(optional)</span>
                  <input type="number" min="0" step="0.25" value={form.earning} onChange={update("earning")} />
                  <span className="hint">For delivery apps, only time spent earning counts — not time logged in.</span>
                </label>
              )}
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <button className="button button--primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save shift"}
              </button>
            </form>
            <ImportShifts jobs={jobs} onImported={() => setReloadKey((k) => k + 1)} />
            <HoursRecord />
          </div>
        )}
      </div>
    </>
  );
}

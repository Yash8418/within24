import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { shiftTimes, toDateInput } from "../pages/ShiftsPage.jsx";

const hours = (minutes) => {
  const h = minutes / 60;
  return Number.isInteger(h) ? `${h}` : h.toFixed(1);
};

export default function CheckShift({ jobs, onSaved }) {
  const [form, setForm] = useState({ job_id: "", date: toDateInput(new Date()), start: "17:00", end: "22:00", earning: "" });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const jobId = form.job_id || (jobs[0] ? String(jobs[0].id) : "");
  const job = jobs.find((j) => String(j.id) === jobId);

  const update = (field) => (event) => {
    setForm({ ...form, [field]: event.target.value });
    setResult(null);
    setSaved(false);
  };

  const payload = () => ({
    job_id: Number(jobId),
    ...shiftTimes(form.date, form.start, form.end),
    earning_minutes: job?.job_type === "gig" && form.earning !== "" ? Math.round(Number(form.earning) * 60) : null,
  });

  async function check(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      setResult(await api.checkShift(payload()));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setError("");
    try {
      await api.createShift(payload());
      setSaved(true);
      setResult(null);
      onSaved?.();
    } catch (err) {
      setError(err.message);
    }
  }

  if (jobs.length === 0) {
    return (
      <aside className="card">
        <h2>Can I take this shift?</h2>
        <p className="muted">
          <Link to="/jobs">Add a job</Link> first, then check any shift before you say yes.
        </p>
      </aside>
    );
  }

  return (
    <aside className="card stack" aria-labelledby="check-heading">
      <h2 id="check-heading">Can I take this shift?</h2>
      <form className="stack" onSubmit={check}>
        <label>
          Job
          <select value={jobId} onChange={update("job_id")}>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.name}
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
        {job?.job_type === "gig" && (
          <label>
            Expected hours earning <span className="optional">(optional)</span>
            <input type="number" min="0" step="0.25" value={form.earning} onChange={update("earning")} />
          </label>
        )}
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? "Checking…" : "Check this shift"}
        </button>
      </form>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div className={`verdict verdict--${result.allowed ? "yes" : "no"}`} role="status">
          <p className="verdict__title">{result.allowed ? "✓ Yes, you can take it" : "✕ This would put you over"}</p>
          <p>{result.message}</p>
          {result.counts_toward_limit && (
            <p className="verdict__detail">
              Week total: {hours(result.weeks[0].minutes_before)} h → <strong>{hours(result.weeks[0].minutes_after)} h</strong>
              {" · "}busiest 7 days: {hours(result.rolling_peak_minutes_after)} h
            </p>
          )}
          {result.allowed && (
            <button type="button" className="button" onClick={save}>
              Save this shift
            </button>
          )}
        </div>
      )}
      {saved && (
        <p className="verdict verdict--yes" role="status">
          Shift saved.
        </p>
      )}
    </aside>
  );
}

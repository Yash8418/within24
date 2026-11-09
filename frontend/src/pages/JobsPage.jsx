import { useEffect, useState } from "react";
import { api } from "../api.js";

export const JOB_TYPES = {
  off_campus: { label: "Off campus", help: "Counts toward the 24-hour weekly limit." },
  gig: { label: "Gig / delivery app", help: "Counts toward the limit — only time spent earning." },
  on_campus: { label: "On campus", help: "No weekly limit for eligible students." },
};

const EMPTY = { name: "", employer: "", job_type: "off_campus", hourly_rate: "" };

export default function JobsPage() {
  const [jobs, setJobs] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listJobs().then(setJobs).catch((err) => setError(err.message));
  }, []);

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function addJob(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const job = await api.createJob({
        name: form.name.trim(),
        employer: form.employer.trim() || null,
        job_type: form.job_type,
        hourly_rate: form.hourly_rate === "" ? null : Number(form.hourly_rate),
      });
      setJobs([...jobs, job]);
      setForm(EMPTY);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeJob(job) {
    if (!window.confirm(`Delete "${job.name}" and all of its shifts?`)) return;
    try {
      await api.deleteJob(job.id);
      setJobs(jobs.filter((j) => j.id !== job.id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Jobs</h1>
      <p className="page-intro">Add every job you work. Each shift you log belongs to one of these.</p>

      <div className="two-column">
        <section aria-labelledby="your-jobs">
          <h2 id="your-jobs">Your jobs</h2>
          {jobs === null && !error && <p className="muted">Loading…</p>}
          {jobs?.length === 0 && <p className="muted">No jobs yet. Add your first one to start logging shifts.</p>}
          <ul className="list">
            {jobs?.map((job) => (
              <li key={job.id} className="list__item">
                <div>
                  <strong>{job.name}</strong>
                  {job.employer && <span className="muted"> · {job.employer}</span>}
                  <div>
                    <span className={`tag tag--${job.job_type}`}>{JOB_TYPES[job.job_type].label}</span>
                    {job.hourly_rate != null && <span className="muted"> ${job.hourly_rate.toFixed(2)}/h</span>}
                  </div>
                </div>
                <button type="button" className="link-button link-button--danger" onClick={() => removeJob(job)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </section>

        <form className="card stack" onSubmit={addJob}>
          <h2>Add a job</h2>
          <label>
            Job title
            <input value={form.name} onChange={update("name")} placeholder="e.g. Cashier" required maxLength={120} />
          </label>
          <label>
            Employer <span className="optional">(optional)</span>
            <input value={form.employer} onChange={update("employer")} maxLength={120} />
          </label>
          <label>
            Type
            <select value={form.job_type} onChange={update("job_type")}>
              {Object.entries(JOB_TYPES).map(([value, { label }]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <span className="hint">{JOB_TYPES[form.job_type].help}</span>
          </label>
          <label>
            Hourly pay <span className="optional">(optional)</span>
            <input type="number" min="0" step="0.01" value={form.hourly_rate} onChange={update("hourly_rate")} />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button button--primary" type="submit" disabled={busy}>
            {busy ? "Adding…" : "Add job"}
          </button>
        </form>
      </div>
    </>
  );
}

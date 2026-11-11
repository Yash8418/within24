import { useState } from "react";
import { api } from "../api.js";

const SAMPLE = "date,start,end,active_hours,notes\n2026-11-03,18:00,21:30,2.5,Dinner rush\n2026-11-04,22:00,01:00,,";
const MAX_FILE_BYTES = 1_000_000;

const timeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});
const hours = (minutes) => (minutes / 60).toFixed(minutes % 60 ? 2 : 0);

export default function ImportShifts({ jobs, onImported }) {
  const defaultJob = jobs.find((j) => j.job_type === "gig") ?? jobs[0];
  const [jobId, setJobId] = useState(String(defaultJob.id));
  const [csv, setCsv] = useState("");
  const [fileName, setFileName] = useState("");
  const [preview, setPreview] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(text, dryRun) {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const result = await api.importShifts(jobId, text, dryRun);
      if (dryRun) {
        setPreview(result);
      } else {
        setPreview(null);
        setCsv("");
        setFileName("");
        setMessage(`Imported ${result.imported} ${result.imported === 1 ? "shift" : "shifts"}.`);
        onImported();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function chooseFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setError("That file is larger than 1 MB. Split it into smaller files.");
      return;
    }
    const text = await file.text();
    setFileName(file.name);
    setCsv(text);
    run(text, true);
  }

  const newRows = preview?.rows.filter((r) => !r.duplicate) ?? [];
  const duplicates = (preview?.rows.length ?? 0) - newRows.length;

  return (
    <section className="card stack" aria-labelledby="import-heading">
      <h2 id="import-heading">Import from a CSV</h2>
      <p className="muted small">
        Export your trips or shifts from a delivery or rideshare app (or a spreadsheet) as CSV with <code>date</code>,{" "}
        <code>start</code> and <code>end</code> columns. For gig work, add <code>active_hours</code> or{" "}
        <code>active_minutes</code> so only earning time counts.
      </p>
      <label>
        Import into
        <select
          value={jobId}
          onChange={(e) => {
            setJobId(e.target.value);
            if (csv) setPreview(null);
          }}
        >
          {jobs.map((job) => (
            <option key={job.id} value={job.id}>
              {job.name}
            </option>
          ))}
        </select>
      </label>
      <label className="file-input">
        <span>CSV file</span>
        <input type="file" accept=".csv,text/csv" onChange={chooseFile} disabled={busy} />
        {fileName && <span className="hint">{fileName}</span>}
      </label>
      {csv && !preview && !busy && (
        <button type="button" className="button" onClick={() => run(csv, true)}>
          Preview
        </button>
      )}

      {preview && (
        <div className="import-preview" aria-live="polite">
          {preview.errors.length > 0 ? (
            <>
              <p className="form-error" role="alert">
                Fix {preview.errors.length === 1 ? "this row" : `these ${preview.errors.length} rows`} and choose the
                file again — nothing has been imported:
              </p>
              <ul className="import-errors">
                {preview.errors.slice(0, 8).map((e) => (
                  <li key={e.line}>
                    Line {e.line}: {e.message}
                  </li>
                ))}
                {preview.errors.length > 8 && <li>…and {preview.errors.length - 8} more</li>}
              </ul>
            </>
          ) : (
            <>
              <p>
                <strong>{newRows.length}</strong> new {newRows.length === 1 ? "shift" : "shifts"}
                {duplicates > 0 && <span className="muted"> · {duplicates} already saved, will be skipped</span>}
              </p>
              <ul className="import-rows">
                {newRows.slice(0, 5).map((r) => (
                  <li key={r.line}>
                    <span>{timeFmt.format(new Date(r.starts_at))}</span>
                    <span className="mono">
                      {r.earning_minutes != null
                        ? `${hours(r.earning_minutes)} h earning`
                        : `${hours((new Date(r.ends_at) - new Date(r.starts_at)) / 60000)} h`}
                    </span>
                  </li>
                ))}
                {newRows.length > 5 && <li className="muted">…and {newRows.length - 5} more</li>}
              </ul>
              {newRows.length > 0 && (
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => run(csv, false)}
                  disabled={busy}
                >
                  {busy ? "Importing…" : `Import ${newRows.length} ${newRows.length === 1 ? "shift" : "shifts"}`}
                </button>
              )}
            </>
          )}
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="form-success" role="status">
          {message}
        </p>
      )}
      <details className="hint">
        <summary>Example file</summary>
        <pre>{SAMPLE}</pre>
      </details>
    </section>
  );
}

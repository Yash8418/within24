import { useState } from "react";
import { api } from "../api.js";
import { addDays, toDateInput } from "../pages/ShiftsPage.jsx";

export default function HoursRecord() {
  const today = new Date();
  const [start, setStart] = useState(() => toDateInput(addDays(today, -7 * 12 + 1)));
  const [end, setEnd] = useState(() => toDateInput(today));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function download(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { blob, filename } = await api.downloadHoursPdf(start, end);
      const url = URL.createObjectURL(blob);
      const link = Object.assign(document.createElement("a"), { href: url, download: filename });
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card stack" onSubmit={download} aria-labelledby="record-heading">
      <h2 id="record-heading">Hours record (PDF)</h2>
      <p className="muted small">
        A printable summary of every week and shift — handy for your own records or a meeting with your international
        student advisor.
      </p>
      <div className="row">
        <label>
          From
          <input type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} required />
        </label>
        <label>
          To
          <input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} required />
        </label>
      </div>
      <span className="hint">Whole weeks (Monday to Sunday) are included, up to one year.</span>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button" type="submit" disabled={busy}>
        {busy ? "Preparing…" : "Download PDF"}
      </button>
    </form>
  );
}

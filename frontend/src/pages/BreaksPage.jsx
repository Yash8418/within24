import { useEffect, useState } from "react";
import { api } from "../api.js";

const EMPTY = { name: "", start_date: "", end_date: "" };

const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
const formatDate = (iso) => dateFmt.format(new Date(`${iso}T00:00:00`));

function lengthInDays(b) {
  const ms = new Date(`${b.end_date}T00:00:00`) - new Date(`${b.start_date}T00:00:00`);
  return Math.round(ms / 86_400_000) + 1;
}

export default function BreaksPage() {
  const [breaks, setBreaks] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listBreaks().then(setBreaks).catch((err) => setError(err.message));
  }, []);

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function addBreak(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const created = await api.createBreak({ ...form, name: form.name.trim() });
      setBreaks([...breaks, created].sort((a, b) => a.start_date.localeCompare(b.start_date)));
      setForm(EMPTY);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeBreak(b) {
    if (!window.confirm(`Delete "${b.name}"? Hours you worked during it will count toward the limit again.`)) return;
    try {
      await api.deleteBreak(b.id);
      setBreaks(breaks.filter((x) => x.id !== b.id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>School breaks</h1>
      <p className="page-intro">
        During breaks scheduled by your school — like winter and summer holidays or reading week — the weekly limit on
        off-campus work doesn't apply. Add them here and Within24 leaves those days out of your totals.
      </p>

      <div className="two-column">
        <section aria-labelledby="your-breaks">
          <h2 id="your-breaks">Your breaks</h2>
          {breaks === null && !error && <p className="muted">Loading…</p>}
          {breaks?.length === 0 && <p className="muted">No breaks added yet.</p>}
          <ul className="list">
            {breaks?.map((b) => (
              <li key={b.id} className="list__item">
                <div>
                  <strong>{b.name}</strong>
                  <div className="muted">
                    {formatDate(b.start_date)} – {formatDate(b.end_date)} · {lengthInDays(b)}{" "}
                    {lengthInDays(b) === 1 ? "day" : "days"}
                  </div>
                </div>
                <button type="button" className="link-button link-button--danger" onClick={() => removeBreak(b)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </section>

        <form className="card stack" onSubmit={addBreak}>
          <h2>Add a break</h2>
          <label>
            Name
            <input value={form.name} onChange={update("name")} placeholder="e.g. Winter break" required maxLength={120} />
          </label>
          <label>
            First day
            <input type="date" value={form.start_date} onChange={update("start_date")} required />
          </label>
          <label>
            Last day
            <input type="date" value={form.end_date} onChange={update("end_date")} min={form.start_date} required />
            <span className="hint">Use the dates in your school's academic calendar. Both days are included.</span>
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button button--primary" type="submit" disabled={busy}>
            {busy ? "Adding…" : "Add break"}
          </button>
          <p className="hint">
            Only official breaks count. If you take time off on your own, or are between programs, different rules
            apply — check with your international student office.
          </p>
        </form>
      </div>
    </>
  );
}

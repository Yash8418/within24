import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const COPY = {
  login: {
    title: "Sign in",
    button: "Sign in",
    busy: "Signing in…",
    switchText: "New to Within24?",
    switchLink: "Create an account",
    switchTo: "/register",
  },
  register: {
    title: "Create your account",
    button: "Create account",
    busy: "Creating account…",
    switchText: "Already have an account?",
    switchLink: "Sign in",
    switchTo: "/login",
  },
};

export default function AuthPage({ mode }) {
  const { user, signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "", fullName: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const copy = COPY[mode];

  if (user) return <Navigate to={location.state?.from ?? "/"} replace />;

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "register") await signUp(form.email, form.password, form.fullName);
      else await signIn(form.email, form.password);
      navigate(location.state?.from ?? "/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <section className="auth__intro">
        <p className="wordmark">
          Within<span>24</span>
        </p>
        <h1>Know your hours before you say yes to a shift.</h1>
        <p>
          International students can work up to 24 hours a week off campus during term. Within24 adds up every job —
          store, restaurant, delivery apps — and tells you how many hours you have left.
        </p>
      </section>

      <form className="card auth__form" onSubmit={handleSubmit} noValidate>
        <h2>{copy.title}</h2>
        {mode === "register" && (
          <label>
            Name <span className="optional">(optional)</span>
            <input value={form.fullName} onChange={update("fullName")} autoComplete="name" />
          </label>
        )}
        <label>
          Email
          <input type="email" value={form.email} onChange={update("email")} autoComplete="email" required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={update("password")}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            minLength={mode === "register" ? 8 : undefined}
            required
          />
          {mode === "register" && <span className="hint">At least 8 characters.</span>}
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? copy.busy : copy.button}
        </button>
        <p className="auth__switch">
          {copy.switchText} <Link to={copy.switchTo}>{copy.switchLink}</Link>
        </p>
      </form>
    </main>
  );
}

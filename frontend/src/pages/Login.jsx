import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/** Sample accounts for viva / evaluation walkthrough (optional quick access). */
const SAMPLE_ACCOUNTS = [
  { role: "Invigilator", email: "invigilator@demo.com" },
  { role: "HOD", email: "hod@demo.com" },
  { role: "DEC", email: "dec@demo.com" },
  { role: "Exam Dept", email: "examdept@demo.com" },
  { role: "UFM Committee", email: "ufm@demo.com" },
  { role: "Student", email: "student@demo.com" },
];

export default function Login() {
  const { login, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  if (!loading && isAuthenticated) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError("");
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      setFormError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function signInAs(accountEmail) {
    setEmail(accountEmail);
    setPassword("Demo@123");
    setSubmitting(true);
    setFormError("");
    try {
      await login(accountEmail, "Demo@123");
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      setFormError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-au-surface">
      <section className="relative hidden lg:flex flex-col justify-between bg-au-navy text-white p-12 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(37,99,235,0.35),transparent_45%),radial-gradient(circle_at_80%_70%,rgba(14,165,233,0.25),transparent_40%)]" />
        <div className="relative z-10">
          <div className="inline-flex items-center gap-3 rounded-full bg-white/10 px-4 py-2 text-sm">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            Air University · Examination Integrity
          </div>
          <h1 className="mt-10 text-5xl font-semibold leading-tight tracking-tight">
            VigilantEye
          </h1>
          <p className="mt-5 max-w-md text-lg text-slate-200">
            Institutional UFM portal — live monitoring, AI-assisted detections,
            case review, student clarification, and result controls.
          </p>
        </div>
        <div className="relative z-10 grid gap-2 text-sm text-slate-200">
          <p className="font-medium text-white">Evaluation role shortcuts</p>
          <p className="text-xs text-slate-400">
            For viva walkthroughs. Production users sign in with their own
            credentials on the right.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {SAMPLE_ACCOUNTS.map((item) => (
              <button
                key={item.email}
                type="button"
                disabled={submitting}
                onClick={() => signInAs(item.email)}
                className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-left transition hover:bg-white/15 disabled:opacity-50"
              >
                <span className="block font-semibold text-white">{item.role}</span>
                <span className="text-xs text-slate-300">{item.email}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md rounded-2xl border border-au-border bg-white p-8 shadow-[0_20px_60px_rgba(11,31,58,0.08)]">
          <div className="mb-8">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-au-blue">
              Air University
            </p>
            <h2 className="mt-2 text-3xl font-semibold text-au-navy">Sign in</h2>
            <p className="mt-2 text-slate-500">
              Enter your portal email and password to continue.
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Email
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
                placeholder="you@university.edu"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Password
              </span>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
                placeholder="••••••••"
              />
            </label>

            {formError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {formError}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-au-navy px-4 py-3.5 font-semibold text-white transition hover:bg-au-navy-deep disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Signing in..." : "Sign in to Portal"}
            </button>
          </form>

          <div className="mt-6 grid gap-2 lg:hidden">
            <p className="text-center text-xs text-slate-400">
              Evaluation shortcuts
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SAMPLE_ACCOUNTS.map((item) => (
                <button
                  key={item.email}
                  type="button"
                  disabled={submitting}
                  onClick={() => signInAs(item.email)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 disabled:opacity-50"
                >
                  {item.role}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

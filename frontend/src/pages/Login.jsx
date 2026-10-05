import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import DemoLoginShortcuts from "../components/DemoLoginShortcuts";
import { DEMO_HELPERS_ENABLED } from "../config/demoMode";
import { homePathForRole } from "../config/roleHome";
import { useAuth } from "../context/AuthContext";
import { fetchAuthConfig } from "../services/api";

function loadGoogleScript() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve();
      return;
    }
    const existing = document.getElementById("google-gsi");
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () =>
        reject(new Error("Failed to load Google Sign-In"))
      );
      return;
    }
    const script = document.createElement("script");
    script.id = "google-gsi";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google Sign-In"));
    document.head.appendChild(script);
  });
}

export default function Login() {
  const { login, loginWithGoogle, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [authConfig, setAuthConfig] = useState(null);
  const [configLoading, setConfigLoading] = useState(true);
  const googleBtnRef = useRef(null);

  const mode = authConfig?.auth_mode || "demo";
  const passwordEnabled = Boolean(authConfig?.password_login_enabled);
  const googleEnabled = Boolean(authConfig?.google_auth_enabled);
  const googleClientId = authConfig?.google_client_id || "";
  // Server may disable shortcuts (AUTH_MODE=google); outer DEMO_HELPERS_ENABLED
  // stays compile-time so production builds can tree-shake demo credentials.
  const serverDemoHelpers = Boolean(authConfig?.demo_helpers_enabled);
  const institutionalGoogleOnly = mode === "google" && googleEnabled;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await fetchAuthConfig();
        if (!cancelled) setAuthConfig(cfg);
      } catch {
        if (!cancelled) {
          setAuthConfig({
            auth_mode: "demo",
            password_login_enabled: DEMO_HELPERS_ENABLED,
            google_auth_enabled: false,
            google_client_id: null,
            demo_helpers_enabled: DEMO_HELPERS_ENABLED,
          });
        }
      } finally {
        if (!cancelled) setConfigLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!googleEnabled || !googleClientId || !googleBtnRef.current) return undefined;
    let cancelled = false;

    (async () => {
      try {
        await loadGoogleScript();
        if (cancelled || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          callback: async (response) => {
            if (!response?.credential) {
              setFormError("Google did not return a credential");
              return;
            }
            setSubmitting(true);
            setFormError("");
            try {
              const loggedIn = await loginWithGoogle(response.credential);
              navigate(homePathForRole(loggedIn?.role), { replace: true });
            } catch (err) {
              setFormError(err.message || "Google sign-in failed");
            } finally {
              setSubmitting(false);
            }
          },
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        googleBtnRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "rectangular",
          width: 320,
        });
      } catch (err) {
        if (!cancelled) {
          setFormError(err.message || "Google Sign-In unavailable");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [googleEnabled, googleClientId, loginWithGoogle, navigate]);

  if (!loading && isAuthenticated) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!passwordEnabled) return;
    setFormError("");
    setSubmitting(true);
    try {
      const loggedIn = await login(email.trim(), password);
      navigate(homePathForRole(loggedIn?.role), { replace: true });
    } catch (err) {
      setFormError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function signInAs(accountEmail, demoPassword) {
    if (!DEMO_HELPERS_ENABLED || !serverDemoHelpers) return;
    setEmail(accountEmail);
    setPassword(demoPassword);
    setSubmitting(true);
    setFormError("");
    try {
      const loggedIn = await login(accountEmail, demoPassword);
      navigate(homePathForRole(loggedIn?.role), { replace: true });
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
        {DEMO_HELPERS_ENABLED && serverDemoHelpers ? (
          <DemoLoginShortcuts
            submitting={submitting}
            onSignInAs={signInAs}
            variant="desktop"
          />
        ) : (
          <p className="relative z-10 text-sm text-slate-300">
            {institutionalGoogleOnly
              ? "Sign in with an authorized university Google account."
              : "Sign in with a university-authorized Google account."}
          </p>
        )}
      </section>

      <section className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md rounded-2xl border border-au-border bg-white p-8 shadow-[0_20px_60px_rgba(11,31,58,0.08)]">
          <div className="mb-8">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-au-blue">
              Air University
            </p>
            <h2 className="mt-2 text-3xl font-semibold text-au-navy">
              {institutionalGoogleOnly
                ? "Sign in to the UFM Portal"
                : "Sign in"}
            </h2>
            <p className="mt-2 text-slate-500">
              {institutionalGoogleOnly
                ? "Sign in with an authorized university Google account."
                : googleEnabled
                  ? "Sign in with a university-authorized Google account."
                  : passwordEnabled
                    ? "Enter the portal email and password to continue."
                    : "Authentication is not configured. Contact IT support."}
            </p>
          </div>

          {configLoading ? (
            <p className="text-sm text-slate-500" role="status">
              Loading sign-in options…
            </p>
          ) : null}

          {googleEnabled ? (
            <div className="mb-6 space-y-3">
              <p className="text-sm font-medium text-au-navy">
                Continue with Google
              </p>
              <div
                ref={googleBtnRef}
                className="flex min-h-[44px] justify-center"
                aria-label="Continue with Google"
              />
              {submitting ? (
                <p className="text-center text-xs text-slate-500" role="status">
                  Signing in…
                </p>
              ) : null}
            </div>
          ) : null}

          {googleEnabled && passwordEnabled ? (
            <div className="mb-6 space-y-2">
              <div className="flex items-center gap-3 text-xs uppercase tracking-wide text-slate-400">
                <span className="h-px flex-1 bg-slate-200" />
                development options
                <span className="h-px flex-1 bg-slate-200" />
              </div>
              <p className="text-center text-[11px] text-slate-400">
                Password / evaluation logins are for local testing only
                (AUTH_MODE=both).
              </p>
            </div>
          ) : null}

          {passwordEnabled ? (
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

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-xl bg-au-navy px-4 py-3.5 font-semibold text-white transition hover:bg-au-navy-deep disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Signing in..." : "Sign in to Portal"}
              </button>
            </form>
          ) : null}

          {formError ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {formError}
            </div>
          ) : null}

          {DEMO_HELPERS_ENABLED && serverDemoHelpers ? (
            <DemoLoginShortcuts
              submitting={submitting}
              onSignInAs={signInAs}
              variant="mobile"
            />
          ) : null}
        </div>
      </section>
    </div>
  );
}

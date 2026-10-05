/**
 * Development / viva login shortcuts — imported only by Login when demo helpers
 * are enabled. Keep credentials out of the default production UI path.
 */
const SAMPLE_ACCOUNTS = [
  { role: "Invigilator", email: "invigilator@demo.com" },
  { role: "HOD", email: "hod@demo.com" },
  { role: "DEC", email: "dec@demo.com" },
  { role: "Exam Dept", email: "examdept@demo.com" },
  { role: "UFM Committee", email: "ufm@demo.com" },
  { role: "Student", email: "student@demo.com" },
];

const DEMO_PASSWORD = "Demo@123";

export default function DemoLoginShortcuts({
  submitting,
  onSignInAs,
  variant = "desktop",
}) {
  if (variant === "mobile") {
    return (
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
              onClick={() => onSignInAs(item.email, DEMO_PASSWORD)}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 disabled:opacity-50"
            >
              {item.role}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
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
            onClick={() => onSignInAs(item.email, DEMO_PASSWORD)}
            className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-left transition hover:bg-white/15 disabled:opacity-50"
          >
            <span className="block font-semibold text-white">{item.role}</span>
            <span className="text-xs text-slate-300">{item.email}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

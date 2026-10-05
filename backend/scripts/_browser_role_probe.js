/**
 * Multi-role responsive probe for acceptance gate.
 * Run inside the browser page after AUTH_MODE=both is enabled.
 * Does not print passwords.
 */
(async () => {
  const roles = [
    {
      email: "hod@demo.com",
      label: "HOD",
      pages: [
        "/app/dashboard",
        "/app/cases",
        "/app/cases/11",
        "/app/evidence",
        "/app/reports",
        "/app/audit",
        "/app/notifications",
        "/app/help",
      ],
    },
    {
      email: "dec@demo.com",
      label: "DEC",
      pages: [
        "/app/dashboard",
        "/app/cases",
        "/app/cases/11",
        "/app/evidence",
        "/app/reports",
      ],
    },
    {
      email: "examdept@demo.com",
      label: "EXAM",
      pages: [
        "/app/dashboard",
        "/app/cases",
        "/app/result-controls",
        "/app/reports",
        "/app/audit",
      ],
    },
    {
      email: "ufm@demo.com",
      label: "UFM",
      pages: [
        "/app/dashboard",
        "/app/cases",
        "/app/result-controls",
        "/app/reports",
      ],
    },
    {
      email: "student@demo.com",
      label: "STUDENT",
      pages: [
        "/app/dashboard",
        "/app/cases",
        "/app/clarification",
        "/app/notifications",
        "/app/help",
      ],
    },
    {
      email: "admin@demo.com",
      label: "ADMIN",
      pages: [
        "/app/admin/dashboard",
        "/app/admin/users",
        "/app/admin/system",
        "/app/admin/audit",
        "/app/notifications",
      ],
    },
  ];

  const password = "Demo@123";
  const issues = [];
  const ok = [];

  async function login(email) {
    const r = await fetch("http://127.0.0.1:8000/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const body = await r.json();
    if (!r.ok) throw new Error(`${email} ${r.status}`);
    localStorage.setItem("ve_token", body.access_token);
    localStorage.setItem("ve_user", JSON.stringify(body.user));
  }

  function probe(role, path) {
    const overflowX =
      Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) >
      Math.ceil(innerWidth) + 1;
    const clippedMain = [];
    for (const el of Array.from(
      document.querySelectorAll("main a, main button, main input, main select")
    ).slice(0, 220)) {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0) continue;
      if (rect.right > innerWidth + 2 || rect.left < -2) {
        clippedMain.push(
          (el.getAttribute("aria-label") || el.textContent || "")
            .trim()
            .slice(0, 40)
        );
      }
    }
    const missing = Array.from(
      document.querySelectorAll("main input,main select,main textarea")
    )
      .filter((el) => {
        if (el.type === "hidden") return false;
        const id = el.id;
        return !(
          el.getAttribute("aria-label") ||
          el.getAttribute("aria-labelledby") ||
          (id && document.querySelector(`label[for="${CSS.escape(id)}"]`)) ||
          el.closest("label")
        );
      })
      .map((el) => el.name || el.id || el.placeholder || el.type);
    const unlabeled = Array.from(document.querySelectorAll("main button")).filter(
      (b) =>
        !(b.textContent || "").trim() &&
        !b.getAttribute("aria-label") &&
        !b.getAttribute("title")
    ).length;
    const rec = {
      role,
      path,
      overflowX,
      clippedMain: clippedMain.slice(0, 5),
      missingLabels: missing.slice(0, 5),
      unlabeledIconButtons: unlabeled,
      w: innerWidth,
    };
    if (
      overflowX ||
      clippedMain.length ||
      missing.length ||
      unlabeled
    ) {
      issues.push(rec);
    } else {
      ok.push(`${role}:${path}`);
    }
  }

  // Probe CURRENT role pages only (caller switches role + reloads between batches)
  const roleLabel = (JSON.parse(localStorage.getItem("ve_user") || "{}").role ||
    "UNKNOWN");
  const pages =
    roles.find((r) => r.label === roleLabel || r.email.includes(roleLabel.toLowerCase()))
      ?.pages || [];
  window.__veProbeLogin = login;
  window.__veProbePages = async (label, pageList) => {
    const localIssues = [];
    const localOk = [];
    for (const path of pageList) {
      history.pushState({}, "", path);
      window.dispatchEvent(new PopStateEvent("popstate"));
      await new Promise((r) => setTimeout(r, 1000));
      const before = issues.length;
      probe(label, path);
      if (issues.length > before) localIssues.push(issues[issues.length - 1]);
      else localOk.push(`${label}:${path}`);
    }
    return { localIssues, localOk, viewport: { w: innerWidth, h: innerHeight } };
  };
  return JSON.stringify({
    installed: true,
    currentRole: roleLabel,
    knownPages: pages,
  });
})()

/**
 * Layout + a11y smoke probe for acceptance gate.
 * Call as: await window.__veProbe(pages)
 * Does not print tokens.
 */
window.__veProbe = async function veProbe(pages) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = [];
  for (const path of pages) {
    history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
    await sleep(900);
    const docEl = document.documentElement;
    const overflowX = Math.max(0, docEl.scrollWidth - window.innerWidth);
    const issues = [];
    if (overflowX > 2) issues.push(`horizontal_overflow:${overflowX}`);

    let off = 0;
    for (const el of document.querySelectorAll("button, a, input, select, textarea")) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > window.innerWidth + 6) off += 1;
    }
    if (off) issues.push(`controls_right_clip:${off}`);

    const iconButtons = [...document.querySelectorAll("button")].filter((b) => {
      const t = (b.textContent || "").trim();
      return t.length === 0 || t.length <= 2;
    });
    const unlabeled = iconButtons.filter(
      (b) => !(b.getAttribute("aria-label") || b.getAttribute("title"))
    );
    if (unlabeled.length) issues.push(`icon_buttons_unlabeled:${unlabeled.length}`);

    const h1 = (document.querySelector("h1")?.textContent || "").trim().slice(0, 90);
    const cards = document.querySelector(".portal-data-cards, .portal-case-cards");
    const table = document.querySelector(".portal-table-desktop");
    out.push({
      path,
      h1,
      overflowX,
      issues,
      cardsDisplay: cards ? getComputedStyle(cards).display : null,
      tableDisplay: table ? getComputedStyle(table).display : null,
      dialogs: document.querySelectorAll("[role=dialog], [role=alertdialog]").length,
      interactive: document.querySelectorAll(
        'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      ).length,
    });
  }
  return {
    role: (() => {
      try {
        return JSON.parse(localStorage.getItem("ve_user") || "{}").role;
      } catch {
        return null;
      }
    })(),
    viewport: { w: window.innerWidth, h: window.innerHeight },
    pages: out,
  };
};

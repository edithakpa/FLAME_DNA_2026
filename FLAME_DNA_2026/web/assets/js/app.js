/* FLAME DNA — routeur SPA (hash), transitions de page, menu, thème */
(function () {
  "use strict";
  const FD = window.FD;
  const view = FD.$("#view");
  let current = null, cleanup = null, navToken = 0;

  /* pastille active qui glisse d'un item à l'autre */
  function moveGlider(route) {
    const nav = FD.$("#nav"), glider = FD.$(".nav-glider");
    const link = FD.$(`a[data-route="${route}"]`, nav);
    FD.$$("a", nav).forEach((a) => a.classList.toggle("active", a === link));
    if (!link) return (glider.style.opacity = 0);
    glider.style.opacity = 1;
    if (window.innerWidth <= 760) {
      glider.style.width = link.offsetWidth + "px";
      glider.style.transform = `translateX(${link.offsetLeft}px)`;
    } else {
      glider.style.width = "";
      glider.style.transform = `translateY(${link.offsetTop}px)`;
    }
  }

  async function navigate() {
    const route = (location.hash.replace(/^#\/?/, "").split("?")[0] || "overview");
    const page = FD.pages[route] || FD.pages.overview;
    const key = FD.pages[route] ? route : "overview";
    if (key === current) return;
    const token = ++navToken;
    moveGlider(key);
    FD.closeDrawer();
    if (current) {
      view.classList.remove("entering");
      view.classList.add("leaving");
      await new Promise((r) => setTimeout(r, 170));
      if (token !== navToken) return;
    }
    if (typeof cleanup === "function") try { cleanup(); } catch (e) {}
    cleanup = null;
    current = key;
    FD.$("#pageTitle").textContent = page.title;
    FD.$("#crumbPage").textContent = page.title;
    FD.$("#pageSubtitle").textContent = page.subtitle;
    document.title = `${page.title} · FLAME DNA`;
    view.classList.remove("leaving");
    view.innerHTML = "";
    view.classList.add("entering");
    window.scrollTo({ top: 0, behavior: "smooth" });
    try {
      cleanup = await page.render(view);
    } catch (e) {
      console.error(e);
      view.innerHTML = `<div class="card empty"><i class="fa-solid fa-triangle-exclamation"></i>Unable to load this section.<br><small class="mono">${FD.esc(e.message)}</small><br><br><span class="muted">Tip: serve the folder over HTTP (e.g. <code>python -m http.server</code>) or deploy on Vercel — browsers block local JSON files opened with file://</span></div>`;
    }
    setTimeout(() => view.classList.remove("entering"), 450);
  }

  /* bascule de thème + re-rendu des graphiques (couleurs de grille) */
  FD.$("#themeToggle").addEventListener("click", () => {
    FD.setTheme(FD.theme() === "dark" ? "light" : "dark");
  });

  /* statut de surveillance partagé (menu + en-tête) — mis à jour par le moniteur global */
  FD.on("monitor", (s) => {
    const cls = ["", "", "warn", "danger"][s.level] || "";
    const chip = FD.$("#headerStatus"), pill = FD.$("#sidebarLive");
    [chip, pill].forEach((el) => {
      el.querySelector(".dot").className = "dot " + cls;
      el.querySelector(".lbl").textContent = s.short;
    });
  });
  FD.$("#headerStatus").addEventListener("click", () => (location.hash = "#/monitoring"));

  window.addEventListener("hashchange", navigate);
  window.addEventListener("resize", () => moveGlider(current));
  document.addEventListener("DOMContentLoaded", () => {});
  if (!location.hash) history.replaceState(null, "", "#/overview");
  navigate();
  // démarre le moteur de surveillance en tâche de fond (alimente l'en-tête)
  FD.monitor && FD.monitor.start();
})();

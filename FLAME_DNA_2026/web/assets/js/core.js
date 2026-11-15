/* FLAME DNA — utilitaires communs (DOM, données, animations, routeur, thème) */
(function () {
  "use strict";
  const FD = (window.FD = window.FD || {});
  FD.pages = FD.pages || {};

  /* ---------- DOM ---------- */
  FD.$ = (sel, root = document) => root.querySelector(sel);
  FD.$$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  FD.h = (html) => {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  };
  FD.esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------- couleurs de séries (lisibles en sombre et clair) ---------- */
  FD.palette = ["#F36B21", "#5BCFE3", "#D9A441", "#8E83F5", "#3DBE8B", "#EF5350", "#E58AC0", "#9CB0C9", "#B5D86A", "#FF9A4D", "#4F8FEA", "#C49A6C", "#7ED6C4"];
  FD.cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /* ---------- données (cache) ---------- */
  const cache = new Map();
  FD.data = (path) => {
    if (!cache.has(path)) {
      cache.set(path, fetch(path).then((r) => {
        if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
        return r.json();
      }).catch((e) => { cache.delete(path); throw e; }));
    }
    return cache.get(path);
  };
  FD.saffire = () => FD.data("data/saffire_index.json");
  FD.series = (slug) => FD.data(`data/series/${slug}.json`);
  FD.publications = () => FD.data("data/publications.json");
  FD.knowledge = () => FD.data("data/knowledge.json");

  /* ---------- formatage ---------- */
  FD.fmt = (v, d = 1) => {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Number(v).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: Math.min(d, Math.abs(v) < 10 && d > 0 ? d : 0) });
  };
  FD.fmtInt = (v) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));

  /* ---------- compteur animé : défile des valeurs avant la vraie ---------- */
  FD.countUp = (node, target, { decimals = 0, duration = 1500, prefix = "", suffix = "", delay = 0 } = {}) => {
    if (!node) return;
    if (target === null || target === undefined || Number.isNaN(+target)) { node.textContent = "—"; return; }
    target = +target;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const show = (v) => (node.innerHTML = prefix + FD.fmt(v, decimals) + suffix);
    if (reduce) return show(target);
    const mag = Math.max(1, Math.abs(target));
    const start = performance.now() + delay;
    show(0);
    const tick = (now) => {
      const p = Math.min(1, Math.max(0, (now - start) / duration));
      if (p <= 0) return requestAnimationFrame(tick);
      const eased = 1 - Math.pow(1 - p, 4);
      let v;
      if (p < 0.55) {
        // phase « machine à sous » : valeurs brouillées qui convergent
        const jitter = (1 - p / 0.55) * mag * 0.9;
        v = target * eased + (Math.random() - 0.5) * jitter;
        if (target >= 0) v = Math.abs(v);
      } else v = target * eased + (target - target * eased) * 0;
      show(p >= 1 ? target : v);
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  /* anime tous les [data-count] d'un conteneur */
  FD.animateCounts = (root) => {
    FD.$$("[data-count]", root).forEach((n, i) => {
      FD.countUp(n, parseFloat(n.dataset.count), {
        decimals: +(n.dataset.dec || 0), suffix: n.dataset.suffix || "", prefix: n.dataset.prefix || "",
        delay: i * 70, duration: 1300 + Math.random() * 500,
      });
    });
  };

  /* ---------- notifications ---------- */
  FD.toast = (title, text = "", kind = "info", ms = 4200) => {
    const icons = { info: "fa-circle-info", ok: "fa-circle-check", warn: "fa-triangle-exclamation", danger: "fa-fire" };
    const colors = { info: "var(--cyan)", ok: "var(--ok)", warn: "var(--warn)", danger: "var(--danger)" };
    const t = FD.h(`<div class="toast"><i class="fa-solid ${icons[kind]}" style="color:${colors[kind]}"></i><div><b>${FD.esc(title)}</b>${FD.esc(text)}</div></div>`);
    FD.$("#toasts").appendChild(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 320); }, ms);
  };

  /* ---------- panneau latéral de détail ---------- */
  FD.drawer = (html) => {
    let bd = FD.$(".drawer-backdrop"), dr = FD.$(".drawer");
    if (!bd) {
      bd = FD.h(`<div class="drawer-backdrop"></div>`);
      dr = FD.h(`<aside class="drawer" role="dialog" aria-modal="true"></aside>`);
      document.body.append(bd, dr);
      bd.addEventListener("click", FD.closeDrawer);
      document.addEventListener("keydown", (e) => e.key === "Escape" && FD.closeDrawer());
    }
    dr.innerHTML = `<button class="btn sm ghost close" aria-label="Close"><i class="fa-solid fa-xmark"></i></button>` + html;
    dr.querySelector(".close").onclick = FD.closeDrawer;
    requestAnimationFrame(() => { bd.classList.add("open"); dr.classList.add("open"); });
    dr.scrollTop = 0;
    return dr;
  };
  FD.closeDrawer = () => { FD.$(".drawer-backdrop")?.classList.remove("open"); FD.$(".drawer")?.classList.remove("open"); };

  /* ---------- bus d'événements (statut surveillance partagé) ---------- */
  const listeners = {};
  FD.on = (ev, fn) => ((listeners[ev] = listeners[ev] || []).push(fn));
  FD.off = (ev, fn) => (listeners[ev] = (listeners[ev] || []).filter((f) => f !== fn));
  FD.emit = (ev, payload) => (listeners[ev] || []).forEach((fn) => fn(payload));

  /* ---------- thème ---------- */
  FD.setTheme = (t) => {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("fd-theme", t); } catch (e) {}
    FD.emit("theme", t);
  };
  FD.theme = () => document.documentElement.dataset.theme;

  /* ---------- statistiques ---------- */
  FD.stats = {
    mean: (a) => a.reduce((s, v) => s + v, 0) / (a.length || 1),
    std: (a) => { const m = FD.stats.mean(a); return Math.sqrt(FD.stats.mean(a.map((v) => (v - m) ** 2))); },
    clamp: (v, a, b) => Math.max(a, Math.min(b, v)),
  };

  /* ---------- export CSV ---------- */
  FD.download = (name, text, mime = "text/csv") => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: mime }));
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  /* ---------- étiquettes lisibles des métriques communes ---------- */
  FD.METRICS = {
    flame_duration_s: { label: "Flame duration", unit: "s", dec: 1, icon: "fa-stopwatch", good: "low", desc: "Time the flame signal stays above 10% of its peak after ignition (radiometers, or sample thermocouples > 100 °C when radiometers are not resolved)." },
    radiometer_rise_mw_cm2: { label: "Radiative heat-flux rise", unit: "mW/cm²", dec: 1, icon: "fa-sun", good: "low", desc: "Peak radiometer signal above the pre-ignition baseline — a proxy for flame size and heat release." },
    radiant_dose_mj_cm2: { label: "Radiant dose", unit: "mJ/cm²", dec: 0, icon: "fa-radiation", good: "low", desc: "Time-integrated radiometer signal above baseline during the flame." },
    sample_temp_peak_c: { label: "Peak sample temperature", unit: "°C", dec: 0, icon: "fa-temperature-high", good: "low", desc: "Maximum of the six sample-surface thermocouples (TC7–TC12)." },
    plume_temp_peak_c: { label: "Peak plume temperature", unit: "°C", dec: 1, icon: "fa-smog", good: "low", desc: "Maximum of the six downstream plume thermocouples (TC1–TC6)." },
    o2_drop_pct: { label: "O₂ consumed", unit: "% vol", dec: 3, icon: "fa-lungs", good: "low", desc: "Initial O₂ concentration minus the minimum measured in the Cygnus cabin." },
    co2_rise_pct: { label: "CO₂ produced", unit: "% vol", dec: 3, icon: "fa-cloud", good: "low", desc: "Maximum CO₂ minus pre-test level — combustion products released into the cabin." },
    pressure_rise_psia: { label: "Pressure rise", unit: "psia", dec: 3, icon: "fa-gauge-high", good: "low", desc: "Cabin pressure increase over the test (thermal expansion of cabin gas)." },
    airflow_median_cm_s: { label: "Imposed airflow", unit: "cm/s", dec: 1, icon: "fa-wind", good: null, desc: "Median anemometer reading — the forced flow that feeds the flame in microgravity." },
    sample_front_transit_s: { label: "Front transit (TC7→TC12)", unit: "s", dec: 1, icon: "fa-arrow-right-long", good: null, desc: "Delay between the first and last sample thermocouple peaks (> 60 °C) — an indicator of flame-front travel time." },
    o2_initial_pct: { label: "Initial O₂", unit: "% vol", dec: 2, icon: "fa-atom", good: null, desc: "Cabin oxygen concentration before ignition." },
    pressure_mean_psia: { label: "Mean cabin pressure", unit: "psia", dec: 2, icon: "fa-compress", good: null, desc: "Average ambient pressure in the test section." },
  };
})();

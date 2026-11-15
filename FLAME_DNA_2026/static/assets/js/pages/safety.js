/* FLAME DNA — Sécurité incendie des missions + utilité terrestre
   - carte des atmosphères d'habitat (O₂ / pression)
   - simulateur « what-if » ancré sur les mesures SAFFIRE
   - transferts espace → Terre avec données chiffrées */
(function () {
  const FD = window.FD;
  const CYGNUS_M3 = 27; // volume pressurisé approximatif d'un Cygnus amélioré (ordre de grandeur)
  const w = { mat: "SAFFIRE-I-S1", o2: 21, flow: 20, vol: 75 };

  FD.pages.safety = {
    title: "Mission Fire Safety",
    subtitle: "From the ISS to lunar bases and pressurized rovers — what SAFFIRE data mean for crew habitats, and what they bring back to firefighters on Earth.",
    async render(view) {
      const [idx, kn] = await Promise.all([FD.saffire(), FD.knowledge()]);
      const S = idx.samples, mats = S.filter((s) => s.metrics.flame_confidence === "high");
      view.innerHTML = `
      <div class="grid">
        <article class="card media-card span-4 lift" style="--i:0"><img src="assets/img/apollo1.jpg" alt="Apollo 1 command module after the 1967 fire"><div class="body"><span class="tag danger">1967 · lesson learned</span><h4 style="margin-top:8px">Apollo 1: oxygen + flammable materials</h4><p>100 % O₂ at ~16.7 psia turned a small electrical spark into a fatal fire within seconds. Every spacecraft material has been flammability-screened since.</p></div></article>
        <article class="card media-card span-4 lift" style="--i:1"><img src="assets/img/flame-earth-vs-micro.jpg" alt="Flame on Earth vs in microgravity" style="object-position:center 30%"><div class="body"><span class="tag cyan">Physics</span><h4 style="margin-top:8px">No buoyancy, different fire</h4><p>Without gravity, flames don't rise: they creep along surfaces, fed only by the ventilation flow — slower, cooler, harder to see and to detect.</p></div></article>
        <article class="card media-card span-4 lift" style="--i:2"><img src="assets/img/firefighter.jpg" alt="Firefighter in protective equipment"><div class="body"><span class="tag ok">Back on Earth</span><h4 style="margin-top:8px">Space fire research protects firefighters</h4><p>Water-mist extinguishers, better smoke detectors, lighter breathing gear and flame-resistant clothing all draw on space fire-safety work.</p></div></article>

        <div class="span-12 section-title">Habitat atmospheres & flammability risk</div>
        <section class="card span-7" style="--i:3"><div class="card-head"><div><h3>Where each habitat sits</h3><div class="sub">Oxygen fraction drives flammability; total pressure mostly drives spacewalk prep</div></div><span class="card-icon"><i class="fa-solid fa-map-location-dot"></i></span></div><div id="atmoMap"></div></section>
        <section class="card span-5" style="--i:4"><div class="card-head"><div><h3>Habitat table</h3><div class="sub">Relative flame-growth indicator vs. ISS (illustrative scaling ∝ (O₂/21)^1.6)</div></div></div>
          <table class="data risk-table"><thead><tr><th>Habitat</th><th>O₂ %</th><th>psia</th><th>ppO₂</th><th>Index</th></tr></thead><tbody>
          ${kn.habitats.map((h) => { const idxv = Math.pow(h.o2 / 21, 1.6); return `<tr><td>${FD.esc(h.name)}</td><td class="mono">${h.o2}</td><td class="mono">${h.p}</td><td class="mono">${FD.fmt((h.o2 / 100) * h.p, 1)}</td><td><span class="tag ${idxv > 3 ? "danger" : idxv > 1.3 ? "warn" : "ok"}">×${FD.fmt(idxv, 1)}</span></td></tr>`; }).join("")}
          </tbody></table>
          <p class="note"><i class="fa-solid fa-circle-info"></i><span>Exploration habitats trade lower pressure for higher O₂ % — fewer hours of pre-breathing before spacewalks, but more materials become flammable.</span></p></section>

        <div class="span-12 section-title">What-if simulator — anchored on real SAFFIRE measurements</div>
        <section class="card span-5" style="--i:5"><div class="card-head"><div><h3>Scenario</h3><div class="sub">Pick a measured fire, then move it into another habitat</div></div><span class="card-icon"><i class="fa-solid fa-sliders"></i></span></div>
          <label class="muted" style="font-size:12px">Reference fire (measured)</label>
          <select class="select" id="wMat" style="margin:6px 0 14px">${mats.map((s) => `<option value="${s.id}" ${s.id === w.mat ? "selected" : ""}>${s.id}${s.meta.material ? " — " + s.meta.material + ", " + s.meta.flow_direction : ""} (${FD.fmt(s.metrics.radiometer_rise_mw_cm2, 0)} mW/cm²)</option>`).join("")}</select>
          ${slider("o2", "Cabin oxygen", 15, 40, 0.5, "%")}
          ${slider("flow", "Ventilation flow", 0, 40, 1, "cm/s")}
          ${slider("vol", "Free cabin volume", 8, 120, 1, "m³")}
          <div class="chips" style="margin-top:6px">
            <span class="chip" data-preset="iss">ISS module</span><span class="chip" data-preset="lunar">Lunar habitat</span><span class="chip" data-preset="rover">Pressurized rover</span><span class="chip" data-preset="vent">Ventilation off</span>
          </div></section>
        <section class="card span-7" style="--i:6"><div class="card-head"><div><h3>Projected outcome</h3><div class="sub" id="wSub"></div></div><span class="card-icon"><i class="fa-solid fa-chart-line"></i></span></div>
          <div class="whatif-out">
            <div class="metric"><div class="k"><i class="fa-solid fa-fire"></i> Flame-growth index</div><div class="v" id="oIdx">—</div></div>
            <div class="metric"><div class="k"><i class="fa-solid fa-lungs"></i> O₂ after the burn</div><div class="v" id="oO2">—</div></div>
            <div class="metric"><div class="k"><i class="fa-solid fa-cloud"></i> CO₂ added</div><div class="v" id="oCO2">—</div></div>
          </div>
          <div id="wChart" style="margin-top:12px"></div>
          <div id="wVerdict" class="question-box" style="margin-top:10px"></div>
          <p class="note"><i class="fa-solid fa-flask-vial"></i><span>Gas changes are scaled from the measured SAFFIRE O₂/CO₂ balance in a Cygnus (~${CYGNUS_M3} m³) by volume ratio. The growth index is an <b>illustrative</b> O₂ and flow scaling — not a validated flammability model.</span></p></section>

        <div class="span-12 section-title">Benefits on Earth</div>
        <section class="card span-6" style="--i:7"><div class="card-head"><div><h3>From orbit to the fire station</h3><div class="sub">Space fire-safety knowledge that protects people on Earth</div></div><span class="card-icon"><i class="fa-solid fa-earth-africa"></i></span></div>
          ${kn.transfers.map((t) => `<div class="transfer"><div class="side"><b><i class="fa-solid fa-rocket" style="color:var(--cyan)"></i> Space</b>${FD.esc(t.space)}</div><div class="arrow"><i class="fa-solid ${t.icon}"></i></div><div class="side"><b><i class="fa-solid fa-house" style="color:var(--ok)"></i> Earth</b>${FD.esc(t.earth)}</div></div>`).join("")}</section>
        <section class="card span-6" style="--i:8"><div class="card-head"><div><h3>The same fire in an Earth room</h3><div class="sub">Measured SAFFIRE gas balance rescaled to a closed 30 m³ room (bedroom-size)</div></div><span class="card-icon"><i class="fa-solid fa-house-chimney-crack"></i></span></div>
          <div id="roomChart"></div>
          <p class="note"><i class="fa-solid fa-circle-info"></i><span>Pure gas-balance scaling (no buoyancy, no leakage). It shows why closed compartments — submarines, aircraft cabins, small apartments — degrade quickly and why early chemical detection matters.</span></p></section>
        <section class="card span-6" style="--i:9"><div class="card-head"><div><h3>Measure the surface, not just the air</h3><div class="sub">Peak sample-surface vs. plume-gas temperature (°C) — samples with sustained flames</div></div><span class="card-icon"><i class="fa-solid fa-temperature-high"></i></span></div><div id="surfChart"></div>
          <p class="note"><i class="fa-solid fa-lightbulb"></i><span>Surfaces reach ~1000 °C while plume gas stays near 100 °C: heat detectors placed in the air respond late — a lesson for both spacecraft and building fire detection.</span></p></section>
        <section class="card span-6" style="--i:10"><div class="card-head"><div><h3>Fire-safety milestones</h3><div class="sub">Why this research exists</div></div><span class="card-icon"><i class="fa-solid fa-timeline"></i></span></div>
          <ul class="timeline" style="max-height:none">
            ${[[1967, "Apollo 1 fire — pure-oxygen cabin; leads to material flammability testing and flame-resistant fabrics", 3], [1990, "SSCE on the Space Shuttle — first systematic flame-spread studies over solids in microgravity", 1], [1997, "Mir fire from an oxygen-generator canister — a real fire on a crewed station", 3], [2003, "MIST — water-mist suppression studied in orbit", 1], [2011, "BASS on the ISS — solid-fuel flammability and extinction", 1], [2016, "SAFFIRE-I & II — first large-scale spacecraft fires, inside Cygnus", 2], [2017, "SAFFIRE-III — large-scale flame spread with different ventilation", 2], [2022, "SoFIE on the ISS — ignition & extinction for exploration atmospheres", 1], ["Next", "Artemis-era lunar habitats & rovers at higher O₂ % — the risk FLAME DNA helps quantify", 0]].map(([y, t, l]) => `<li class="l${l}"><span class="mk"></span><div class="t">${y}</div><div class="m">${t}</div></li>`).join("")}
          </ul></section>
      </div>`;

      drawAtmoMap(kn.habitats);
      // Terre : pièce de 30 m³
      const burned = S.filter((s) => s.metrics.flame_confidence === "high" && s.metrics.co2_rise_pct > 0.005);
      FD.charts.bar(FD.$("#roomChart"), { labels: burned.map((s) => s.mission.replace("SAFFIRE-", "S-") + " " + s.sample), series: [{ name: "O₂ drop in 30 m³ room", values: burned.map((s) => s.metrics.o2_drop_pct * (CYGNUS_M3 / 30)), color: "#5BCFE3" }, { name: "CO₂ rise in 30 m³ room", values: burned.map((s) => s.metrics.co2_rise_pct * (CYGNUS_M3 / 30)), color: "#F36B21" }], unit: "% vol", height: 240, rotate: true });
      const hot = S.filter((s) => (s.metrics.sample_temp_peak_c || 0) > 100);
      FD.charts.bar(FD.$("#surfChart"), { labels: hot.map((s) => s.mission.replace("SAFFIRE-", "S-") + " " + s.sample), series: [{ name: "Sample surface (TC7–12)", values: hot.map((s) => s.metrics.sample_temp_peak_c), color: "#F36B21" }, { name: "Plume gas (TC1–6)", values: hot.map((s) => s.metrics.plume_temp_peak_c), color: "#9CB0C9" }], unit: "°C", height: 240 });

      // simulateur
      const PRE = { iss: { o2: 21, flow: 15, vol: 75 }, lunar: { o2: 34, flow: 12, vol: 45 }, rover: { o2: 34, flow: 10, vol: 12 }, vent: { flow: 0 } };
      const upd = () => {
        const s = S.find((x) => x.id === w.mat), m = s.metrics;
        const fO2 = (o) => Math.pow(o / 21, 1.6);
        const fFlow = (f) => (f < 2 ? 0.05 + 0.1 * f : f < 5 ? 0.25 + 0.15 * (f - 2) : Math.min(1.35, Math.sqrt(f / (m.airflow_median_cm_s || 20))));
        const gi = fO2(w.o2) * fFlow(w.flow) / (fO2(m.o2_initial_pct || 21) * fFlow(m.airflow_median_cm_s || 20));
        const scale = (CYGNUS_M3 / w.vol) * Math.max(0, gi);
        const o2After = w.o2 - (m.o2_drop_pct || 0) * scale, co2 = (m.co2_rise_pct || 0) * scale;
        FD.countUp(FD.$("#oIdx"), gi, { decimals: 2, prefix: "×", duration: 700 });
        FD.countUp(FD.$("#oO2"), o2After, { decimals: 2, suffix: " <small>%</small>", duration: 700 });
        FD.countUp(FD.$("#oCO2"), co2, { decimals: 3, prefix: "+", suffix: " <small>%</small>", duration: 700 });
        FD.$("#wSub").textContent = `${s.id} measured at ${FD.fmt(m.o2_initial_pct, 1)} % O₂, ${FD.fmt(m.airflow_median_cm_s, 0)} cm/s → moved to ${w.o2} % O₂, ${w.flow} cm/s, ${w.vol} m³`;
        const xs = [], y1 = [], y2 = [];
        for (let o = 15; o <= 40; o += 0.5) { xs.push(o); y1.push(fO2(o) * fFlow(w.flow) / (fO2(m.o2_initial_pct || 21) * fFlow(m.airflow_median_cm_s || 20))); y2.push(fO2(o) * fFlow(0) / (fO2(m.o2_initial_pct || 21) * fFlow(m.airflow_median_cm_s || 20))); }
        FD.charts.line(FD.$("#wChart"), { series: [{ name: `Growth index at ${w.flow} cm/s`, x: xs, y: y1, color: "#F36B21", area: true }, { name: "Ventilation off", x: xs, y: y2, color: "#5BCFE3", dash: "5 4" }], height: 200, xLabel: "cabin O₂ (%)", xName: "O₂", xUnit: " %", yLabel: "× measured fire", markers: [{ x: 21, label: "ISS", color: "var(--ok)" }, { x: 34, label: "Exploration", color: "var(--danger)" }, { x: w.o2, label: "you", color: "var(--accent)" }], yMin: 0, animate: false });
        const v = FD.$("#wVerdict");
        v.innerHTML = gi < 0.3 ? `<i class="fa-solid fa-wind" style="color:var(--cyan)"></i> <b>Near extinction:</b> with so little airflow, the flame is starved of oxygen — why shutting down ventilation is a first response in microgravity.`
          : gi < 1.2 ? `<i class="fa-solid fa-shield-heart" style="color:var(--ok)"></i> <b>Comparable to the measured fire.</b> Detection thresholds tuned on SAFFIRE data remain representative.`
          : gi < 2.5 ? `<i class="fa-solid fa-triangle-exclamation" style="color:var(--warn)"></i> <b>Faster, larger fire than measured.</b> Materials accepted for the ISS may need re-screening at this O₂ level.`
          : `<i class="fa-solid fa-fire" style="color:var(--danger)"></i> <b>Severe escalation.</b> Expect rapid spread and cabin-wide O₂/CO₂ changes — detection must trigger within seconds, and material choices are critical.`;
        if (scale > 0 && o2After < 19.5 && w.o2 >= 19.5) v.innerHTML += `<br><i class="fa-solid fa-lungs" style="color:var(--danger)"></i> In this small volume the cabin O₂ would fall below 19.5 % — breathing masks required.`;
      };
      FD.$("#wMat").onchange = (e) => { w.mat = e.target.value; upd(); };
      FD.$$("input[data-w]").forEach((inp) => inp.addEventListener("input", () => { w[inp.dataset.w] = +inp.value; FD.$(`#v-${inp.dataset.w}`).textContent = inp.value; upd(); }));
      FD.$$("[data-preset]").forEach((c) => c.onclick = () => {
        Object.assign(w, PRE[c.dataset.preset]);
        ["o2", "flow", "vol"].forEach((k) => { FD.$(`input[data-w="${k}"]`).value = w[k]; FD.$(`#v-${k}`).textContent = w[k]; });
        FD.$$("[data-preset]").forEach((x) => x.classList.toggle("on", x === c));
        upd();
      });
      upd();
    },
  };

  function slider(k, label, min, max, step, unit) {
    return `<div style="margin-bottom:12px"><div style="display:flex;justify-content:space-between;font-size:12.5px"><span class="muted">${label}</span><b class="mono"><span id="v-${k}">${w[k]}</span> ${unit}</b></div><input type="range" class="slider" data-w="${k}" min="${min}" max="${max}" step="${step}" value="${w[k]}"></div>`;
  }

  function drawAtmoMap(habs) {
    const el = FD.$("#atmoMap");
    const W = Math.max(300, el.clientWidth), H = 300, P = { l: 46, r: 20, t: 16, b: 36 };
    const sx = (o) => P.l + ((o - 15) / (100 - 15)) * (W - P.l - P.r), sy = (p) => H - P.b - (p / 18) * (H - P.t - P.b);
    const col = { earth: "var(--ok)", space: "var(--cyan)", future: "var(--accent)", accident: "var(--danger)" };
    let svg = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:${H}px;overflow:visible"><defs><linearGradient id="riskG" x1="0" x2="1"><stop offset="0" stop-color="#3DBE8B" stop-opacity=".10"/><stop offset=".25" stop-color="#F2B135" stop-opacity=".14"/><stop offset="1" stop-color="#EF5350" stop-opacity=".22"/></linearGradient></defs>
      <rect x="${P.l}" y="${P.t}" width="${W - P.l - P.r}" height="${H - P.t - P.b}" fill="url(#riskG)" rx="10"/>`;
    [20, 40, 60, 80, 100].forEach((o) => (svg += `<line x1="${sx(o)}" x2="${sx(o)}" y1="${P.t}" y2="${H - P.b}" stroke="var(--grid)"/><text x="${sx(o)}" y="${H - 14}" text-anchor="middle" fill="var(--muted)" font-size="11">${o}%</text>`));
    [0, 5, 10, 15].forEach((p) => (svg += `<line x1="${P.l}" x2="${W - P.r}" y1="${sy(p)}" y2="${sy(p)}" stroke="var(--grid)"/><text x="${P.l - 8}" y="${sy(p) + 4}" text-anchor="end" fill="var(--muted)" font-size="11">${p}</text>`));
    svg += `<text x="${W - P.r}" y="${H - 1}" text-anchor="end" fill="var(--muted)" font-size="10.5">O₂ fraction → higher flammability</text><text x="4" y="10" fill="var(--muted)" font-size="10.5">total pressure (psia)</text>`;
    habs.forEach((h, i) => {
      const x = sx(h.o2), y = sy(h.p), left = x > W - 160;
      svg += `<g style="animation:pop .6s var(--ease) ${0.15 * i}s both;transform-origin:${x}px ${y}px"><circle cx="${x}" cy="${y}" r="9" fill="${col[h.kind]}" fill-opacity=".25" stroke="${col[h.kind]}" stroke-width="2"/><circle cx="${x}" cy="${y}" r="3" fill="${col[h.kind]}"/>
        <text x="${left ? x - 14 : x + 14}" y="${y + (i % 2 ? 14 : -6)}" text-anchor="${left ? "end" : "start"}" fill="var(--text)" font-size="11.5" font-weight="600">${FD.esc(h.name)}</text></g>`;
    });
    el.innerHTML = svg + `</svg><div class="legend"><span><i style="background:var(--ok)"></i>Earth</span><span><i style="background:var(--cyan)"></i>Flown vehicles</span><span><i style="background:var(--accent)"></i>Planned exploration</span><span><i style="background:var(--danger)"></i>Accident</span></div>`;
  }
})();

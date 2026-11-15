/* FLAME DNA — Surveillance temps réel (simulation physiquement cohérente)
   - capteurs cabine simulés, plages nominales réalistes (type ISS)
   - scénario « feu » rejoué à partir des courbes RÉELLES de SAFFIRE-I S1
   - logique d'alerte multicritère avec persistance (pas un simple seuil)
*/
(function () {
  const FD = window.FD;
  const rnd = () => { let u = 0, v = 0; while (!u) u = Math.random(); while (!v) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };

  /* --- capteurs : plage nominale, seuils, famille de signature --- */
  const SENSORS = {
    smoke: { label: "Smoke obscuration", unit: "%/m", dec: 2, icon: "fa-smog", nominal: [0, 0.15], watch: 0.3, sig: 1.0, max: 5, family: "particulate", color: "#9CB0C9" },
    co: { label: "Carbon monoxide", unit: "ppm", dec: 1, icon: "fa-skull-crossbones", nominal: [0, 2], watch: 3, sig: 10, max: 80, family: "chemical", color: "#E58AC0" },
    temp: { label: "Rack air temperature", unit: "°C", dec: 1, icon: "fa-temperature-half", nominal: [18.3, 26.7], watch: 27.5, sig: 35, max: 90, family: "thermal", color: "#F36B21" },
    flux: { label: "Radiant heat flux", unit: "mW/cm²", dec: 1, icon: "fa-sun", nominal: [0, 1], watch: 2, sig: 5, max: 60, family: "thermal", color: "#D9A441" },
    o2: { label: "Oxygen", unit: "% vol", dec: 2, icon: "fa-lungs", family: "chemical", color: "#5BCFE3" },
    co2: { label: "Carbon dioxide", unit: "% vol", dec: 3, icon: "fa-cloud", family: "chemical", color: "#8E83F5" },
    air: { label: "Ventilation flow", unit: "cm/s", dec: 1, icon: "fa-wind", nominal: [7.6, 20], family: "flow", color: "#3DBE8B" },
  };
  const HABITATS = {
    iss: { name: "ISS module", o2: 21.0, p: 14.7, vol: 75, air: 14, desc: "21 % O₂ · 14.7 psia" },
    lunar: { name: "Lunar habitat", o2: 34.0, p: 8.2, vol: 45, air: 12, desc: "34 % O₂ · 8.2 psia" },
    rover: { name: "Pressurized rover", o2: 34.0, p: 8.2, vol: 12, air: 10, desc: "34 % O₂ · 8.2 psia · small volume" },
  };
  const SCENARIOS = {
    nominal: { label: "Nominal cabin", icon: "fa-circle-check" },
    fault: { label: "Sensor fault", icon: "fa-plug-circle-exclamation" },
    smolder: { label: "Overheating cable (smoldering)", icon: "fa-bolt" },
    fire: { label: "Flaming fire (SAFFIRE replay)", icon: "fa-fire" },
  };
  const LEVELS = [
    { name: "Nominal", short: "Cabin nominal", icon: "fa-shield-heart", text: "All signals inside their nominal bands." },
    { name: "Watch", short: "Watch — 1 signal off-nominal", icon: "fa-eye", text: "A single signature family deviates. Plausibility check in progress (possible sensor fault or transient)." },
    { name: "Warning", short: "Warning — pre-fire signature", icon: "fa-triangle-exclamation", text: "Two independent fire signatures agree and persist. Investigate the suspect area now." },
    { name: "Fire alarm", short: "FIRE ALARM", icon: "fa-fire", text: "Thermal signature confirmed together with smoke and/or combustion products." },
  ];

  /* ===================== MOTEUR ===================== */
  const M = (FD.monitor = {
    scenario: "nominal", habitat: "iss", t: 0, running: true, speed: 1,
    hist: [], events: [], level: 0, persist: { particulate: 0, chemical: 0, thermal: 0 },
    fx: { vent: true, power: true, suppress: 0, starve: 0, smolder: 0, fireClock: 0, fault: 0 },
    replay: null, timeIn: [0, 0, 0, 0], timer: null,
  });

  async function loadReplay() {
    if (M.replay) return M.replay;
    const idx = await FD.saffire();
    const s = idx.samples.find((x) => x.id === "SAFFIRE-I-S1");
    const ser = await FD.series(s.slug);
    const t = ser.t, ign = s.metrics.ignition_time_s || 60;
    const rad = ["Radiometer 1", "Radiometer 2", "Radiometer 3", "Radiometer 4"].map((c) => ser.channels[c].y);
    const plume = Object.keys(ser.channels).filter((c) => c.startsWith("Plume")).map((c) => ser.channels[c].y);
    const at = (arr, i) => (arr[i] == null ? NaN : arr[i]);
    const base = (fn) => { const v = []; t.forEach((x, i) => x < ign && v.push(fn(i))); return FD.stats.mean(v.filter(isFinite)); };
    const hfRaw = (i) => Math.max(...rad.map((a) => at(a, i)).filter(isFinite));
    const plRaw = (i) => Math.max(...plume.map((a) => at(a, i)).filter(isFinite));
    const b = { hf: base(hfRaw), pl: base(plRaw), o2: base((i) => at(ser.channels.O2.y, i)), co2: base((i) => at(ser.channels.CO2.y, i)) };
    const rows = [];
    t.forEach((x, i) => {
      if (x < ign) return;
      rows.push({ t: x - ign, hf: Math.max(0, hfRaw(i) - b.hf), dT: Math.max(0, plRaw(i) - b.pl), dO2: at(ser.channels.O2.y, i) - b.o2, dCO2: at(ser.channels.CO2.y, i) - b.co2 });
    });
    M.replay = { rows, sample: s, peak: s.metrics.radiometer_rise_mw_cm2 };
    return M.replay;
  }
  function replayAt(sec) {
    const R = M.replay.rows;
    if (sec >= R[R.length - 1].t) return R[R.length - 1];
    let k = 0; while (k < R.length - 1 && R[k + 1].t <= sec) k++;
    return R[k];
  }

  function log(msg, level = 0, kind = "state") {
    M.events.unshift({ t: M.t, msg, level, kind, clock: new Date().toLocaleTimeString() });
    M.events = M.events.slice(0, 120);
    FD.emit("monitor-event", M.events[0]);
  }

  M.setScenario = async function (sc) {
    M.scenario = sc;
    M.fx = { vent: true, power: true, suppress: 0, starve: 0, smolder: 0, fireClock: 0, fault: 0 };
    M.persist = { particulate: 0, chemical: 0, thermal: 0 };
    if (sc === "fire") await loadReplay();
    log(`Scenario → ${SCENARIOS[sc].label} · ${HABITATS[M.habitat].name}`, 0, "info");
  };
  M.setHabitat = function (h) { M.habitat = h; log(`Habitat → ${HABITATS[h].name} (${HABITATS[h].desc})`, 0, "info"); };
  M.action = function (a) {
    if (a === "vent") { M.fx.vent = false; log("Crew action: ventilation shut down in affected module", M.level, "action"); }
    if (a === "power") { M.fx.power = false; log("Crew action: electrical power removed from suspect rack", M.level, "action"); }
    if (a === "ext") { M.fx.suppress = 1; log("Crew action: fine-water-mist extinguisher discharged", M.level, "action"); }
    if (a === "reset") { M.setScenario(M.scenario); }
    FD.emit("tick", M);
  };

  function step() {
    const H = HABITATS[M.habitat], fx = M.fx, dt = 1 * M.speed;
    M.t += dt;
    const volF = 27 / H.vol;           // gaz : effet d'un même feu selon le volume libre (Cygnus ≈ 27 m³)
    const o2F = Math.pow(H.o2 / 21, 1.6); // croissance illustrative avec la fraction d'O₂
    let s = {
      smoke: 0.04 + 0.02 * Math.abs(rnd()), co: 0.6 + 0.25 * Math.abs(rnd()),
      temp: 22.4 + 0.12 * rnd(), flux: Math.max(0, 0.25 + 0.15 * rnd()),
      o2: H.o2 + 0.02 * rnd(), co2: 0.32 + 0.0015 * rnd(),
      air: fx.vent ? H.air + 0.6 * rnd() : Math.max(0, 0.4 + 0.2 * rnd()),
    };
    if (M.scenario === "fault") {
      fx.fault = Math.min(1, fx.fault + 0.012 * dt);
      s.temp += 30 * fx.fault + 0.4 * rnd();                // dérive d'un seul thermistor
    }
    if (M.scenario === "smolder") {
      if (fx.power) fx.smolder = Math.min(1.4, fx.smolder + 0.01 * dt);
      else fx.smolder = Math.max(0, fx.smolder - 0.01 * dt);
      const k = fx.smolder;
      s.co += 60 * k * volF * (fx.vent ? 0.8 : 1.2);         // fort rapport CO/CO₂ : combustion couvante
      s.smoke += 1.6 * k * (fx.vent ? 0.9 : 1.15);
      s.temp += 6 * k;
      s.co2 += 0.03 * k * volF;
      s.o2 -= 0.04 * k * volF;
      if (k >= 1.35 && fx.power && fx.vent && !fx._trans) { fx._trans = true; log("Smoldering → flaming transition", 3, "state"); M.scenario = "fire"; loadReplay(); }
    }
    if (M.scenario === "fire" && M.replay) {
      fx.fireClock += 2.5 * dt;                               // 1 s affichée ≈ 2,5 s de l'essai SAFFIRE
      if (!fx.vent) fx.starve = Math.min(1, fx.starve + 0.06 * dt); // sans écoulement, la flamme s'étouffe (µg)
      if (fx.suppress) fx.suppress = Math.min(1, fx.suppress + 0.2 * dt);
      const g = o2F * (1 - fx.starve) * (1 - fx.suppress);
      const r = replayAt(fx.fireClock);
      M.fireGain = g;
      s.flux += r.hf * 0.35 * g;
      s.temp += r.dT * 0.55 * g + 0.2 * rnd();
      s.co2 += Math.max(0, r.dCO2) * volF;
      s.o2 += Math.min(0, r.dO2) * volF;
      s.co += Math.max(0, r.dCO2) * volF * 10000 * 0.03;      // rapport CO/CO₂ ≈ 0,03 (flamme ventilée)
      s.smoke += (r.hf / (M.replay.peak || 100)) * 4 * g + Math.max(0, r.dCO2) * 4 * volF;
    }
    for (const k in s) s[k] = Math.max(0, s[k]);
    M.cur = s;
    M.hist.push({ t: M.t, ...s });
    if (M.hist.length > 240) M.hist.shift();
    evaluate();
    M.timeIn[M.level] += dt;
    FD.emit("tick", M);
  }

  /* ---------- logique d'alerte multicritère ---------- */
  // pente robuste : moyenne de la 2e moitié de fenêtre − moyenne de la 1re (anti-bruit)
  function rate(key, win = 20) {
    const h = M.hist.slice(-win); if (h.length < 12) return 0;
    const half = Math.floor(h.length / 2), a = h.slice(0, half), b = h.slice(half);
    const ma = FD.stats.mean(a.map((p) => p[key])), mb = FD.stats.mean(b.map((p) => p[key]));
    const ta = FD.stats.mean(a.map((p) => p.t)), tb = FD.stats.mean(b.map((p) => p.t));
    return (mb - ma) / Math.max(1, tb - ta);
  }
  function evaluate() {
    const s = M.cur, H = HABITATS[M.habitat];
    const ev = {
      smoke: { on: s.smoke > SENSORS.smoke.sig, watch: s.smoke > SENSORS.smoke.watch, txt: `Smoke ${FD.fmt(s.smoke, 2)} %/m`, fam: "particulate" },
      co: { on: s.co > SENSORS.co.sig, watch: s.co > SENSORS.co.watch, txt: `CO ${FD.fmt(s.co, 1)} ppm`, fam: "chemical" },
      co2r: { on: rate("co2") > 0.0008, watch: rate("co2") > 0.0005, txt: `CO₂ rising ${FD.fmt(rate("co2") * 60, 3)} %/min`, fam: "chemical" },
      o2d: { on: H.o2 - s.o2 > 0.15, watch: H.o2 - s.o2 > 0.08, txt: `O₂ depleted ${FD.fmt(H.o2 - s.o2, 2)} %`, fam: "chemical" },
      ror: { on: rate("temp") > 0.15 || s.temp > SENSORS.temp.sig, watch: s.temp > SENSORS.temp.watch, txt: `Temp ${FD.fmt(s.temp, 1)} °C (${FD.fmt(rate("temp") * 60, 1)} °C/min)`, fam: "thermal" },
      flux: { on: s.flux > SENSORS.flux.sig, watch: s.flux > SENSORS.flux.watch, txt: `Heat flux ${FD.fmt(s.flux, 1)} mW/cm²`, fam: "thermal" },
      air: { on: false, watch: s.air < 5 || s.air > 25, txt: `Airflow ${FD.fmt(s.air, 1)} cm/s`, fam: "flow" },
    };
    const fams = { particulate: false, chemical: false, thermal: false };
    for (const k in ev) if (ev[k].on && fams[ev[k].fam] !== undefined) fams[ev[k].fam] = true;
    for (const f in fams) M.persist[f] = fams[f] ? M.persist[f] + 1 : 0;
    const P = (f) => M.persist[f] >= 3;   // persistance ≥ 3 s
    const anyWatch = Object.values(ev).some((e) => e.watch || e.on);
    const nFam = ["particulate", "chemical", "thermal"].filter(P).length;
    let lvl = 0;
    if (anyWatch) lvl = 1;
    if (nFam >= 2) lvl = 2;
    if (P("thermal") && (P("particulate") || P("chemical")) && (ev.flux.on || s.temp > 40)) lvl = 3;
    // faute capteur probable : un seul capteur thermique dévie sans aucune autre signature
    M.faultSuspect = ev.ror.watch && !ev.flux.watch && !ev.smoke.watch && !ev.co.watch;
    // score d'anomalie statistique (z-score moyen vs. bande nominale)
    const z = [(s.smoke - 0.05) / 0.03, (s.co - 0.8) / 0.4, (s.temp - 22.4) / 0.5, (s.flux - 0.3) / 0.3, (H.o2 - s.o2) / 0.05, (s.co2 - 0.32) / 0.01].map((v) => Math.max(0, v));
    M.anomaly = 1 - Math.exp(-FD.stats.mean(z) / 6);
    M.evidence = ev; M.families = fams;
    M.risk = Math.min(1, [0.04, 0.3, 0.62, 0.9][lvl] + M.anomaly * 0.1 + (lvl === 3 ? Math.min(0.1, s.flux / 300) : 0));
    if (lvl !== M.level) {
      const up = lvl > M.level;
      M.level = lvl;
      const why = Object.values(ev).filter((e) => e.on || e.watch).map((e) => e.txt).slice(0, 3).join(" · ");
      log(`${up ? "▲" : "▼"} ${LEVELS[lvl].name}${why ? " — " + why : ""}${lvl === 1 && M.faultSuspect ? " (single-sensor deviation: possible sensor fault)" : ""}`, lvl, "state");
      if (up && lvl >= 2) FD.toast(LEVELS[lvl].name, " — " + LEVELS[lvl].text, lvl === 3 ? "danger" : "warn", 5000);
    }
    FD.emit("monitor", { level: M.level, short: LEVELS[M.level].short });
  }

  M.start = function () {
    if (M.timer) return;
    log("Monitoring started · ISS module · nominal cabin", 0, "info");
    M.timer = setInterval(() => M.running && step(), 1000);
    step();
  };

  /* ===================== PAGE ===================== */
  FD.pages.monitoring = {
    title: "Real-Time Monitoring",
    subtitle: "Simulated cabin sensors, a fire scenario replayed from real SAFFIRE data, and a multi-criteria alert logic that separates sensor faults from real fires.",
    async render(view) {
      view.innerHTML = `
      <div class="grid">
        <section class="card span-12" style="--i:0">
          <div class="scenario-bar">
            <div><div class="muted" style="font-size:12px;margin-bottom:6px">Scenario</div>
              <div class="seg" id="scSeg">${Object.entries(SCENARIOS).map(([k, v]) => `<button data-k="${k}" class="${k === M.scenario ? "on" : ""}"><i class="fa-solid ${v.icon}"></i> ${v.label}</button>`).join("")}</div></div>
            <div><div class="muted" style="font-size:12px;margin-bottom:6px">Habitat</div>
              <div class="seg" id="habSeg">${Object.entries(HABITATS).map(([k, v]) => `<button data-k="${k}" class="${k === M.habitat ? "on" : ""}" title="${v.desc}">${v.name}</button>`).join("")}</div></div>
            <div style="display:flex;gap:8px;align-self:flex-end">
              <button class="btn sm" id="pauseBtn"><i class="fa-solid ${M.running ? "fa-pause" : "fa-play"}"></i> ${M.running ? "Pause" : "Resume"}</button>
              <button class="btn sm" id="resetBtn"><i class="fa-solid fa-rotate-left"></i> Reset</button>
            </div>
          </div>
        </section>

        <section class="alert-banner span-12 card" id="banner" style="--i:1">
          <div class="sweep"></div>
          <div class="lvl-icon"><i class="fa-solid fa-shield-heart"></i></div>
          <div style="min-width:0"><h3 id="bTitle">Nominal</h3><p id="bText"></p></div>
          <div class="stages">${LEVELS.map((l, i) => `<div class="stage s${i}" data-s="${i}">${l.name}</div>`).join("")}</div>
        </section>

        ${["smoke", "co", "temp", "flux"].map((k, i) => sensorCard(k, i + 2)).join("")}
        ${["o2", "co2", "air"].map((k, i) => sensorCard(k, i + 6)).join("")}
        <section class="card span-3" style="--i:9;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px">
          <div id="riskRing"></div>
          <div class="muted" style="font-size:12px">Anomaly score <b class="mono" id="anom" style="color:var(--text)">0</b></div>
        </section>

        <section class="card span-8" style="--i:10">
          <div class="card-head"><div><h3>Live signals</h3><div class="sub">Last 4 minutes · dashed lines = alert thresholds</div></div>
            <div class="seg" id="chartSeg"><button class="on" data-k="thermal"><i class="fa-solid fa-temperature-half"></i> Thermal</button><button data-k="chemical"><i class="fa-solid fa-flask"></i> Chemical</button><button data-k="particulate"><i class="fa-solid fa-smog"></i> Smoke</button></div></div>
          <div id="liveChart"></div>
        </section>

        <section class="card span-4" style="--i:11">
          <div class="card-head"><div><h3>Fire-signature evidence</h3><div class="sub">Alarm needs independent families to agree</div></div><span class="card-icon"><i class="fa-solid fa-diagram-project"></i></span></div>
          <div class="evidence" id="evidence"></div>
          <div class="note" id="faultNote"></div>
        </section>

        <section class="card span-5" style="--i:12">
          <div class="card-head"><div><h3>Crew response</h3><div class="sub">Generic spacecraft fire-response steps — try them</div></div><span class="card-icon"><i class="fa-solid fa-user-astronaut"></i></span></div>
          <div class="actions-list" id="actions"></div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
            <button class="btn sm" data-act="vent"><i class="fa-solid fa-fan"></i> Shut down ventilation</button>
            <button class="btn sm" data-act="power"><i class="fa-solid fa-power-off"></i> Remove rack power</button>
            <button class="btn sm primary" data-act="ext"><i class="fa-solid fa-spray-can-sparkles"></i> Water-mist extinguisher</button>
          </div>
          <div class="note"><i class="fa-solid fa-circle-info"></i><span>In microgravity the ventilation flow is what feeds the flame: stopping the fans starves it (watch the heat flux decay).</span></div>
        </section>

        <section class="card span-7" style="--i:13">
          <div class="card-head"><div><h3>Event log</h3><div class="sub">State transitions, crew actions and scenario changes</div></div>
            <div style="display:flex;gap:8px;align-items:center"><div id="timeInBar" style="width:180px"></div><button class="btn sm" id="exportLog"><i class="fa-solid fa-file-csv"></i> CSV</button></div></div>
          <ul class="timeline" id="timeline"></ul>
        </section>
      </div>
      <p class="note"><i class="fa-solid fa-flask-vial"></i><span>Simulated sensors only. Nominal bands follow typical ISS cabin ranges (18.3–26.7 °C, ~21 % O₂, ~0.3 % CO₂, 7.6–20 cm/s ventilation). The flaming scenario replays the measured heat-flux, plume-temperature, O₂ and CO₂ dynamics of SAFFIRE-I S1 (time-compressed ×2.5, scaled by habitat volume and O₂ fraction). Thresholds are demonstration values, not certified limits.</span></p>`;

      const ring = FD.charts.ring(FD.$("#riskRing"), { size: 150, thickness: 13, value: M.risk || 0.04, label: "fire risk index", color: "var(--ok)" });
      let chartKind = "thermal", chart = null;

      const drawChart = (anim) => {
        const h = M.hist, t = h.map((x) => x.t - M.t);
        const defs = {
          thermal: { s: [["temp", "Rack temp (°C)", "#F36B21"], ["flux", "Heat flux (mW/cm²)", "#D9A441"]], bands: [{ y0: SENSORS.flux.sig, y1: SENSORS.flux.sig + 0.15, color: "var(--danger)", opacity: 0.5 }, { y0: SENSORS.temp.sig, y1: SENSORS.temp.sig + 0.15, color: "var(--warn)", opacity: 0.6 }] },
          chemical: { s: [["co", "CO (ppm)", "#E58AC0"], ["co2", "CO₂ (% ×100)", "#8E83F5", 100], ["o2d", "O₂ deficit (% ×100)", "#5BCFE3"]], bands: [{ y0: SENSORS.co.sig, y1: SENSORS.co.sig + 0.2, color: "var(--danger)", opacity: 0.5 }] },
          particulate: { s: [["smoke", "Smoke (%/m)", "#9CB0C9"]], bands: [{ y0: SENSORS.smoke.sig, y1: SENSORS.smoke.sig + 0.02, color: "var(--danger)", opacity: 0.6 }, { y0: 0, y1: SENSORS.smoke.watch, color: "var(--ok)", opacity: 0.06, label: "nominal" }] },
        }[chartKind];
        const H = HABITATS[M.habitat];
        const series = defs.s.map(([k, name, color, mul]) => ({ name, color, x: t, y: h.map((p) => (k === "o2d" ? Math.max(0, H.o2 - p.o2) * 100 : p[k] * (mul || 1))), area: true }));
        const opts = { series, bands: defs.bands, xLabel: "seconds (0 = now)", xName: "t", xUnit: " s", height: 280, xMin: -240, xMax: 0, yMin: 0, animate: anim };
        if (!chart || anim) chart = FD.charts.line(FD.$("#liveChart"), opts);
        else chart.update(series);
      };

      const render = () => {
        const s = M.cur; if (!s) return;
        const H = HABITATS[M.habitat];
        ["smoke", "co", "temp", "flux", "o2", "co2", "air"].forEach((k) => {
          const cfg = SENSORS[k], card = FD.$(`#sen-${k}`); if (!card) return;
          const v = s[k];
          card.querySelector(".value span").textContent = FD.fmt(v, cfg.dec);
          let state = "ok", pct;
          if (k === "o2") { const d = H.o2 - v; state = d > 0.15 ? "crit" : d > 0.08 ? "warn" : "ok"; pct = FD.stats.clamp((v - (H.o2 - 1)) / 1.5, 0, 1); }
          else if (k === "co2") { state = v > 0.45 ? "crit" : v > 0.36 ? "warn" : "ok"; pct = FD.stats.clamp(v / 0.8, 0, 1); }
          else if (k === "air") { state = v < 5 ? "warn" : "ok"; pct = FD.stats.clamp(v / 30, 0, 1); }
          else { state = v > cfg.sig ? "crit" : v > cfg.watch ? "warn" : "ok"; pct = FD.stats.clamp(v / cfg.max, 0, 1); }
          card.classList.toggle("s-warn", state === "warn"); card.classList.toggle("s-crit", state === "crit");
          const fill = card.querySelector(".bar-fill");
          fill.style.width = (pct * 100).toFixed(1) + "%";
          fill.style.background = state === "crit" ? "var(--danger)" : state === "warn" ? "var(--warn)" : cfg.color;
          const st = card.querySelector(".state");
          st.textContent = { ok: "nominal", warn: "elevated", crit: "fire signature" }[state];
          st.style.color = state === "crit" ? "var(--danger)" : state === "warn" ? "var(--warn)" : "var(--ok)";
          FD.charts.spark(card.querySelector(".spark"), M.hist.slice(-60).map((p) => p[k]), cfg.color, { animate: false, height: 34 });
        });
        // bannière
        const L = LEVELS[M.level], b = FD.$("#banner");
        b.className = `alert-banner span-12 card lvl-${M.level}`;
        b.querySelector(".lvl-icon i").className = "fa-solid " + L.icon;
        FD.$("#bTitle").textContent = L.name + (M.level === 1 && M.faultSuspect ? " — possible sensor fault" : "");
        FD.$("#bText").textContent = L.text;
        FD.$$(".stage", b).forEach((x) => x.classList.toggle("on", +x.dataset.s <= M.level));
        ring.set(M.risk, ["var(--ok)", "var(--cyan)", "var(--warn)", "var(--danger)"][M.level]);
        FD.$("#anom").textContent = Math.round(M.anomaly * 100) + " / 100";
        // preuves
        const ev = M.evidence, fams = [["particulate", "fa-smog", "Particulate", ["smoke"]], ["chemical", "fa-flask", "Combustion products", ["co", "co2r", "o2d"]], ["thermal", "fa-temperature-arrow-up", "Thermal", ["ror", "flux"]]];
        FD.$("#evidence").innerHTML = fams.map(([f, ic, name, keys]) => {
          const on = M.families[f], pers = M.persist[f] >= 3;
          const detail = keys.map((k) => `<span style="opacity:${ev[k].on ? 1 : ev[k].watch ? 0.85 : 0.5}">${ev[k].txt}</span>`).join(" · ");
          return `<div class="ev ${on ? "met" : ""} ${on && pers && M.level === 3 ? "crit" : ""}"><i class="fa-solid ${ic}" style="color:${on ? "var(--warn)" : "var(--muted)"}"></i><div><b>${name}</b><div class="muted" style="font-size:11.5px">${detail}</div></div><span class="st" style="color:${on ? (pers ? "var(--danger)" : "var(--warn)") : "var(--ok)"}">${on ? (pers ? "CONFIRMED" : "DETECTED") : "CLEAR"}</span></div>`;
        }).join("");
        FD.$("#faultNote").innerHTML = M.faultSuspect ? `<i class="fa-solid fa-plug-circle-exclamation"></i><span><b>Plausibility check:</b> only the temperature channel deviates while smoke, CO and heat flux are clean — consistent with a <b>sensor fault</b>, so no fire alarm is raised.</span>` : `<i class="fa-solid fa-circle-info"></i><span>Watch = 1 family · Warning = 2 families for ≥ 3 s · Fire alarm = thermal + smoke or combustion products.</span>`;
        // actions recommandées
        const steps = M.level >= 3 ? ["Sound the alarm, crew gathers at the safe haven", "Shut down ventilation in the affected module", "Remove power from the suspect rack", "Don breathing masks, monitor CO / HCN / HCl", "Discharge portable extinguisher if fire persists"]
          : M.level === 2 ? ["Locate the source with a portable combustion-products analyzer", "Prepare masks and extinguisher", "Be ready to stop ventilation & power"]
          : M.level === 1 ? ["Cross-check the deviating sensor with neighbouring sensors", "No action on ventilation yet — avoid false-alarm cost"]
          : ["Routine monitoring — no action required"];
        FD.$("#actions").innerHTML = steps.map((x) => `<div>${x}</div>`).join("");
        FD.$$("[data-act]").forEach((btn) => {
          const k = btn.dataset.act;
          btn.disabled = (k === "vent" && !M.fx.vent) || (k === "power" && !M.fx.power) || (k === "ext" && M.fx.suppress > 0);
        });
        // temps passé par niveau
        const tot = M.timeIn.reduce((a, b) => a + b, 0) || 1;
        FD.$("#timeInBar").innerHTML = `<div title="Time spent per level" style="display:flex;height:8px;border-radius:6px;overflow:hidden;background:var(--surface-3)">${M.timeIn.map((v, i) => `<span style="width:${(100 * v) / tot}%;background:${["var(--ok)", "var(--cyan)", "var(--warn)", "var(--danger)"][i]};transition:width .6s"></span>`).join("")}</div>`;
        drawChart(false);
      };
      const renderLog = () => {
        FD.$("#timeline").innerHTML = M.events.slice(0, 40).map((e) => `<li class="l${e.level}"><span class="mk"></span><div class="t">T+${Math.round(e.t)} s · ${e.clock} ${e.kind === "action" ? '<span class="tag orange">crew</span>' : e.kind === "info" ? '<span class="tag">info</span>' : ""}</div><div class="m">${FD.esc(e.msg)}</div></li>`).join("");
      };

      FD.$$("#scSeg button").forEach((b) => b.onclick = async () => { FD.$$("#scSeg button").forEach((x) => x.classList.toggle("on", x === b)); await M.setScenario(b.dataset.k); });
      FD.$$("#habSeg button").forEach((b) => b.onclick = () => { FD.$$("#habSeg button").forEach((x) => x.classList.toggle("on", x === b)); M.setHabitat(b.dataset.k); });
      FD.$$("#chartSeg button").forEach((b) => b.onclick = () => { FD.$$("#chartSeg button").forEach((x) => x.classList.toggle("on", x === b)); chartKind = b.dataset.k; drawChart(true); });
      FD.$$("[data-act]").forEach((b) => b.onclick = () => M.action(b.dataset.act));
      FD.$("#pauseBtn").onclick = (e) => { M.running = !M.running; e.currentTarget.innerHTML = `<i class="fa-solid ${M.running ? "fa-pause" : "fa-play"}"></i> ${M.running ? "Pause" : "Resume"}`; };
      FD.$("#resetBtn").onclick = () => { M.hist = []; M.timeIn = [0, 0, 0, 0]; M.action("reset"); };
      FD.$("#exportLog").onclick = () => FD.download("flame_dna_event_log.csv", "t_s,clock,level,kind,message\n" + M.events.map((e) => `${Math.round(e.t)},${e.clock},${LEVELS[e.level].name},${e.kind},"${e.msg.replace(/"/g, "'")}"`).join("\n"));

      FD.animateCounts(view);
      drawChart(true);
      render(); renderLog();
      const onTick = () => FD.$("#banner") && render();
      const onEv = () => FD.$("#timeline") && renderLog();
      FD.on("tick", onTick); FD.on("monitor-event", onEv);
      return () => { FD.off("tick", onTick); FD.off("monitor-event", onEv); };
    },
  };

  function sensorCard(k, i) {
    const c = SENSORS[k];
    return `<section class="card kpi sensor span-3 lift" id="sen-${k}" style="--i:${i}">
      <div class="kpi-top"><span class="label"><i class="fa-solid ${c.icon}" style="color:${c.color};margin-right:6px"></i>${c.label}</span><span class="state">nominal</span></div>
      <div class="value"><span>—</span><small>${c.unit}</small></div>
      <div class="bar-track"><div class="bar-fill"></div></div>
      <div class="spark"></div></section>`;
  }
})();

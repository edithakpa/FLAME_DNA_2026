/* FLAME DNA — Accueil : synthèse globale des données SAFFIRE + accès rapide */
(function () {
  const FD = window.FD;
  const MISSION_COLOR = { "SAFFIRE-I": "#F36B21", "SAFFIRE-II": "#5BCFE3", "SAFFIRE-III": "#D9A441" };
  FD.MISSION_COLOR = MISSION_COLOR;

  FD.pages.overview = {
    title: "Overview",
    subtitle: "How do flames spread in space — and how do we stop them? Real NASA microgravity fire data, turned into safety insight.",
    async render(view) {
      const [idx, pubs] = await Promise.all([FD.saffire(), FD.publications()]);
      const S = idx.samples;
      const totalRecords = S.reduce((a, s) => a + (s.metrics.records || 0), 0);
      const sustained = S.filter((s) => s.metrics.flame_confidence !== "low" && s.metrics.flame_duration_s != null);
      const flameSeconds = sustained.reduce((a, s) => a + s.metrics.flame_duration_s, 0);
      const relevantPubs = pubs.filter((p) => p.relevance >= 40).length;
      const channels = new Set(S.flatMap((s) => s.channels)).size;
      const byMission = Object.keys(MISSION_COLOR).map((m) => ({ label: m, value: S.filter((s) => s.mission === m).length, color: MISSION_COLOR[m] }));
      const big = S.find((s) => s.id === "SAFFIRE-I-S1") || S[0];
      const hottest = [...S].sort((a, b) => (b.metrics.sample_temp_peak_c || 0) - (a.metrics.sample_temp_peak_c || 0))[0];
      const strongest = [...S].sort((a, b) => (b.metrics.radiometer_rise_mw_cm2 || 0) - (a.metrics.radiometer_rise_mw_cm2 || 0))[0];
      const maxO2 = [...S].sort((a, b) => (b.metrics.o2_drop_pct || 0) - (a.metrics.o2_drop_pct || 0))[0];
      const s1 = S.find((s) => s.id === "SAFFIRE-I-S1"), s2 = S.find((s) => s.id === "SAFFIRE-I-S2");

      view.innerHTML = `
      <div class="grid">
        <section class="card hero span-12" style="--i:0">
          <div>
            <span class="tag orange"><i class="fa-solid fa-satellite"></i> NASA Space Apps 2026 · Flame in free fall</span>
            <h2 style="margin-top:12px">A fire in space doesn't rise — it <em>creeps, hides and suffocates.</em></h2>
            <p>FLAME DNA reads the "fingerprint" of real microgravity fires recorded by NASA's SAFFIRE experiments to answer one question for every crewed habitat — spacecraft, space station, lunar base or pressurized rover:</p>
            <div class="question-box"><i class="fa-solid fa-circle-question" style="color:var(--accent)"></i> <b>Is this material, in this habitat, under this airflow, safe — and how fast would we detect a fire?</b></div>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px">
              <a class="btn primary" href="#/monitoring"><i class="fa-solid fa-tower-broadcast"></i> Live monitoring</a>
              <a class="btn" href="#/explorer"><i class="fa-solid fa-folder-tree"></i> Explore NASA data</a>
              <a class="btn ghost" href="#/assistant"><i class="fa-solid fa-wand-magic-sparkles"></i> Ask the AI</a>
            </div>
          </div>
          <div class="hero-media"><img src="assets/img/flame-earth-vs-micro.jpg" alt="Candle flame on Earth (left) and in microgravity (right)"><div class="cap"><span>1 g — buoyant, yellow</span><span>µg — spherical, blue</span></div></div>
        </section>

        <div class="card kpi span-3 lift" style="--i:1"><div class="kpi-top"><span class="label">SAFFIRE samples analysed</span><span class="card-icon"><i class="fa-solid fa-fire-flame-simple"></i></span></div>
          <div class="value" data-count="${S.length}">0</div><div class="foot">3 missions · real NASA PSI files</div><div class="spark" id="spSamples"></div></div>
        <div class="card kpi span-3 lift" style="--i:2"><div class="kpi-top"><span class="label">Calibrated telemetry records</span><span class="card-icon" style="background:color-mix(in srgb,var(--cyan) 15%,transparent);color:var(--cyan)"><i class="fa-solid fa-wave-square"></i></span></div>
          <div class="value" data-count="${totalRecords}">0</div><div class="foot">${channels} sensor channels per sample</div><div class="spark" id="spRecords"></div></div>
        <div class="card kpi span-3 lift" style="--i:3"><div class="kpi-top"><span class="label">Seconds of flame measured</span><span class="card-icon" style="background:color-mix(in srgb,var(--amber) 16%,transparent);color:var(--amber)"><i class="fa-solid fa-stopwatch"></i></span></div>
          <div class="value"><span data-count="${flameSeconds}">0</span><small>s</small></div><div class="foot">${sustained.length} samples with a resolved flame signal</div><div class="spark" id="spFlame"></div></div>
        <div class="card kpi span-3 lift" style="--i:4">
          <div class="kpi-split">
            <div><span class="label">NASA publications</span><div class="value" data-count="${pubs.length}">0</div><div class="spark" id="spPubs"></div></div>
            <div class="sep"></div>
            <div><span class="label">Fire-safety relevant</span><div class="value" style="color:var(--accent)" data-count="${relevantPubs}">0</div><div class="spark" id="spRel"></div></div>
          </div>
        </div>

        <section class="card span-8" style="--i:5">
          <div class="card-head"><div><h3>Anatomy of a spacecraft fire — ${big.id}</h3><div class="sub">Radiative heat flux on the 4 radiometers · ${FD.esc(big.meta.material || "")} · ${FD.esc(big.meta.flow_direction || "")} flow ${big.meta.nominal_flow_cm_s ? "at " + big.meta.nominal_flow_cm_s + " cm/s" : ""}</div></div>
          <div class="seg" id="anatomySeg"><button class="on" data-k="rad"><i class="fa-solid fa-sun"></i> Heat flux</button><button data-k="tc"><i class="fa-solid fa-temperature-high"></i> Sample TCs</button><button data-k="atm"><i class="fa-solid fa-lungs"></i> O₂ / CO₂</button></div></div>
          <div id="anatomy"></div>
        </section>

        <section class="card span-4" style="--i:6">
          <div class="card-head"><div><h3>Dataset coverage</h3><div class="sub">Samples per mission</div></div></div>
          <div id="donut"></div>
          <div class="section-title" style="margin:18px 0 10px">Flame resolution</div>
          <div style="display:flex;justify-content:space-around;gap:10px">
            <div id="ringSustained"></div><div id="ringHigh"></div>
          </div>
        </section>

        <section class="card span-6" style="--i:7">
          <div class="card-head"><div><h3>Flame duration per sample</h3><div class="sub">Time the flame signal stays above 10 % of its peak</div></div><span class="card-icon"><i class="fa-solid fa-hourglass-half"></i></span></div>
          <div id="barDuration"></div>
        </section>
        <section class="card span-6" style="--i:8">
          <div class="card-head"><div><h3>Radiative heat-flux rise</h3><div class="sub">Peak radiometer signal above pre-ignition baseline (mW/cm²)</div></div><span class="card-icon"><i class="fa-solid fa-sun"></i></span></div>
          <div id="barFlux"></div>
        </section>

        <section class="card span-7" style="--i:9">
          <div class="card-head"><div><h3>What the data tell us</h3><div class="sub">Automatically derived from the calibrated SAFFIRE files</div></div><span class="card-icon"><i class="fa-solid fa-lightbulb"></i></span></div>
          <div class="finding"><span class="n">01</span><p><b>Flow direction changes everything.</b> Same SIBAL fabric, same 20 cm/s airflow: concurrent spread (${s1?.id}) reached <b>${FD.fmt(s1?.metrics.radiometer_rise_mw_cm2, 0)} mW/cm²</b> versus <b>${FD.fmt(s2?.metrics.radiometer_rise_mw_cm2, 1)} mW/cm²</b> in opposed flow (${s2?.id}) — about ${FD.fmt((s1?.metrics.radiometer_rise_mw_cm2 || 0) / (s2?.metrics.radiometer_rise_mw_cm2 || 1), 0)}× more radiant heat.</p></div>
          <div class="finding"><span class="n">02</span><p><b>Surfaces get hotter than the plume.</b> ${hottest.id} reached <b>${FD.fmt(hottest.metrics.sample_temp_peak_c, 0)} °C</b> on the sample while plume thermocouples stayed below ${FD.fmt(hottest.metrics.plume_temp_peak_c, 0)} °C — gas-temperature sensors alone would underestimate the fire.</p></div>
          <div class="finding"><span class="n">03</span><p><b>A small fire measurably changes a cabin.</b> ${maxO2.id} consumed <b>${FD.fmt(maxO2.metrics.o2_drop_pct, 2)} %</b> O₂ of the whole Cygnus atmosphere; CO₂ rose by up to <b>${FD.fmt(Math.max(...S.map((s) => s.metrics.co2_rise_pct || 0)), 2)} %</b> — combustion products are an early, cabin-wide fire signature.</p></div>
          <div class="finding"><span class="n">04</span><p><b>Strongest radiant fire:</b> ${strongest.id} (${FD.fmt(strongest.metrics.radiometer_rise_mw_cm2, 0)} mW/cm²) — large samples produce heat fluxes able to ignite neighbouring materials, the key scenario for habitat design.</p></div>
        </section>

        <section class="card span-5" style="--i:10">
          <div class="card-head"><div><h3>Where to go next</h3><div class="sub">Six tools, one mission</div></div></div>
          <div style="display:grid;gap:14px">
            ${[
              ["monitoring", "fa-tower-broadcast", "Real-Time Monitoring", "Simulated cabin sensors with a multi-criteria fire-alert logic"],
              ["explorer", "fa-folder-tree", "Data Explorer", "Browse NASA microgravity files & investigations channel by channel"],
              ["compare", "fa-code-compare", "Scientific Comparison", "Compare samples on their common parameters, find similar ones"],
              ["safety", "fa-shield-halved", "Mission Fire Safety", "Habitat risk, what-if scenarios and benefits on Earth"],
              ["catalog", "fa-book-atlas", "NASA Research Catalog", "Publications & reference sites ranked by fire-safety relevance"],
            ].map(([r, ic, t, d]) => `<a class="quick" href="#/${r}"><span class="card-icon"><i class="fa-solid ${ic}"></i></span><div><h4>${t}</h4><p>${d}</p></div><i class="fa-solid fa-arrow-right arrow"></i></a>`).join("")}
          </div>
        </section>
      </div>`;

      FD.animateCounts(view);
      // sparklines (vraies distributions)
      const order = [...S];
      FD.charts.spark(FD.$("#spSamples"), order.map((s) => s.metrics.duration_s), "var(--accent)");
      FD.charts.spark(FD.$("#spRecords"), order.map((s) => s.metrics.records), "var(--cyan)", { delay: 0.2 });
      FD.charts.spark(FD.$("#spFlame"), order.map((s) => s.metrics.flame_duration_s), "var(--amber)", { delay: 0.3 });
      const yearCounts = {};
      pubs.forEach((p) => { const y = +p.year; if (y) yearCounts[y] = (yearCounts[y] || 0) + 1; });
      const ys = Object.keys(yearCounts).sort();
      FD.charts.spark(FD.$("#spPubs"), ys.map((y) => yearCounts[y]), "var(--violet)", { delay: 0.4 });
      FD.charts.spark(FD.$("#spRel"), pubs.slice(0, 30).map((p) => p.relevance), "var(--accent)", { delay: 0.5 });

      FD.charts.donut(FD.$("#donut"), { items: byMission, center: S.length, centerLabel: "samples" });
      FD.charts.ring(FD.$("#ringSustained"), { size: 118, thickness: 11, value: sustained.length / S.length, label: "resolved flame", gradient: ["#D9A441", "#F36B21"] });
      const high = S.filter((s) => s.metrics.flame_confidence === "high").length;
      FD.charts.ring(FD.$("#ringHigh"), { size: 118, thickness: 11, value: high / S.length, label: "strong signal", gradient: ["#5BCFE3", "#8E83F5"] });

      const labels = S.map((s) => s.id.replace("SAFFIRE-", "").replace("-", " "));
      const colors = S.map((s) => MISSION_COLOR[s.mission]);
      FD.charts.bar(FD.$("#barDuration"), { labels, series: [{ name: "Flame duration", values: S.map((s) => s.metrics.flame_duration_s), colors }], unit: "s", rotate: true, height: 250 });
      FD.charts.bar(FD.$("#barFlux"), { labels, series: [{ name: "Heat-flux rise", values: S.map((s) => s.metrics.radiometer_rise_mw_cm2), colors }], unit: "mW/cm²", rotate: true, height: 250 });

      // anatomie d'un feu (série réelle)
      const ser = await FD.series(big.slug);
      const m = big.metrics;
      const markers = [
        { x: m.ignition_time_s, label: "Ignition", color: "var(--warn)" },
        { x: m.radiometer_peak_time_s, label: "Peak", color: "var(--danger)" },
        { x: m.flame_signal_end_s, label: "Extinction", color: "var(--cyan)" },
      ];
      const drawAnatomy = (k) => {
        const el = FD.$("#anatomy");
        const pick = (names, colors) => names.filter((n) => ser.channels[n]).map((n, i) => ({ name: n, unit: ser.channels[n].unit, x: ser.t, y: ser.channels[n].y, color: colors[i] }));
        if (k === "rad") FD.charts.line(el, { series: pick(["Radiometer 1", "Radiometer 2", "Radiometer 3", "Radiometer 4"], FD.palette), area: true, yLabel: "mW/cm²", xName: "t", xUnit: " s", xLabel: "elapsed time (s)", markers, height: 290 });
        if (k === "tc") FD.charts.line(el, { series: pick(Object.keys(ser.channels).filter((c) => c.startsWith("Sample Temp")), FD.palette), yLabel: "°C", xName: "t", xUnit: " s", xLabel: "elapsed time (s)", markers, height: 290 });
        if (k === "atm") {
          const o2 = ser.channels.O2, co2 = ser.channels.CO2;
          const base = (y) => { const v = y.find((x) => x != null); return y.map((x) => (x == null ? null : x - v)); };
          FD.charts.line(el, { series: [{ name: "ΔO₂ (vs start)", unit: "%", x: ser.t, y: base(o2.y), color: "#5BCFE3" }, { name: "ΔCO₂ (vs start)", unit: "%", x: ser.t, y: base(co2.y), color: "#F36B21" }], area: true, yLabel: "Δ % vol", xName: "t", xUnit: " s", xLabel: "elapsed time (s)", markers, height: 290 });
        }
      };
      drawAnatomy("rad");
      FD.$$("#anatomySeg button").forEach((b) => b.addEventListener("click", () => {
        FD.$$("#anatomySeg button").forEach((x) => x.classList.toggle("on", x === b));
        drawAnatomy(b.dataset.k);
      }));
    },
  };
})();

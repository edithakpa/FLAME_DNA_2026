/* FLAME DNA — Comparaison scientifique : uniquement sur les paramètres COMMUNS aux fichiers choisis,
   avec recherche d'échantillons similaires (distance sur métriques normalisées) */
(function () {
  const FD = window.FD;
  const CORE = ["flame_duration_s", "radiometer_rise_mw_cm2", "sample_temp_peak_c", "plume_temp_peak_c", "o2_drop_pct", "co2_rise_pct", "airflow_median_cm_s", "o2_initial_pct", "pressure_mean_psia", "radiant_dose_mj_cm2", "sample_front_transit_s", "pressure_rise_psia"];
  const RADAR = ["flame_duration_s", "radiometer_rise_mw_cm2", "sample_temp_peak_c", "plume_temp_peak_c", "o2_drop_pct", "co2_rise_pct"];
  const SIM_KEYS = ["flame_duration_s", "radiometer_rise_mw_cm2", "sample_temp_peak_c", "plume_temp_peak_c", "o2_drop_pct", "co2_rise_pct", "airflow_median_cm_s"];
  const st = { sel: ["SAFFIRE-I-S1", "SAFFIRE-I-S2"], metric: "radiometer_rise_mw_cm2", channel: "Radiometer 1" };

  function stats(samples) {
    const o = {};
    CORE.forEach((k) => { const v = samples.map((s) => s.metrics[k]).filter((x) => x != null); o[k] = { min: Math.min(...v), max: Math.max(...v), mean: FD.stats.mean(v), std: FD.stats.std(v) || 1 }; });
    return o;
  }
  function similarity(a, b, S) {
    const ks = SIM_KEYS.filter((k) => a.metrics[k] != null && b.metrics[k] != null);
    if (!ks.length) return 0;
    const d = Math.sqrt(FD.stats.mean(ks.map((k) => {
      const z = (v) => (Math.sign(v) * Math.log1p(Math.abs(v)) - 0) / 1;
      const sc = Math.log1p(Math.abs(S[k].max)) || 1;
      return ((z(a.metrics[k]) - z(b.metrics[k])) / sc) ** 2;
    })));
    return Math.max(0, 1 - d * 1.6);
  }

  FD.pages.compare = {
    title: "Scientific Comparison",
    subtitle: "Pick 2 to 4 burned samples — FLAME DNA compares them only on the parameters they share, and suggests the most similar experiments.",
    async render(view) {
      const idx = await FD.saffire();
      const S = idx.samples, ST = stats(S);
      if (FD.compareSeed) { st.sel = [FD.compareSeed]; const sims = S.filter((x) => x.id !== FD.compareSeed).map((x) => [x, similarity(S.find((y) => y.id === FD.compareSeed), x, ST)]).sort((a, b) => b[1] - a[1]); st.sel.push(sims[0][0].id); FD.compareSeed = null; }
      view.innerHTML = `
        <section class="card" style="--i:0">
          <div class="card-head"><div><h3>1 · Choose samples</h3><div class="sub">Click to add/remove (max 4). The <span style="color:var(--cyan);font-weight:700">% similar</span> badge is relative to the first selected sample.</div></div>
            <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn sm" id="simBtn"><i class="fa-solid fa-wand-magic-sparkles"></i> Add most similar</button><button class="btn sm ghost" id="clearBtn"><i class="fa-solid fa-eraser"></i> Clear</button></div></div>
          <div class="sample-picker" id="picker"></div>
        </section>
        <div id="cmpBody"></div>`;

      const drawPicker = () => {
        const ref = S.find((s) => s.id === st.sel[0]);
        FD.$("#picker").innerHTML = S.map((s) => {
          const k = st.sel.indexOf(s.id), on = k >= 0;
          const sim = ref && s.id !== ref.id ? Math.round(similarity(ref, s, ST) * 100) : null;
          return `<div class="sample-opt ${on ? "on" : ""}" data-id="${s.id}" style="--c:${on ? FD.palette[k] : ""}"><b>${s.mission} · ${s.sample}</b><span>${FD.fmt(s.metrics.flame_duration_s, 0)} s flame · ${FD.fmt(s.metrics.radiometer_rise_mw_cm2, 0)} mW/cm²</span>${sim != null ? `<span class="sim">${sim}% similar</span>` : ""}</div>`;
        }).join("");
        FD.$$(".sample-opt").forEach((o) => o.onclick = () => {
          const id = o.dataset.id;
          if (st.sel.includes(id)) st.sel = st.sel.filter((x) => x !== id);
          else if (st.sel.length < 4) st.sel.push(id);
          else FD.toast("4 samples max", " — remove one first", "info");
          update();
        });
      };
      const update = () => { drawPicker(); drawBody(); };
      FD.$("#simBtn").onclick = () => {
        if (!st.sel.length) st.sel = ["SAFFIRE-I-S1"];
        if (st.sel.length >= 4) return FD.toast("4 samples max", "", "info");
        const ref = S.find((s) => s.id === st.sel[0]);
        const best = S.filter((s) => !st.sel.includes(s.id)).map((s) => [s, similarity(ref, s, ST)]).sort((a, b) => b[1] - a[1])[0];
        st.sel.push(best[0].id);
        FD.toast("Similar sample added", ` — ${best[0].id} (${Math.round(best[1] * 100)}% similar to ${ref.id})`, "ok");
        update();
      };
      FD.$("#clearBtn").onclick = () => { st.sel = []; update(); };

      const drawBody = async () => {
        const body = FD.$("#cmpBody");
        const sel = st.sel.map((id) => S.find((s) => s.id === id));
        if (sel.length < 2) { body.innerHTML = `<div class="card empty" style="margin-top:18px"><i class="fa-solid fa-code-compare"></i>Select at least two samples — or one, then <b>Add most similar</b>.</div>`; return; }
        const common = CORE.filter((k) => sel.every((s) => s.metrics[k] != null));
        const commonCh = sel.map((s) => s.channels).reduce((a, b) => a.filter((c) => b.includes(c)));
        const excluded = CORE.filter((k) => !common.includes(k) && sel.some((s) => s.metrics[k] != null));
        if (!common.includes(st.metric)) st.metric = common[0];
        if (!commonCh.includes(st.channel)) st.channel = commonCh.find((c) => c.startsWith("Radiometer")) || commonCh[0];
        const col = (i) => FD.palette[i % FD.palette.length];
        body.innerHTML = `
          <div class="grid" style="margin-top:18px">
            <section class="card span-12" style="--i:1"><div class="card-head"><div><h3>2 · Common ground</h3><div class="sub">${common.length} shared parameters · ${commonCh.length} shared sensor channels${excluded.length ? ` · excluded (not available in every file): ${excluded.map((k) => FD.METRICS[k].label).join(", ")}` : ""}</div></div><span class="card-icon"><i class="fa-solid fa-equals"></i></span></div>
              <div class="chips">${sel.map((s, i) => `<span class="tag" style="border-color:${col(i)};color:${col(i)}"><i class="fa-solid fa-circle" style="font-size:8px"></i> ${s.id}${s.meta.flow_direction ? " · " + s.meta.flow_direction : ""}${i === 0 ? " · reference" : ""}</span>`).join("")}</div>
              <div id="insights" style="margin-top:12px"></div></section>

            <section class="card span-7" style="--i:2"><div class="card-head"><div><h3>Side-by-side parameters</h3><div class="sub">Δ relative to the reference (first sample)</div></div></div>
              <div class="table-wrap" style="max-height:none"><table class="data"><thead><tr><th>Parameter</th>${sel.map((s, i) => `<th style="color:${col(i)}">${s.mission.replace("SAFFIRE-", "S-")} ${s.sample}</th>`).join("")}</tr></thead>
              <tbody>${common.map((k) => {
                const d = FD.METRICS[k], ref = sel[0].metrics[k];
                const vals = sel.map((s) => s.metrics[k]), mx = Math.max(...vals);
                return `<tr data-k="${k}" style="cursor:pointer" title="${FD.esc(d.desc)}"><td><i class="fa-solid ${d.icon}" style="color:var(--muted);width:18px"></i> ${d.label} <span class="muted">(${d.unit})</span></td>${sel.map((s, i) => {
                  const v = s.metrics[k]; const delta = i && ref ? ((v - ref) / Math.abs(ref)) * 100 : null;
                  return `<td class="mono" style="${v === mx && sel.length > 1 ? "font-weight:700;color:var(--text)" : ""}">${FD.fmt(v, d.dec)}${delta != null && isFinite(delta) ? ` <small class="${delta > 0 ? "delta-up" : "delta-down"}">${delta > 0 ? "+" : ""}${FD.fmt(delta, 0)}%</small>` : ""}</td>`;
                }).join("")}</tr>`;
              }).join("")}</tbody></table></div>
              <p class="note"><i class="fa-solid fa-hand-pointer"></i><span>Click a row to plot that parameter.</span></p></section>

            <section class="card span-5" style="--i:3"><div class="card-head"><div><h3>Fire fingerprint</h3><div class="sub">Normalized against all 13 SAFFIRE samples (0 = min, 1 = max)</div></div></div><div id="radar"></div></section>

            <section class="card span-5" style="--i:4"><div class="card-head"><div><h3 id="barTitle">Parameter</h3><div class="sub" id="barSub"></div></div></div><div id="mBar"></div>
              <div class="chips" id="metricChips" style="margin-top:10px">${common.map((k) => `<span class="chip ${k === st.metric ? "on" : ""}" data-k="${k}">${FD.METRICS[k].label}</span>`).join("")}</div></section>

            <section class="card span-7" style="--i:5"><div class="card-head"><div><h3>Time-series overlay</h3><div class="sub">Shared channel, t = 0 at ignition</div></div>
              <select class="select" id="chSel" style="width:auto">${commonCh.map((c) => `<option ${c === st.channel ? "selected" : ""}>${FD.esc(c)}</option>`).join("")}</select></div><div id="overlay"></div></section>
          </div>`;

        // radar
        FD.charts.radar(FD.$("#radar"), { axes: RADAR.map((k) => FD.METRICS[k].label.replace("Peak ", "").replace("Radiative heat-flux rise", "Heat flux")), series: sel.map((s, i) => ({ name: s.id, color: col(i), values: RADAR.map((k) => { const v = s.metrics[k]; if (v == null) return 0; const r = ST[k]; return Math.log1p(Math.max(0, v - Math.min(0, r.min))) / Math.log1p(r.max - Math.min(0, r.min) || 1); }) })), size: 300 });
        // barres
        const drawBar = () => {
          const d = FD.METRICS[st.metric];
          FD.$("#barTitle").textContent = d.label;
          FD.$("#barSub").textContent = d.desc;
          FD.$$("#metricChips .chip").forEach((c) => c.classList.toggle("on", c.dataset.k === st.metric));
          FD.charts.bar(FD.$("#mBar"), { labels: sel.map((s) => s.mission.replace("SAFFIRE-", "S-") + " " + s.sample), series: [{ name: d.label, values: sel.map((s) => s.metrics[st.metric]), colors: sel.map((_, i) => col(i)) }], unit: d.unit, height: 230 });
        };
        FD.$$("#metricChips .chip").forEach((c) => c.onclick = () => { st.metric = c.dataset.k; drawBar(); });
        FD.$$("tr[data-k]").forEach((r) => r.onclick = () => { st.metric = r.dataset.k; drawBar(); FD.$("#mBar").scrollIntoView({ behavior: "smooth", block: "center" }); });
        drawBar();
        // superposition temporelle
        const drawOverlay = async () => {
          const sers = await Promise.all(sel.map((s) => FD.series(s.slug)));
          FD.charts.line(FD.$("#overlay"), { series: sers.map((sr, i) => ({ name: sel[i].id, unit: sr.channels[st.channel]?.unit, x: sr.t.map((t) => t - (sel[i].metrics.ignition_time_s || 0)), y: sr.channels[st.channel]?.y || [], color: col(i) })), height: 280, xName: "t", xUnit: " s", xLabel: "time since ignition (s)", yLabel: sers[0].channels[st.channel]?.unit, markers: [{ x: 0, label: "Ignition", color: "var(--warn)" }] });
        };
        FD.$("#chSel").onchange = (e) => { st.channel = e.target.value; drawOverlay(); };
        drawOverlay();
        // enseignements automatiques
        const ins = [];
        const by = (k) => [...sel].sort((a, b) => (b.metrics[k] || 0) - (a.metrics[k] || 0));
        if (common.includes("radiometer_rise_mw_cm2")) { const o = by("radiometer_rise_mw_cm2"); const r = o[0].metrics.radiometer_rise_mw_cm2 / Math.max(0.1, o[o.length - 1].metrics.radiometer_rise_mw_cm2); ins.push(`<b>${o[0].id}</b> radiated <b>${FD.fmt(r, 1)}×</b> more heat than <b>${o[o.length - 1].id}</b> — a larger, more dangerous flame for neighbouring materials.`); }
        if (common.includes("flame_duration_s")) { const o = by("flame_duration_s"); ins.push(`Longest-lived flame: <b>${o[0].id}</b> (${FD.fmt(o[0].metrics.flame_duration_s, 0)} s) vs. shortest <b>${o[o.length - 1].id}</b> (${FD.fmt(o[o.length - 1].metrics.flame_duration_s, 0)} s).`); }
        if (common.includes("airflow_median_cm_s")) { const fl = sel.map((s) => s.metrics.airflow_median_cm_s); if (Math.max(...fl) - Math.min(...fl) > 2) ins.push(`Airflow differs (${fl.map((f) => FD.fmt(f, 0)).join(" / ")} cm/s): in microgravity the forced flow controls oxygen supply, so part of the difference is ventilation-driven.`); else ins.push(`Same imposed airflow (~${FD.fmt(fl[0], 0)} cm/s): differences come from material, geometry or flow direction rather than ventilation.`); }
        const flows = sel.map((s) => s.meta.flow_direction).filter(Boolean);
        if (new Set(flows).size > 1) ins.push(`Flow direction differs (${flows.join(" vs ")}): concurrent spread pre-heats the fuel ahead of the flame, opposed spread does not.`);
        FD.$("#insights").innerHTML = ins.map((t) => `<div class="finding"><span class="n"><i class="fa-solid fa-lightbulb"></i></span><p>${t}</p></div>`).join("");
      };
      update();
    },
  };
})();

/* FLAME DNA — Data Explorer : naviguer dans les FICHIERS NASA (SAFFIRE) canal par canal
   + classement des investigations NASA de combustion en microgravité par pertinence */
(function () {
  const FD = window.FD;
  const st = { tab: "files", sel: "SAFFIRE-I-S1", channels: ["Radiometer 1", "Radiometer 2", "Radiometer 3", "Radiometer 4"], normalize: false, align: true, focus: "habitat", open: new Set(["SAFFIRE-I"]) };
  const GROUP_META = {
    atmosphere: ["fa-lungs", "Cabin atmosphere"], flow: ["fa-wind", "Airflow"], radiation: ["fa-sun", "Radiometers"],
    plume: ["fa-smog", "Plume thermocouples"], sample: ["fa-temperature-high", "Sample thermocouples"], inlet: ["fa-door-open", "Inlet"], igniter: ["fa-bolt", "Igniter"],
  };
  const FOCUS = {
    habitat: { label: "Habitat design", w: { habitat_scale: 3, material_flammability: 2, detection: 1, suppression: 1, predictive_modeling: 1 } },
    detection: { label: "Detection", w: { habitat_scale: 1, material_flammability: 1, detection: 3, suppression: 0.5, predictive_modeling: 1 } },
    suppression: { label: "Suppression", w: { habitat_scale: 1, material_flammability: 0.5, detection: 0.5, suppression: 3, predictive_modeling: 1 } },
    modeling: { label: "Predictive modeling", w: { habitat_scale: 1, material_flammability: 2, detection: 0.5, suppression: 0.5, predictive_modeling: 3 } },
  };

  FD.pages.explorer = {
    title: "Data Explorer",
    subtitle: "Open the NASA microgravity data files themselves: browse every SAFFIRE sample channel by channel, and find the investigations that matter most for crew fire safety.",
    async render(view) {
      const [idx, kn] = await Promise.all([FD.saffire(), FD.knowledge()]);
      view.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px">
          <div class="seg" id="tabSeg"><button data-k="files"><i class="fa-solid fa-folder-open"></i> NASA data files</button><button data-k="inv"><i class="fa-solid fa-ranking-star"></i> Investigations ranking</button></div>
          <span class="muted" style="font-size:12.5px"><i class="fa-solid fa-database" style="color:var(--accent)"></i> ${idx.samples.length} files · source: ${FD.esc(idx.source)}</span>
        </div>
        <div id="tabBody"></div>`;
      const body = FD.$("#tabBody");
      const show = () => {
        FD.$$("#tabSeg button").forEach((b) => b.classList.toggle("on", b.dataset.k === st.tab));
        body.innerHTML = "";
        body.classList.remove("entering"); void body.offsetWidth; body.classList.add("entering");
        st.tab === "files" ? renderFiles(body, idx) : renderInv(body, kn, idx);
      };
      FD.$$("#tabSeg button").forEach((b) => b.onclick = () => { st.tab = b.dataset.k; show(); });
      show();
    },
  };

  /* ---------------- FICHIERS ---------------- */
  function renderFiles(body, idx) {
    const missions = [...new Set(idx.samples.map((s) => s.mission))];
    body.innerHTML = `
      <div class="explorer">
        <aside class="card tree" style="--i:0">
          <div class="search" style="margin-bottom:8px"><i class="fa-solid fa-filter"></i><input class="input" id="fileFilter" placeholder="Filter files…"></div>
          ${missions.map((m) => `
            <div class="tree-group ${st.open.has(m) ? "open" : ""}" data-m="${m}">
              <button><i class="fa-solid fa-satellite" style="color:${FD.MISSION_COLOR[m]}"></i> ${m} <span class="tag" style="margin-left:6px">${idx.samples.filter((s) => s.mission === m).length}</span><i class="fa-solid fa-chevron-right chev"></i></button>
              <div class="tree-items"><div>${idx.samples.filter((s) => s.mission === m).map((s) => `
                <div class="file ${s.id === st.sel ? "on" : ""}" data-id="${s.id}"><i class="fa-solid fa-file-excel"></i><span>${s.sample}.xlsx</span><span class="sz">${FD.fmtInt(s.metrics.records)} rows</span></div>`).join("")}</div></div>
            </div>`).join("")}
          <p class="note" style="padding:0 6px"><i class="fa-solid fa-circle-info"></i><span>Each file = one burned sample. Sheet read: <b>Calibrated Data</b> (NASA-calibrated units).</span></p>
        </aside>
        <div id="filePane"></div>
      </div>`;
    FD.$$(".tree-group > button", body).forEach((b) => b.onclick = () => { const g = b.parentElement; g.classList.toggle("open"); g.classList.contains("open") ? st.open.add(g.dataset.m) : st.open.delete(g.dataset.m); });
    FD.$$(".file", body).forEach((f) => f.onclick = () => { st.sel = f.dataset.id; FD.$$(".file", body).forEach((x) => x.classList.toggle("on", x === f)); renderFile(idx); });
    FD.$("#fileFilter").addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      FD.$$(".file", body).forEach((f) => (f.style.display = f.dataset.id.toLowerCase().includes(q) ? "" : "none"));
      if (q) FD.$$(".tree-group", body).forEach((g) => g.classList.add("open"));
    });
    renderFile(idx);
  }

  async function renderFile(idx) {
    const pane = FD.$("#filePane");
    const s = idx.samples.find((x) => x.id === st.sel);
    pane.innerHTML = `<div class="card skeleton" style="height:420px"></div>`;
    const ser = await FD.series(s.slug);
    const m = s.metrics;
    st.channels = st.channels.filter((c) => ser.channels[c]);
    if (!st.channels.length) st.channels = ["Radiometer 1"].filter((c) => ser.channels[c]);
    const keyMetrics = ["flame_duration_s", "radiometer_rise_mw_cm2", "sample_temp_peak_c", "plume_temp_peak_c", "o2_drop_pct", "co2_rise_pct", "airflow_median_cm_s", "o2_initial_pct"];
    const conf = { high: ["ok", "strong radiometer signal"], medium: ["warn", "moderate signal"], low: ["danger", "weak signal — interpret with care"] }[m.flame_confidence] || ["", "not resolved"];
    pane.innerHTML = `
      <section class="card" style="--i:1">
        <div class="card-head">
          <div><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><h3 style="font-size:19px">${s.id}</h3><span class="tag" style="color:${FD.MISSION_COLOR[s.mission]}">${s.vehicle} · ${s.year}</span><span class="tag ${conf[0]}">flame: ${conf[1]}</span></div>
          <div class="sub"><i class="fa-regular fa-file"></i> ${FD.esc(s.source_file)} · ${FD.fmtInt(m.records)} records · ${FD.fmt(m.duration_s, 0)} s · ${s.channels.length} channels${s.meta.material ? ` · <b>${FD.esc(s.meta.material)}</b>, ${FD.esc(s.meta.flow_direction)} flow, ${s.meta.size_cm} cm` : ""}</div></div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn sm" id="dlCsv"><i class="fa-solid fa-file-csv"></i> CSV</button>
            <a class="btn sm primary" href="#/compare" id="toCompare"><i class="fa-solid fa-code-compare"></i> Compare similar</a>
          </div>
        </div>
        <div class="metric-grid">${keyMetrics.map((k) => { const d = FD.METRICS[k]; return `<div class="metric" title="${FD.esc(d.desc)}"><div class="k"><i class="fa-solid ${d.icon}"></i> ${d.label}</div><div class="v"><span data-count="${m[k] ?? ""}" data-dec="${d.dec}">0</span> <small>${d.unit}</small></div></div>`; }).join("")}</div>
      </section>

      <section class="card" style="--i:2;margin-top:18px">
        <div class="card-head"><div><h3>Channel viewer</h3><div class="sub">Pick channels below — the curve redraws instantly</div></div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <span class="chip ${st.normalize ? "on" : ""}" id="normChip"><i class="fa-solid fa-arrows-up-down"></i> Normalize 0–1</span>
            <span class="chip ${st.align ? "on" : ""}" id="alignChip"><i class="fa-solid fa-bolt"></i> t = 0 at ignition</span>
          </div></div>
        <div id="chView"></div>
        <div id="chGroups" style="display:grid;gap:12px;margin-top:16px"></div>
      </section>

      <section class="card" style="--i:3;margin-top:18px">
        <div class="card-head"><div><h3>Data preview</h3><div class="sub">Downsampled view (≈500 time bins, mean per bin) of the selected channels</div></div></div>
        <div class="table-wrap" id="preview"></div>
      </section>`;
    FD.animateCounts(pane);

    const groups = FD.$("#chGroups");
    groups.innerHTML = Object.entries(idx.channel_groups).map(([g, list]) => {
      const avail = list.filter((c) => ser.channels[c]);
      if (!avail.length) return "";
      return `<div><div class="muted" style="font-size:12px;margin-bottom:6px"><i class="fa-solid ${GROUP_META[g][0]}"></i> ${GROUP_META[g][1]}</div><div class="channel-picker">${avail.map((c) => `<span class="chip ${st.channels.includes(c) ? "on" : ""}" data-c="${FD.esc(c)}">${FD.esc(c.replace(/ \(TC\d+\)/, ""))} <small style="opacity:.7">${FD.esc(ser.channels[c].unit)}</small></span>`).join("")}</div></div>`;
    }).join("");

    const draw = () => {
      const t0 = st.align ? (m.ignition_time_s || 0) : 0;
      const x = ser.t.map((v) => v - t0);
      const series = st.channels.map((c, i) => {
        let y = ser.channels[c].y;
        if (st.normalize) { const v = y.filter((a) => a != null); const mn = Math.min(...v), mx = Math.max(...v); y = y.map((a) => (a == null ? null : (a - mn) / (mx - mn || 1))); }
        return { name: c, unit: st.normalize ? "" : ser.channels[c].unit, x, y, color: FD.palette[i % FD.palette.length] };
      });
      const units = [...new Set(st.channels.map((c) => ser.channels[c].unit))];
      const markers = [{ x: (m.ignition_time_s || 0) - t0, label: "Ignition", color: "var(--warn)" }];
      if (m.flame_signal_start_s != null) markers.push({ x: m.flame_signal_end_s - t0, label: "Flame end", color: "var(--cyan)" });
      FD.charts.line(FD.$("#chView"), { series, height: 320, area: st.channels.length <= 2, yLabel: st.normalize ? "normalized" : units.join(" · "), xLabel: st.align ? "time since ignition (s)" : "elapsed time (s)", xName: "t", xUnit: " s", markers });
      // aperçu tabulaire
      const step = Math.max(1, Math.floor(ser.t.length / 60));
      const rows = [];
      for (let i = 0; i < ser.t.length; i += step) rows.push(i);
      FD.$("#preview").innerHTML = `<table class="data"><thead><tr><th>t (s)</th>${st.channels.map((c) => `<th>${FD.esc(c)} <span style="text-transform:none">(${FD.esc(ser.channels[c].unit)})</span></th>`).join("")}</tr></thead><tbody>${rows.map((i) => `<tr><td class="mono">${FD.fmt(ser.t[i], 1)}</td>${st.channels.map((c) => `<td class="mono">${FD.fmt(ser.channels[c].y[i], 3)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    };
    FD.$$(".chip[data-c]", groups).forEach((ch) => ch.onclick = () => {
      const c = ch.dataset.c;
      if (st.channels.includes(c)) { if (st.channels.length > 1) st.channels = st.channels.filter((x) => x !== c); }
      else st.channels = [...st.channels, c].slice(-8);
      FD.$$(".chip[data-c]", groups).forEach((x) => x.classList.toggle("on", st.channels.includes(x.dataset.c)));
      draw();
    });
    FD.$("#normChip").onclick = (e) => { st.normalize = !st.normalize; e.currentTarget.classList.toggle("on", st.normalize); draw(); };
    FD.$("#alignChip").onclick = (e) => { st.align = !st.align; e.currentTarget.classList.toggle("on", st.align); draw(); };
    FD.$("#dlCsv").onclick = () => {
      const cols = Object.keys(ser.channels);
      const lines = ["t_s," + cols.map((c) => `"${c} (${ser.channels[c].unit})"`).join(",")];
      ser.t.forEach((t, i) => lines.push([t, ...cols.map((c) => ser.channels[c].y[i] ?? "")].join(",")));
      FD.download(`${s.slug}_downsampled.csv`, lines.join("\n"));
      FD.toast("CSV exported", ` — ${cols.length} channels, ${ser.t.length} rows`, "ok");
    };
    FD.$("#toCompare").onclick = () => { FD.compareSeed = s.id; };
    draw();
  }

  /* ---------------- INVESTIGATIONS ---------------- */
  function renderInv(body, kn) {
    const labels = kn.criteria_labels;
    body.innerHTML = `
      <section class="card" style="--i:0;margin-bottom:18px">
        <div class="card-head"><div><h3>Which NASA investigations matter most for crew fire safety?</h3><div class="sub">Each investigation is scored on five transparent criteria. Choose your priority — the ranking updates.</div></div><span class="card-icon"><i class="fa-solid fa-ranking-star"></i></span></div>
        <div class="seg" id="focusSeg">${Object.entries(FOCUS).map(([k, v]) => `<button data-k="${k}">${v.label}</button>`).join("")}</div>
      </section>
      <div class="grid"><div class="span-8" id="invList" style="display:grid;gap:14px"></div>
        <aside class="span-4"><section class="card" style="--i:2;position:sticky;top:16px"><div class="card-head"><div><h3>Top-3 profile</h3><div class="sub">Criteria coverage of the leading investigations</div></div></div><div id="invRadar"></div></section></aside></div>`;
    const draw = () => {
      FD.$$("#focusSeg button").forEach((b) => b.classList.toggle("on", b.dataset.k === st.focus));
      const w = FOCUS[st.focus].w, wsum = Object.values(w).reduce((a, b) => a + b, 0);
      const ranked = kn.investigations.map((inv) => ({ ...inv, score: Object.keys(w).reduce((a, k) => a + w[k] * (inv.criteria[k] || 0), 0) / wsum })).sort((a, b) => b.score - a.score);
      FD.$("#invList").innerHTML = ranked.map((inv, i) => `
        <article class="card lift" style="--i:${i}">
          <div class="inv">
            <div class="score" id="sc-${inv.id}"></div>
            <div style="min-width:0">
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="mono muted">#${i + 1}</span><h4 style="font-size:15px">${FD.esc(inv.name)}</h4>${inv.local ? `<span class="tag ok"><i class="fa-solid fa-database"></i> data in FLAME DNA</span>` : ""}</div>
              <div class="muted" style="font-size:12.5px;margin:2px 0 6px"><i class="fa-solid fa-satellite-dish"></i> ${FD.esc(inv.platform)} · ${inv.years} · ${FD.esc(inv.lab)}</div>
              <p style="margin:0 0 6px;font-size:13px;color:var(--text-2)">${FD.esc(inv.focus)}</p>
              <p style="margin:0;font-size:13px"><i class="fa-solid fa-shield-halved" style="color:var(--accent)"></i> ${FD.esc(inv.fire_safety)}</p>
              <div class="chips" style="margin-top:8px">${inv.tags.map((t) => `<span class="tag">${t}</span>`).join("")}</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:8px">
              ${inv.local ? `<a class="btn sm primary" href="#/explorer" data-open-files><i class="fa-solid fa-folder-open"></i> Open files</a>` : ""}
              <a class="btn sm" href="https://ntrs.nasa.gov/search?q=${encodeURIComponent(inv.query)}" target="_blank" rel="noopener"><i class="fa-solid fa-file-lines"></i> NTRS papers</a>
              <a class="btn sm ghost" href="https://psi.nasa.gov/" target="_blank" rel="noopener"><i class="fa-solid fa-database"></i> PSI</a>
            </div>
          </div>
        </article>`).join("");
      ranked.forEach((inv) => FD.charts.ring(FD.$(`#sc-${inv.id}`), { size: 58, thickness: 6, value: inv.score, label: "", gradient: ["#D9A441", "#F36B21"] }));
      FD.$$(".score .v").forEach((v) => (v.style.fontSize = "15px"));
      FD.$$("[data-open-files]").forEach((a) => a.onclick = (e) => { e.preventDefault(); st.tab = "files"; FD.$('#tabSeg button[data-k="files"]').click(); });
      const keys = Object.keys(labels);
      FD.charts.radar(FD.$("#invRadar"), { axes: keys.map((k) => labels[k]), series: ranked.slice(0, 3).map((inv, i) => ({ name: inv.id, values: keys.map((k) => inv.criteria[k]), color: FD.palette[[0, 1, 3][i]] })), size: 300 });
    };
    FD.$$("#focusSeg button").forEach((b) => b.onclick = () => { st.focus = b.dataset.k; draw(); });
    draw();
  }
})();

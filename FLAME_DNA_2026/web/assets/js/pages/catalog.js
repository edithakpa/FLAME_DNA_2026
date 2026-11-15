/* FLAME DNA — Catalogue de recherche NASA : bibliothèque de publications + sites de référence
   (différent du Data Explorer, qui manipule les FICHIERS de données) */
(function () {
  const FD = window.FD;
  const SITES = [
    { name: "NASA Physical Sciences Informatics (PSI)", url: "https://psi.nasa.gov/", icon: "fa-database", desc: "Open repository of microgravity physical-science data — source of the SAFFIRE files.", tag: "Data" },
    { name: "NASA Technical Reports Server (NTRS)", url: "https://ntrs.nasa.gov/", icon: "fa-file-lines", desc: "Full-text NASA papers, presentations and reports — source of this catalog.", tag: "Papers" },
    { name: "SAFFIRE mission page", url: "https://www.nasa.gov/mission/saffire/", icon: "fa-fire-flame-curved", desc: "Overview of the Spacecraft Fire Safety Experiments flown on Cygnus.", tag: "Mission" },
    { name: "NASA Spinoff", url: "https://spinoff.nasa.gov/", icon: "fa-earth-americas", desc: "How NASA technology — including fire-safety tech — reaches everyday life on Earth.", tag: "Earth" },
    { name: "PSI on data.gov", url: "https://catalog.data.gov/dataset/physical-sciences-informatics-psi-system-data-repository-international-space-station-iss", icon: "fa-landmark", desc: "Federal open-data listing of the PSI ISS repository.", tag: "Open data" },
  ];
  let state = { q: "", topics: new Set(), types: new Set(), minRel: 20, sort: "relevance" };

  FD.pages.catalog = {
    title: "NASA Research Catalog",
    subtitle: "A curated library of NASA publications and reference sites on microgravity combustion — ranked by their relevance to crew fire safety.",
    async render(view) {
      const pubs = await FD.publications();
      const topics = count(pubs, "topic"), types = count(pubs, "type");
      view.innerHTML = `
      <div class="section-title" style="margin-top:4px">Reference sites</div>
      <div class="grid" id="sites">${SITES.map((s, i) => `
        <a class="card lift site-card span-${i < 3 ? 4 : 6}" style="--i:${i};text-decoration:none;color:var(--text)" href="${s.url}" target="_blank" rel="noopener">
          <span class="card-icon"><i class="fa-solid ${s.icon}"></i></span>
          <div style="min-width:0"><div style="display:flex;gap:8px;align-items:center"><h4 style="font-size:14.5px">${s.name}</h4><span class="tag">${s.tag}</span></div>
          <p class="muted" style="margin:4px 0 0;font-size:12.5px">${s.desc}</p><span style="font-size:12px;color:var(--accent)">${new URL(s.url).host} <i class="fa-solid fa-arrow-up-right-from-square"></i></span></div>
        </a>`).join("")}</div>

      <div class="section-title">Publication library</div>
      <div class="lib-layout">
        <aside class="card facet" style="--i:5;align-self:start;position:sticky;top:16px">
          <div class="search"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="q" placeholder="Search title, abstract, author…" value="${FD.esc(state.q)}"></div>
          <h4>Fire-safety relevance</h4>
          <input type="range" class="slider" id="rel" min="0" max="90" step="10" value="${state.minRel}"><div class="muted" style="font-size:12px">Minimum score: <b id="relV">${state.minRel}</b></div>
          <h4>Topic</h4>${Object.entries(topics).map(([k, n]) => `<label><input type="checkbox" data-f="topics" value="${FD.esc(k)}" ${state.topics.has(k) ? "checked" : ""}> ${FD.esc(k)}<span class="c">${n}</span></label>`).join("")}
          <h4>Document type</h4>${Object.entries(types).map(([k, n]) => `<label><input type="checkbox" data-f="types" value="${FD.esc(k)}" ${state.types.has(k) ? "checked" : ""}> ${FD.esc(k)}<span class="c">${n}</span></label>`).join("")}
          <h4>Publications per decade</h4><div id="decades"></div>
        </aside>
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px">
            <div class="muted" id="count"></div>
            <div class="seg" id="sortSeg"><button data-k="relevance"><i class="fa-solid fa-fire"></i> Relevance</button><button data-k="year"><i class="fa-solid fa-calendar"></i> Newest</button><button data-k="title"><i class="fa-solid fa-arrow-down-a-z"></i> Title</button></div>
          </div>
          <div class="pub-grid" id="pubs"></div>
        </div>
      </div>`;

      const dec = {};
      pubs.forEach((p) => { const y = +p.year; if (y) { const d = Math.floor(y / 10) * 10; dec[d] = (dec[d] || 0) + 1; } });
      const dk = Object.keys(dec).sort();
      FD.charts.bar(FD.$("#decades"), { labels: dk.map((d) => "'" + String(d).slice(2)), series: [{ name: "Publications", values: dk.map((d) => dec[d]), color: "var(--accent)" }], height: 150, pad: { l: 26, r: 4, t: 8, b: 26 } });

      const draw = () => {
        const q = state.q.trim().toLowerCase();
        const terms = q.split(/\s+/).filter(Boolean);
        let list = pubs.filter((p) => p.relevance >= state.minRel
          && (!state.topics.size || state.topics.has(p.topic))
          && (!state.types.size || state.types.has(p.type))
          && terms.every((t) => (p.title + " " + p.abstract + " " + p.authors).toLowerCase().includes(t)));
        list.sort(state.sort === "year" ? (a, b) => b.year - a.year : state.sort === "title" ? (a, b) => a.title.localeCompare(b.title) : (a, b) => b.relevance - a.relevance);
        FD.$("#count").innerHTML = `<b style="color:var(--text)">${list.length}</b> of ${pubs.length} publications`;
        FD.$$("#sortSeg button").forEach((b) => b.classList.toggle("on", b.dataset.k === state.sort));
        const hl = (s) => { let out = FD.esc(s); terms.forEach((t) => { if (t.length > 1) out = out.replace(new RegExp(`(${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"), "<mark>$1</mark>"); }); return out; };
        FD.$("#pubs").innerHTML = list.length ? list.map((p, i) => `
          <article class="card pub lift" style="--i:${Math.min(i, 12)}" data-id="${p.id}">
            <div style="display:flex;gap:6px;flex-wrap:wrap"><span class="tag orange">${FD.esc(p.topic)}</span><span class="tag">${FD.esc(p.type)}</span><span class="tag">${p.year || "n.d."}</span></div>
            <h4>${hl(p.title)}</h4>
            <div class="meta"><i class="fa-solid fa-user-pen"></i> ${FD.esc(p.authors || "NASA")}</div>
            <p class="abs">${hl(p.abstract || "No abstract available.")}</p>
            <div style="margin-top:auto"><div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-bottom:4px"><span>Fire-safety relevance</span><b class="mono" style="color:var(--text)">${p.relevance}</b></div><div class="relbar"><span style="width:${p.relevance}%;animation-delay:${Math.min(i, 12) * 50}ms"></span></div></div>
          </article>`).join("") : `<div class="card empty" style="grid-column:1/-1"><i class="fa-solid fa-magnifying-glass"></i>No publication matches these filters.</div>`;
        FD.$$(".pub", FD.$("#pubs")).forEach((c) => c.onclick = () => openPub(pubs.find((p) => p.id === c.dataset.id), terms));
      };
      let deb;
      FD.$("#q").addEventListener("input", (e) => { clearTimeout(deb); deb = setTimeout(() => { state.q = e.target.value; draw(); }, 160); });
      FD.$("#rel").addEventListener("input", (e) => { state.minRel = +e.target.value; FD.$("#relV").textContent = state.minRel; draw(); });
      FD.$$("[data-f]").forEach((c) => c.addEventListener("change", () => { const set = state[c.dataset.f]; c.checked ? set.add(c.value) : set.delete(c.value); draw(); }));
      FD.$$("#sortSeg button").forEach((b) => b.onclick = () => { state.sort = b.dataset.k; draw(); });
      draw();
    },
  };

  function openPub(p, terms) {
    FD.drawer(`
      <span class="tag orange">${FD.esc(p.topic)}</span> <span class="tag">${FD.esc(p.type)}</span> <span class="tag">${p.year}</span>
      <h2 style="font-size:21px;margin:14px 0 8px;line-height:1.3">${FD.esc(p.title)}</h2>
      <div class="muted" style="font-size:13px"><i class="fa-solid fa-user-pen"></i> ${FD.esc(p.authors || "NASA")}</div>
      <div style="display:flex;gap:16px;align-items:center;margin:18px 0"><div id="pubRing"></div><div class="muted" style="font-size:13px">Relevance score combines weighted mentions of fire safety, flame spread, flammability, suppression, detection, ignition and crewed habitats in the title & abstract.</div></div>
      <h4 style="margin:10px 0 6px">Abstract</h4><p style="color:var(--text-2);font-size:14px;line-height:1.7">${FD.esc(p.abstract || "No abstract available.")}</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px">
        <a class="btn primary" href="${p.url}" target="_blank" rel="noopener"><i class="fa-solid fa-arrow-up-right-from-square"></i> Open on NTRS</a>
        <a class="btn" href="#/assistant?q=${encodeURIComponent("Summarize: " + p.title)}"><i class="fa-solid fa-wand-magic-sparkles"></i> Ask the AI about it</a>
      </div>
      <p class="note"><i class="fa-solid fa-hashtag"></i><span>NTRS ID <span class="mono">${p.id}</span> · source: ${FD.esc(p.source)}</span></p>`);
    FD.charts.ring(FD.$("#pubRing"), { size: 96, thickness: 9, value: p.relevance / 100, label: "relevance", gradient: ["#D9A441", "#F36B21"] });
  }
  function count(arr, k) { const o = {}; arr.forEach((x) => (o[x[k]] = (o[x[k]] || 0) + 1)); return Object.fromEntries(Object.entries(o).sort((a, b) => b[1] - a[1])); }
})();

/* FLAME DNA — Assistant IA
   Moteur hybride :
   1) moteur local (toujours disponible) : détection d'intention, requêtes sur les données SAFFIRE,
      état de la surveillance en direct, base de connaissances, recherche BM25 dans les publications NASA,
      mémoire conversationnelle (échantillons cités) ;
   2) si /api/chat a un LLM configuré, il rédige la réponse à partir du MÊME contexte (réponse ancrée). */
(function () {
  const FD = window.FD;
  const chat = (FD.chatState = FD.chatState || { msgs: [], lastSamples: [], llm: null });

  /* ---------------- outils texte ---------------- */
  const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const STOP = new Set("the a an of in on for to and or is are be what which how why does do with from by as at it this that these those me my your about de la le les des du un une et ou est sont pour dans sur avec que qui quoi comment pourquoi quel quelle quels quelles en au aux ce cette ces se sa son il elle on nous vous je tu".split(" "));
  const tokens = (s) => norm(s).replace(/[^a-z0-9₂ ]+/g, " ").split(/\s+/).filter((t) => t.length > 1 && !STOP.has(t));
  const isFrench = (q) => /\b(quel|quelle|comment|pourquoi|est-ce|flamme|incendie|donn[ée]es|échantillon|echantillon|compare[rz]?|explique|selon|plus|moins|sécurité|securite|bonjour|merci|quoi|peux)\b/i.test(q);

  /* ---------------- BM25 sur les publications ---------------- */
  let bm = null;
  function buildBM25(pubs) {
    const docs = pubs.map((p) => tokens(p.title + " " + p.title + " " + p.abstract));
    const df = {}; docs.forEach((d) => new Set(d).forEach((t) => (df[t] = (df[t] || 0) + 1)));
    const avg = FD.stats.mean(docs.map((d) => d.length));
    return { pubs, docs, df, avg, N: docs.length };
  }
  function searchPubs(q, k = 3) {
    if (!bm) return [];
    const qt = tokens(q); const k1 = 1.4, b = 0.75;
    return bm.docs.map((d, i) => {
      let s = 0; const tf = {}; d.forEach((t) => (tf[t] = (tf[t] || 0) + 1));
      qt.forEach((t) => { if (!tf[t]) return; const idf = Math.log(1 + (bm.N - bm.df[t] + 0.5) / (bm.df[t] + 0.5)); s += (idf * tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + (b * d.length) / bm.avg)); });
      s *= 1 + bm.pubs[i].relevance / 200; // petit bonus pertinence sécurité incendie
      return { p: bm.pubs[i], s };
    }).filter((x) => x.s > 1.2).sort((a, b) => b.s - a.s).slice(0, k);
  }
  function bestSentences(text, q, n = 2) {
    const qt = new Set(tokens(q));
    return (text.match(/[^.!?]+[.!?]/g) || [text]).map((s) => ({ s: s.trim(), sc: tokens(s).filter((t) => qt.has(t)).length })).filter((x) => x.sc > 0).sort((a, b) => b.sc - a.sc).slice(0, n).map((x) => x.s);
  }

  /* ---------------- reconnaissance des échantillons ---------------- */
  function findSamples(q, S) {
    const n = norm(q).replace(/saffire[\s-]*/g, "saffire-");
    const found = [];
    const roman = { "1": "I", "2": "II", "3": "III", i: "I", ii: "II", iii: "III" };
    const re = /saffire-?(iii|ii|i|1|2|3)[\s,-]*(?:sample\s*)?s?(\d)/g;
    let m;
    while ((m = re.exec(n))) { const id = `SAFFIRE-${roman[m[1]]}-S${m[2]}`; if (S.find((s) => s.id === id) && !found.includes(id)) found.push(id); }
    if (!found.length) {
      const re2 = /\bs(\d)\b/g; let m2; const mission = /saffire-?(iii|ii|i|1|2|3)/.exec(n);
      while ((m2 = re2.exec(n))) { const id = `SAFFIRE-${mission ? roman[mission[1]] : (chat.lastSamples[0] || "SAFFIRE-I-").split("-")[1] || "I"}-S${m2[1]}`; if (S.find((s) => s.id === id) && !found.includes(id)) found.push(id); }
    }
    return found.map((id) => S.find((s) => s.id === id));
  }
  const METRIC_WORDS = [
    ["radiometer_rise_mw_cm2", /heat flux|radiat|radiom|intense|strongest|rayonn|flux/],
    ["sample_temp_peak_c", /hottest|temperature|temp[ée]rature|chaud|surface/],
    ["flame_duration_s", /longest|duration|dur[ée]e|long|lasted|burn time|shortest|court/],
    ["o2_drop_pct", /oxygen|o2|oxyg[eè]ne|consum/],
    ["co2_rise_pct", /co2|carbon dioxide|dioxyde/],
    ["plume_temp_peak_c", /plume|panache/],
    ["airflow_median_cm_s", /airflow|flow speed|ventilation|d[ée]bit|vitesse/],
  ];

  /* ---------------- moteur local ---------------- */
  async function localAnswer(q) {
    const [idx, kn] = await Promise.all([FD.saffire(), FD.knowledge()]);
    const S = idx.samples, nq = norm(q), fr = isFrench(q);
    const out = { md: "", sources: [], context: [], intent: "" };
    const samples = findSamples(q, S);
    if (samples.length) chat.lastSamples = samples.map((s) => s.id);
    const followUp = /\b(them|those|both|ces|les deux|eux)\b/.test(nq) && chat.lastSamples.length;
    const sel = samples.length ? samples : followUp ? chat.lastSamples.map((id) => S.find((s) => s.id === id)) : [];

    // 1. salutations / aide
    if (/^(hi|hello|hey|bonjour|salut|help|aide)\b/.test(nq) && nq.length < 40) {
      out.intent = "help";
      out.md = fr ? "Bonjour ! Je suis **FLAME DNA Copilot**. Je peux :\n\n- analyser les **13 échantillons SAFFIRE** (durée de flamme, flux radiatif, O₂, CO₂…) et les comparer ;\n- expliquer l'**état de la surveillance** en direct et la logique d'alerte ;\n- répondre sur la **physique des flammes en microgravité** et la sécurité des habitats ;\n- retrouver les **publications NASA** pertinentes.\n\nEssaie : *« Quel échantillon a le flux radiatif le plus élevé ? »*"
        : "Hi! I'm **FLAME DNA Copilot**. I can:\n\n- analyse the **13 SAFFIRE samples** (flame duration, heat flux, O₂, CO₂…) and compare them;\n- explain the **live monitoring** status and alert logic;\n- answer questions on **microgravity flame physics** and habitat fire safety;\n- find the relevant **NASA publications**.\n\nTry: *\"Which sample had the strongest heat flux?\"*";
      return out;
    }

    // 2. état de la surveillance en direct
    if (/\b(status|state|monitor|alert|alarm|current|now|cabin|etat|alerte|surveillance|maintenant|cabine|risque actuel|niveau)\b/.test(nq) && !sel.length) {
      const M = FD.monitor, s = M.cur || {}, lv = ["Nominal", "Watch", "Warning", "Fire alarm"][M.level];
      const ev = M.evidence ? Object.values(M.evidence).filter((e) => e.on || e.watch).map((e) => e.txt) : [];
      out.intent = "monitor";
      out.md = `**Live cabin status: ${lv}** (simulated · scenario *${M.scenario}* · habitat *${M.habitat}*)\n\n| Signal | Value |\n|---|---|\n| Smoke | ${FD.fmt(s.smoke, 2)} %/m |\n| CO | ${FD.fmt(s.co, 1)} ppm |\n| Rack temperature | ${FD.fmt(s.temp, 1)} °C |\n| Heat flux | ${FD.fmt(s.flux, 1)} mW/cm² |\n| O₂ | ${FD.fmt(s.o2, 2)} % |\n| Ventilation | ${FD.fmt(s.air, 1)} cm/s |\n\n${ev.length ? "Elevated signals: " + ev.join(" · ") + "." : "No signal outside its nominal band."}${M.faultSuspect ? "\n\nOnly one temperature channel deviates while smoke, CO and heat flux are clean → **likely sensor fault**, so no fire alarm." : ""}${M.level >= 2 ? "\n\n**Suggested response:** locate the source, prepare masks, then stop ventilation and remove rack power — in microgravity the airflow is what feeds the flame." : ""}\n\n*Simulated sensors — not a certified detection system.*`;
      out.sources.push({ t: "Open Real-Time Monitoring", u: "#/monitoring" });
      out.context.push("LIVE MONITORING: " + out.md);
      return out;
    }

    // 3. comparaison de deux échantillons ou plus
    if (sel.length >= 2 && /compar|versus|\bvs\b|diff|between|entre|both|les deux/.test(nq)) {
      const keys = ["flame_duration_s", "radiometer_rise_mw_cm2", "sample_temp_peak_c", "plume_temp_peak_c", "o2_drop_pct", "co2_rise_pct", "airflow_median_cm_s"].filter((k) => sel.every((s) => s.metrics[k] != null));
      out.intent = "compare";
      out.md = `**Comparison on ${keys.length} common parameters**\n\n| Parameter | ${sel.map((s) => s.id).join(" | ")} |\n|---|${sel.map(() => "---").join("|")}|\n` +
        keys.map((k) => `| ${FD.METRICS[k].label} (${FD.METRICS[k].unit}) | ${sel.map((s) => FD.fmt(s.metrics[k], FD.METRICS[k].dec)).join(" | ")} |`).join("\n");
      const a = sel[0], b = sel[1], ra = a.metrics.radiometer_rise_mw_cm2, rb = b.metrics.radiometer_rise_mw_cm2;
      if (ra && rb) out.md += `\n\n**${ra > rb ? a.id : b.id}** produced **${FD.fmt(Math.max(ra, rb) / Math.min(ra, rb), 1)}×** more radiant heat.`;
      if (a.meta.flow_direction && b.meta.flow_direction && a.meta.flow_direction !== b.meta.flow_direction) out.md += ` The flow direction differs (${a.meta.flow_direction} vs ${b.meta.flow_direction}): concurrent flow pre-heats the fuel ahead of the flame, opposed flow does not.`;
      out.sources.push({ t: "Open in Scientific Comparison", u: "#/compare" });
      out.context.push("DATA: " + out.md);
      FD.compareSeed = null;
      return out;
    }

    // 4. superlatifs (« quel échantillon a le plus… »)
    const mk = METRIC_WORDS.find(([, re]) => re.test(nq));
    if (mk && (/(which|what|most|highest|largest|strongest|longest|hottest|lowest|least|shortest|rank|top|quel|plus|moins|classement)/.test(nq)) && !sel.length) {
      const k = mk[0], d = FD.METRICS[k];
      const asc = /(lowest|least|shortest|weakest|moins|plus court|plus faible)/.test(nq);
      const ranked = S.filter((s) => s.metrics[k] != null).sort((x, y) => asc ? x.metrics[k] - y.metrics[k] : y.metrics[k] - x.metrics[k]);
      const top = ranked[0];
      out.intent = "rank";
      out.md = `**${top.id}** has the ${asc ? "lowest" : "highest"} ${d.label.toLowerCase()}: **${FD.fmt(top.metrics[k], d.dec)} ${d.unit}**${top.meta.material ? ` (${top.meta.material}, ${top.meta.flow_direction} flow)` : ""}.\n\n| Rank | Sample | ${d.label} (${d.unit}) |\n|---|---|---|\n${ranked.slice(0, 5).map((s, i) => `| ${i + 1} | ${s.id} | ${FD.fmt(s.metrics[k], d.dec)} |`).join("\n")}\n\n*${d.desc}*`;
      chat.lastSamples = ranked.slice(0, 2).map((s) => s.id);
      out.sources.push({ t: "Explore the files", u: "#/explorer" });
      out.context.push("DATA RANKING: " + out.md);
      return out;
    }

    // 5. un échantillon précis
    if (sel.length === 1) {
      const s = sel[0], m = s.metrics;
      out.intent = "sample";
      out.md = `**${s.id}** — ${s.vehicle}, ${s.year}${s.meta.material ? ` · ${s.meta.material}, ${s.meta.flow_direction} flow, ${s.meta.size_cm} cm` : ""}\n\n- Ignition at **t = ${FD.fmt(m.ignition_time_s, 0)} s**, flame signal for **${FD.fmt(m.flame_duration_s, 1)} s** (${m.flame_detection_method}, ${m.flame_confidence || "n/a"} confidence)\n- Radiative heat-flux rise **${FD.fmt(m.radiometer_rise_mw_cm2, 1)} mW/cm²**, peak at t = ${FD.fmt(m.radiometer_peak_time_s, 0)} s\n- Peak sample temperature **${FD.fmt(m.sample_temp_peak_c, 0)} °C**, plume **${FD.fmt(m.plume_temp_peak_c, 1)} °C**\n- Cabin O₂ ${FD.fmt(m.o2_initial_pct, 2)} % → −${FD.fmt(m.o2_drop_pct, 3)} %, CO₂ +${FD.fmt(m.co2_rise_pct, 3)} %\n- Imposed airflow ≈ **${FD.fmt(m.airflow_median_cm_s, 1)} cm/s**`;
      if (s.id === "SAFFIRE-I-S2") out.md += `\n\nNASA's test table reports a ~70 s burn for this opposed-flow sample; the radiometers resolve ~${FD.fmt(m.flame_duration_s, 0)} s above 10 % of peak because the opposed flame is small and dim.`;
      out.sources.push({ t: `Open ${s.id} in Data Explorer`, u: "#/explorer" });
      out.context.push("DATA: " + out.md);
      return out;
    }

    // 6. base de connaissances + publications
    const qt = tokens(q);
    const kbScored = kn.kb.map((e) => ({ e, s: e.keys.reduce((a, k) => a + (nq.includes(norm(k)) ? (k.length > 5 ? 2 : 1) : 0), 0) })).sort((a, b) => b.s - a.s);
    const pubs = searchPubs(q, 3);
    if (/summari[sz]e|r[ée]sume/.test(nq) && pubs.length) {
      const p = pubs[0].p;
      out.intent = "summary";
      out.md = `**${p.title}** (${p.year}, ${p.type})\n\n${bestSentences(p.abstract, q + " fire safety flame microgravity", 4).map((s) => "- " + s).join("\n") || p.abstract.slice(0, 600)}\n\nFire-safety relevance score: **${p.relevance}/100**.`;
      out.sources.push({ t: p.title, u: p.url });
      out.context.push(`PUBLICATION ${p.title}: ${p.abstract}`);
      return out;
    }
    if (kbScored[0].s >= 1) {
      const e = kbScored[0].e;
      out.intent = "kb";
      out.md = `**${e.title}**\n\n${e.answer}`;
      out.context.push(`KNOWLEDGE ${e.title}: ${e.answer}`);
      if (kbScored[1] && kbScored[1].s >= 2) out.context.push(`KNOWLEDGE ${kbScored[1].e.title}: ${kbScored[1].e.answer}`);
    }
    if (pubs.length) {
      const ex = pubs.map(({ p }) => ({ p, sent: bestSentences(p.abstract, q, 2) })).filter((x) => x.sent.length);
      if (!out.md && ex.length) {
        out.intent = "pubs";
        out.md = `Here is what the indexed NASA publications say:\n\n` + ex.map(({ p, sent }) => `**${p.title}** (${p.year})\n> ${sent.join(" ")}`).join("\n\n");
      } else if (ex.length) {
        out.md += `\n\n##### Related NASA research\n` + ex.slice(0, 2).map(({ p, sent }) => `- **${p.title}** (${p.year}) — ${sent[0]}`).join("\n");
      }
      pubs.forEach(({ p }) => { out.sources.push({ t: p.title, u: p.url }); out.context.push(`PUBLICATION ${p.title} (${p.year}): ${p.abstract.slice(0, 1200)}`); });
    }
    if (!out.md) {
      out.intent = "none";
      out.md = fr ? "Je n'ai pas trouvé d'élément suffisamment pertinent dans les données SAFFIRE, la base de connaissances ou les publications indexées. Essaie avec des mots-clés comme *flux radiatif*, *SAFFIRE-II S5*, *oxygène*, *écoulement opposé* ou *détection*."
        : "I couldn't find anything relevant enough in the SAFFIRE data, the knowledge base or the indexed NASA publications. Try keywords such as *heat flux*, *SAFFIRE-II S5*, *oxygen*, *opposed flow* or *detection*.";
    }
    // résumé compact des données en contexte pour le LLM
    out.context.push("DATASET SUMMARY: " + S.map((s) => `${s.id}: flame ${FD.fmt(s.metrics.flame_duration_s, 0)}s, heat-flux rise ${FD.fmt(s.metrics.radiometer_rise_mw_cm2, 1)} mW/cm2, sample peak ${FD.fmt(s.metrics.sample_temp_peak_c, 0)}C, O2 drop ${FD.fmt(s.metrics.o2_drop_pct, 3)}%, airflow ${FD.fmt(s.metrics.airflow_median_cm_s, 0)} cm/s`).join("; "));
    return out;
  }

  /* ---------------- mini-rendu Markdown ---------------- */
  function md(src) {
    const esc = FD.esc(src);
    const lines = esc.split("\n"); let html = "", list = null, table = null;
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/`(.+?)`/g, "<code>$1</code>").replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    const flush = () => { if (list) { html += `</${list}>`; list = null; } if (table) { html += "</table>"; table = null; } };
    lines.forEach((l) => {
      if (/^\|.*\|$/.test(l.trim())) {
        if (/^\|[\s|:-]+\|$/.test(l.trim())) return;
        const cells = l.trim().slice(1, -1).split("|").map((c) => inline(c.trim()));
        if (!table) { flush(); table = true; html += "<table><tr>" + cells.map((c) => `<th>${c}</th>`).join("") + "</tr>"; }
        else html += "<tr>" + cells.map((c) => `<td>${c}</td>`).join("") + "</tr>";
        return;
      }
      if (table) { html += "</table>"; table = null; }
      let m;
      if ((m = /^\s*[-•]\s+(.*)/.exec(l))) { if (list !== "ul") { flush(); list = "ul"; html += "<ul>"; } html += `<li>${inline(m[1])}</li>`; return; }
      if ((m = /^\s*\d+\.\s+(.*)/.exec(l))) { if (list !== "ol") { flush(); list = "ol"; html += "<ol>"; } html += `<li>${inline(m[1])}</li>`; return; }
      flush();
      if ((m = /^#{2,6}\s+(.*)/.exec(l))) html += `<h5>${inline(m[1])}</h5>`;
      else if ((m = /^&gt;\s?(.*)/.exec(l))) html += `<p style="border-left:3px solid var(--accent);padding-left:10px;color:var(--text-2)">${inline(m[1])}</p>`;
      else if (l.trim()) html += `<p>${inline(l)}</p>`;
    });
    flush();
    return html;
  }

  /* ---------------- LLM distant (optionnel) ---------------- */
  async function checkLLM() {
    if (chat.llm !== null) return chat.llm;
    try { const r = await fetch("api/chat", { method: "GET" }); chat.llm = r.ok ? (await r.json()).llm : false; } catch (e) { chat.llm = false; }
    return chat.llm;
  }
  async function remoteAnswer(q, local) {
    const r = await fetch("api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q, context: local.context.join("\n\n"), history: chat.msgs.slice(-6).map((m) => ({ role: m.role, content: m.text })) }) });
    if (!r.ok) throw new Error("LLM " + r.status);
    return (await r.json()).answer;
  }

  /* ---------------- PAGE ---------------- */
  const STARTERS = [
    ["fa-fire", "Which sample had the strongest heat flux?"],
    ["fa-code-compare", "Compare SAFFIRE-I S1 and SAFFIRE-I S2"],
    ["fa-tower-broadcast", "What is the current cabin alert status?"],
    ["fa-moon", "Is a lunar habitat at 34% oxygen riskier than the ISS?"],
    ["fa-circle-question", "Why are flames spherical in microgravity?"],
    ["fa-earth-africa", "How does space fire research help firefighters on Earth?"],
  ];

  FD.pages.assistant = {
    title: "AI Assistant",
    subtitle: "Ask in plain language — answers are grounded in the SAFFIRE data, the live monitoring state and NASA publications, with sources.",
    async render(view) {
      FD.publications().then((p) => (bm = bm || buildBM25(p)));
      view.innerHTML = `
      <div class="chat-layout">
        <section class="card chat" style="--i:0">
          <div class="chat-head"><div class="avatar ai"><img src="assets/img/logo.png" alt=""></div><div><b>FLAME DNA Copilot</b><div class="muted" style="font-size:12px"><span class="dot" style="display:inline-block;width:7px;height:7px;margin-right:5px;animation:none"></span>online · grounded answers</div></div>
            <span class="engine-badge" id="engine" style="margin-left:auto">checking engine…</span>
            <button class="btn sm ghost" id="clearChat" title="New conversation"><i class="fa-solid fa-pen-to-square"></i></button></div>
          <div class="chat-log" id="log"></div>
          <div class="chat-input">
            <div class="suggest" id="followups"></div>
            <form class="composer" id="composer"><textarea id="ask" rows="1" placeholder="Ask about flames, SAFFIRE samples, habitat safety… (Enter to send)"></textarea><button class="send" id="sendBtn" aria-label="Send"><i class="fa-solid fa-paper-plane"></i></button></form>
          </div>
        </section>
        <aside style="display:grid;gap:18px;align-content:start">
          <section class="card" style="--i:1"><div class="card-head"><div><h3>Live context</h3><div class="sub">What the assistant currently sees</div></div></div><div id="ctx"></div></section>
          <section class="card" style="--i:2"><div class="card-head"><div><h3>How it thinks</h3></div></div>
            <div class="actions-list" style="font-size:12.5px"><div>Detects the intent (data, ranking, comparison, live status, physics, papers)</div><div>Computes answers from the 13 SAFFIRE files & the monitoring engine</div><div>Retrieves NASA publications (BM25) and quotes them</div><div>Optional LLM rewrites from that context only — no invented numbers</div></div></section>
        </aside>
      </div>`;
      const log = FD.$("#log"), ask = FD.$("#ask");

      const ctx = () => {
        const M = FD.monitor; if (!FD.$("#ctx")) return;
        const lv = ["Nominal", "Watch", "Warning", "Fire alarm"][M.level || 0];
        FD.$("#ctx").innerHTML = `<div class="ev ${M.level >= 2 ? "met" : ""} ${M.level === 3 ? "crit" : ""}"><i class="fa-solid fa-tower-broadcast"></i><div><b>Monitoring: ${lv}</b><div class="muted" style="font-size:11.5px">${M.scenario} · ${M.habitat}</div></div></div>
          <div class="ev" style="margin-top:8px"><i class="fa-solid fa-database"></i><div><b>13 SAFFIRE files</b><div class="muted" style="font-size:11.5px">metrics + time series</div></div></div>
          <div class="ev" style="margin-top:8px"><i class="fa-solid fa-book"></i><div><b>60 NASA publications</b><div class="muted" style="font-size:11.5px">BM25 retrieval</div></div></div>
          ${chat.lastSamples.length ? `<div class="ev" style="margin-top:8px"><i class="fa-solid fa-thumbtack"></i><div><b>In focus</b><div class="muted" style="font-size:11.5px">${chat.lastSamples.join(", ")}</div></div></div>` : ""}`;
      };
      const onTick = () => ctx();
      FD.on("monitor", onTick);

      const scrollDown = () => (log.scrollTop = log.scrollHeight);
      const welcome = () => {
        log.innerHTML = `<div class="welcome"><img src="assets/img/logo.png" alt=""><h3>How can I help keep crews safe?</h3><p>I reason over real NASA microgravity fire data. Pick a question or type your own — French or English.</p>
          <div class="welcome-grid">${STARTERS.map(([i, t]) => `<button data-q="${FD.esc(t)}"><i class="fa-solid ${i}"></i>${t}</button>`).join("")}</div></div>`;
        FD.$$(".welcome-grid button", log).forEach((b) => b.onclick = () => send(b.dataset.q));
      };
      const bubble = (m) => {
        const el = FD.h(`<div class="msg ${m.role === "user" ? "me" : ""}"><div class="avatar ${m.role === "user" ? "me" : "ai"}">${m.role === "user" ? '<i class="fa-solid fa-user-astronaut"></i>' : '<img src="assets/img/logo.png" alt="">'}</div><div style="min-width:0"><div class="bubble"></div>${m.role === "assistant" ? `<div class="msg-meta"><span>${m.engine || ""}</span><button title="Copy"><i class="fa-regular fa-copy"></i></button></div>` : ""}</div></div>`);
        const b = el.querySelector(".bubble");
        if (m.role === "user") b.textContent = m.text; else b.innerHTML = md(m.text) + (m.sources?.length ? `<div class="sources">${m.sources.map((s) => `<a href="${s.u}" ${s.u.startsWith("#") ? "" : 'target="_blank" rel="noopener"'} title="${FD.esc(s.t)}"><i class="fa-solid ${s.u.startsWith("#") ? "fa-arrow-right" : "fa-book-open"}"></i> ${FD.esc(s.t)}</a>`).join("")}</div>` : "");
        const cp = el.querySelector(".msg-meta button");
        if (cp) cp.onclick = () => { navigator.clipboard?.writeText(m.text); FD.toast("Copied", "", "ok", 1500); };
        return el;
      };
      const renderAll = () => { if (!chat.msgs.length) return welcome(); log.innerHTML = ""; chat.msgs.forEach((m) => log.appendChild(bubble(m))); scrollDown(); };
      const followups = (intent) => {
        const f = { rank: ["Compare the top two", "Why is the flow direction important?"], compare: ["Which one is more dangerous for a habitat?", "Show the live cabin status"], sample: ["Compare it with SAFFIRE-I S2", "What does the heat-flux rise mean?"], monitor: ["What should the crew do?", "How does the alert logic avoid false alarms?"], kb: ["Which SAFFIRE sample illustrates this?", "What are the benefits on Earth?"], pubs: ["Summarize the first paper", "Which sample had the hottest surface?"] }[intent] || ["Which sample burned the longest?", "Why are flames spherical in microgravity?"];
        FD.$("#followups").innerHTML = f.map((t) => `<span class="chip" data-q="${FD.esc(t)}"><i class="fa-solid fa-reply"></i> ${t}</span>`).join("");
        FD.$$("#followups .chip").forEach((c) => c.onclick = () => send(c.dataset.q));
      };

      async function send(q) {
        q = (q || "").trim(); if (!q) return;
        if (!chat.msgs.length) log.innerHTML = "";
        if (/compare (the )?top two|compare them|compare it/i.test(q) && chat.lastSamples.length) q = `Compare ${chat.lastSamples.slice(0, 2).join(" and ")}${/it with (.*)/i.exec(q) ? " and " + /it with (.*)/i.exec(q)[1] : ""}`;
        chat.msgs.push({ role: "user", text: q });
        log.appendChild(bubble(chat.msgs[chat.msgs.length - 1]));
        ask.value = ""; ask.style.height = "auto";
        const typing = FD.h(`<div class="msg"><div class="avatar ai"><img src="assets/img/logo.png" alt=""></div><div class="bubble"><span class="typing"><span></span><span></span><span></span></span></div></div>`);
        log.appendChild(typing); scrollDown();
        FD.$("#sendBtn").disabled = true;
        if (!bm) bm = buildBM25(await FD.publications());
        const local = await localAnswer(q);
        let text = local.md, engine = "Local knowledge engine";
        if (await checkLLM() && local.intent !== "help") {
          try { text = await remoteAnswer(q, local); engine = "LLM · grounded on FLAME DNA context"; } catch (e) { engine = "Local engine (LLM unavailable)"; }
        } else await new Promise((r) => setTimeout(r, 450 + Math.random() * 400));
        typing.remove();
        const msg = { role: "assistant", text, sources: local.sources.slice(0, 4), engine };
        chat.msgs.push(msg);
        const el = bubble(msg); log.appendChild(el);
        // effet de frappe progressif
        const b = el.querySelector(".bubble"), full = b.innerHTML; b.style.opacity = 0;
        requestAnimationFrame(() => { b.style.transition = "opacity .3s"; b.style.opacity = 1; });
        b.innerHTML = full;
        scrollDown(); followups(local.intent); ctx();
        FD.$("#sendBtn").disabled = false; ask.focus();
      }

      FD.$("#composer").addEventListener("submit", (e) => { e.preventDefault(); send(ask.value); });
      ask.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(ask.value); } });
      ask.addEventListener("input", () => { ask.style.height = "auto"; ask.style.height = Math.min(140, ask.scrollHeight) + "px"; });
      FD.$("#clearChat").onclick = () => { chat.msgs = []; chat.lastSamples = []; welcome(); followups(); ctx(); };
      checkLLM().then((on) => (FD.$("#engine").textContent = on ? "LLM connected" : "Local engine · no API key needed"));
      renderAll(); followups(); ctx();
      const pre = new URLSearchParams(location.hash.split("?")[1] || "").get("q");
      if (pre) { history.replaceState(null, "", "#/assistant"); send(pre); }
      return () => FD.off("monitor", onTick);
    },
  };
})();

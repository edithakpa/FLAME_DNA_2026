/* FLAME DNA — mini-bibliothèque de graphiques SVG animés (sans dépendance)
   - lignes / aires qui se dessinent progressivement
   - barres qui poussent, anneaux qui se remplissent, radar, sparklines */
(function () {
  "use strict";
  const FD = window.FD;
  const NS = "http://www.w3.org/2000/svg";
  const C = (FD.charts = {});

  const svgEl = (tag, attrs = {}, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };

  /* graduations « propres » */
  function niceTicks(min, max, count = 5) {
    if (!isFinite(min) || !isFinite(max)) return [0, 1];
    if (min === max) { min -= 1; max += 1; }
    const span = max - min;
    const step0 = Math.pow(10, Math.floor(Math.log10(span / count)));
    const err = (count * step0) / span;
    const step = step0 * (err <= 0.15 ? 10 : err <= 0.35 ? 5 : err <= 0.75 ? 2 : 1);
    const t = [];
    for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) t.push(+v.toFixed(10));
    return t;
  }
  C.niceTicks = niceTicks;
  const shortNum = (v) => {
    const a = Math.abs(v);
    if (a >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (a >= 1e4) return (v / 1e3).toFixed(0) + "k";
    if (a >= 1e3) return (v / 1e3).toFixed(1) + "k";
    if (a > 0 && a < 0.01) return v.toExponential(0);
    return +v.toFixed(a < 1 ? 3 : a < 10 ? 2 : 1) + "";
  };
  C.shortNum = shortNum;

  function attachResize(container, render) {
    let w = container.clientWidth;
    if (container._ro) container._ro.disconnect();
    const ro = new ResizeObserver(() => {
      if (Math.abs(container.clientWidth - w) > 4) { w = container.clientWidth; render(false); }
    });
    ro.observe(container);
    container._ro = ro;
  }

  function setLen(path, dur = 1.6, delay = 0) {
    const len = path.getTotalLength ? path.getTotalLength() : 1000;
    path.style.setProperty("--len", Math.ceil(len) + 1);
    path.style.setProperty("--dur", dur + "s");
    path.style.setProperty("--delay", delay + "s");
    path.classList.add("draw");
  }

  /* ================= COURBES ================= */
  C.line = function (container, opts) {
    const o = Object.assign({ height: 260, animate: true, legend: true, area: false, yFmt: shortNum, xFmt: shortNum, pad: { l: 48, r: 14, t: 12, b: 30 } }, opts);
    container.classList.add("chart");
    const render = (animate) => {
      container.innerHTML = "";
      const W = Math.max(240, container.clientWidth), H = o.height, P = o.pad;
      const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, height: H }, container);
      const ser = o.series.filter((s) => s.y && s.y.length);
      let xs = [], ys = [];
      ser.forEach((s) => { s.x.forEach((v) => v != null && xs.push(v)); s.y.forEach((v) => v != null && isFinite(v) && ys.push(v)); });
      if (o.bands) o.bands.forEach((b) => ys.push(b.y0, b.y1));
      let xMin = o.xMin ?? Math.min(...xs), xMax = o.xMax ?? Math.max(...xs);
      let yMin = o.yMin ?? Math.min(...ys), yMax = o.yMax ?? Math.max(...ys);
      if (!isFinite(xMin)) { xMin = 0; xMax = 1; }
      if (!isFinite(yMin)) { yMin = 0; yMax = 1; }
      const padY = (yMax - yMin) * 0.08 || 1;
      if (o.yMin == null) yMin -= padY;
      if (o.yMax == null) yMax += padY;
      const yt = niceTicks(yMin, yMax, o.yTicks || 5);
      if (o.yMin == null) yMin = Math.min(yMin, yt[0]);
      if (o.yMax == null) yMax = Math.max(yMax, yt[yt.length - 1]);
      const sx = (v) => P.l + ((v - xMin) / (xMax - xMin || 1)) * (W - P.l - P.r);
      const sy = (v) => H - P.b - ((v - yMin) / (yMax - yMin || 1)) * (H - P.t - P.b);

      const g = svgEl("g", { class: "axis" }, svg);
      yt.forEach((v) => {
        if (v < yMin || v > yMax) return;
        svgEl("line", { x1: P.l, x2: W - P.r, y1: sy(v), y2: sy(v), class: "grid-line" }, g);
        svgEl("text", { x: P.l - 8, y: sy(v) + 4, "text-anchor": "end" }, g).textContent = o.yFmt(v);
      });
      niceTicks(xMin, xMax, Math.max(3, Math.floor(W / 110))).forEach((v) => {
        if (v < xMin || v > xMax) return;
        svgEl("text", { x: sx(v), y: H - 9, "text-anchor": "middle" }, g).textContent = o.xFmt(v);
      });
      if (o.yLabel) svgEl("text", { x: 4, y: 10, "text-anchor": "start", style: "font-size:10.5px" }, g).textContent = o.yLabel;
      if (o.xLabel) svgEl("text", { x: W - P.r, y: H - 9 - 14, "text-anchor": "end", style: "font-size:10.5px" }, g).textContent = o.xLabel;

      (o.bands || []).forEach((b) => {
        const y0 = sy(Math.min(b.y1, yMax)), y1 = sy(Math.max(b.y0, yMin));
        svgEl("rect", { x: P.l, y: y0, width: W - P.l - P.r, height: Math.max(0, y1 - y0), fill: b.color, opacity: b.opacity ?? 0.08 }, svg);
        if (b.label) svgEl("text", { x: W - P.r - 4, y: y0 + 12, "text-anchor": "end", fill: b.color, style: "font-size:10.5px;font-weight:600" }, svg).textContent = b.label;
      });
      (o.markers || []).forEach((m) => {
        if (m.x < xMin || m.x > xMax) return;
        svgEl("line", { x1: sx(m.x), x2: sx(m.x), y1: P.t, y2: H - P.b, stroke: m.color || "var(--muted)", "stroke-dasharray": "4 4", "stroke-width": 1.2, opacity: .8 }, svg);
        if (m.label) svgEl("text", { x: sx(m.x) + 4, y: P.t + 10, fill: m.color || "var(--muted)", style: "font-size:10.5px;font-weight:600" }, svg).textContent = m.label;
      });

      const defs = svgEl("defs", {}, svg);
      ser.forEach((s, i) => {
        const color = s.color || FD.palette[i % FD.palette.length];
        let d = "", pen = false, first = null, last = null;
        s.y.forEach((v, k) => {
          const xv = s.x[k];
          if (v == null || !isFinite(v) || xv == null) { pen = false; return; }
          const X = sx(xv).toFixed(1), Y = sy(Math.max(yMin, Math.min(yMax, v))).toFixed(1);
          d += (pen ? "L" : "M") + X + " " + Y;
          pen = true; if (!first) first = [X, Y]; last = [X, Y];
        });
        if (!d) return;
        const delay = animate && o.animate ? i * 0.18 : 0;
        if (o.area || s.area) {
          const gid = "g" + Math.random().toString(36).slice(2, 8);
          const lg = svgEl("linearGradient", { id: gid, x1: 0, x2: 0, y1: 0, y2: 1 }, defs);
          svgEl("stop", { offset: "0%", "stop-color": color, "stop-opacity": 0.32 }, lg);
          svgEl("stop", { offset: "100%", "stop-color": color, "stop-opacity": 0 }, lg);
          const a = svgEl("path", { d: `${d}L${last[0]} ${H - P.b}L${first[0]} ${H - P.b}Z`, fill: `url(#${gid})`, class: animate && o.animate ? "area" : "" }, svg);
          a.style.setProperty("--delay", delay + "s");
        }
        const p = svgEl("path", { d, fill: "none", stroke: color, "stroke-width": s.width || 2.2, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": s.dash || null }, svg);
        if (animate && o.animate && !s.dash) setLen(p, o.duration || 1.8, delay);
      });

      // infobulle croisée
      if (o.tooltip !== false && ser.length) {
        const tip = FD.h(`<div class="chart-tip"></div>`);
        container.appendChild(tip);
        const cross = svgEl("line", { y1: P.t, y2: H - P.b, stroke: "var(--muted)", "stroke-width": 1, opacity: 0 }, svg);
        const dots = ser.map((s, i) => svgEl("circle", { r: 4, fill: s.color || FD.palette[i % FD.palette.length], stroke: "var(--surface)", "stroke-width": 2, opacity: 0 }, svg));
        const ov = svgEl("rect", { x: P.l, y: P.t, width: W - P.l - P.r, height: H - P.t - P.b, fill: "transparent" }, svg);
        const nearest = (arr, v) => { let lo = 0, hi = arr.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; arr[m] < v ? (lo = m) : (hi = m); } return Math.abs(arr[lo] - v) < Math.abs(arr[hi] - v) ? lo : hi; };
        ov.addEventListener("mousemove", (ev) => {
          const r = svg.getBoundingClientRect();
          const px = ((ev.clientX - r.left) / r.width) * W;
          const xv = xMin + ((px - P.l) / (W - P.l - P.r)) * (xMax - xMin);
          let rows = "";
          ser.forEach((s, i) => {
            const k = nearest(s.x, xv), y = s.y[k];
            if (y == null) { dots[i].setAttribute("opacity", 0); return; }
            dots[i].setAttribute("cx", sx(s.x[k])); dots[i].setAttribute("cy", sy(Math.max(yMin, Math.min(yMax, y)))); dots[i].setAttribute("opacity", 1);
            rows += `<div class="row"><span><i class="sw" style="background:${s.color || FD.palette[i % FD.palette.length]}"></i> ${FD.esc(s.name || "")}</span><b>${FD.fmt(y, Math.abs(y) < 10 ? 3 : 1)}${s.unit ? " " + s.unit : ""}</b></div>`;
          });
          cross.setAttribute("x1", sx(xv)); cross.setAttribute("x2", sx(xv)); cross.setAttribute("opacity", 0.5);
          tip.innerHTML = `<div class="muted" style="margin-bottom:4px">${o.xName || "x"} = ${FD.fmt(xv, 1)}${o.xUnit || ""}</div>${rows}`;
          tip.style.opacity = 1;
          const tx = (sx(xv) / W) * r.width;
          tip.style.left = Math.min(r.width - tip.offsetWidth - 4, tx + 14) + "px";
          tip.style.top = "8px";
        });
        ov.addEventListener("mouseleave", () => { tip.style.opacity = 0; cross.setAttribute("opacity", 0); dots.forEach((d) => d.setAttribute("opacity", 0)); });
      }
      if (o.legend && ser.length > 1) {
        const lg = FD.h(`<div class="legend">${ser.map((s, i) => `<span><i style="background:${s.color || FD.palette[i % FD.palette.length]}"></i>${FD.esc(s.name)}</span>`).join("")}</div>`);
        container.appendChild(lg);
      }
    };
    render(true);
    attachResize(container, render);
    return { update: (series) => { o.series = series; render(false); } };
  };

  /* ================= BARRES ================= */
  C.bar = function (container, opts) {
    const o = Object.assign({ height: 240, yFmt: shortNum, pad: { l: 44, r: 10, t: 14, b: 44 }, legend: true, rotate: false }, opts);
    container.classList.add("chart");
    const render = (animate) => {
      container.innerHTML = "";
      const W = Math.max(240, container.clientWidth), H = o.height, P = o.pad;
      const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, height: H }, container);
      const vals = o.series.flatMap((s) => s.values.filter((v) => v != null));
      let yMin = Math.min(0, ...vals), yMax = Math.max(...vals, 0) * 1.08 || 1;
      const yt = niceTicks(yMin, yMax, 4); yMax = Math.max(yMax, yt[yt.length - 1]); yMin = Math.min(yMin, yt[0]);
      const sy = (v) => H - P.b - ((v - yMin) / (yMax - yMin || 1)) * (H - P.t - P.b);
      const g = svgEl("g", { class: "axis" }, svg);
      yt.forEach((v) => { svgEl("line", { x1: P.l, x2: W - P.r, y1: sy(v), y2: sy(v), class: "grid-line" }, g); svgEl("text", { x: P.l - 8, y: sy(v) + 4, "text-anchor": "end" }, g).textContent = o.yFmt(v); });
      const n = o.labels.length, groupW = (W - P.l - P.r) / n, ns = o.series.length;
      const bw = Math.min(34, (groupW * 0.72) / ns);
      const tip = FD.h(`<div class="chart-tip"></div>`); container.appendChild(tip);
      o.labels.forEach((lab, i) => {
        const cx = P.l + groupW * (i + 0.5);
        const t = svgEl("text", { x: cx, y: H - P.b + 16, "text-anchor": o.rotate ? "end" : "middle", transform: o.rotate ? `rotate(-30 ${cx} ${H - P.b + 16})` : null }, g);
        t.textContent = lab;
        o.series.forEach((s, j) => {
          const v = s.values[i]; if (v == null) return;
          const x = cx - (ns * bw) / 2 + j * bw + 1;
          const y0 = sy(Math.max(0, v)), y1 = sy(Math.min(0, v));
          const col = (s.colors && s.colors[i]) || s.color || FD.palette[j % FD.palette.length];
          const r = svgEl("rect", { x, y: y0, width: bw - 2, height: Math.max(1, y1 - y0), rx: Math.min(6, bw / 3), fill: col, class: animate ? "bar" : "" }, svg);
          r.style.setProperty("--delay", (i * 0.06 + j * 0.04) + "s");
          r.addEventListener("mousemove", (ev) => {
            const rc = svg.getBoundingClientRect();
            tip.innerHTML = `<div class="muted">${FD.esc(lab)}</div><div class="row"><span><i class="sw" style="background:${col}"></i> ${FD.esc(s.name || "")}</span><b>${FD.fmt(v, Math.abs(v) < 10 ? 3 : 1)} ${o.unit || ""}</b></div>`;
            tip.style.opacity = 1; tip.style.left = Math.min(rc.width - 170, ev.clientX - rc.left + 12) + "px"; tip.style.top = Math.max(0, ev.clientY - rc.top - 50) + "px";
          });
          r.addEventListener("mouseleave", () => (tip.style.opacity = 0));
        });
      });
      if (o.legend && o.series.length > 1) container.appendChild(FD.h(`<div class="legend">${o.series.map((s, i) => `<span><i style="background:${s.color || FD.palette[i]}"></i>${FD.esc(s.name)}</span>`).join("")}</div>`));
    };
    render(true);
    attachResize(container, render);
  };

  /* ================= BARRES HORIZONTALES ================= */
  C.hbar = function (container, opts) {
    const o = Object.assign({ unit: "", dec: 1 }, opts);
    const max = Math.max(...o.items.map((i) => Math.abs(i.value || 0))) || 1;
    container.innerHTML = o.items.map((it, i) => `
      <div style="margin:9px 0">
        <div style="display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:4px"><span>${FD.esc(it.label)}</span><b class="mono" data-count="${it.value ?? ""}" data-dec="${o.dec}" data-suffix=" ${o.unit}">0</b></div>
        <div class="relbar" style="height:8px"><span style="width:${(100 * Math.abs(it.value || 0)) / max}%;background:${it.color || "linear-gradient(90deg,var(--amber),var(--accent))"};animation-delay:${i * 70}ms"></span></div>
      </div>`).join("");
    FD.animateCounts(container);
  };

  /* ================= ANNEAU / JAUGE ================= */
  C.ring = function (container, opts) {
    const o = Object.assign({ size: 150, thickness: 13, value: 0, color: "var(--accent)", label: "", display: null, track: "var(--surface-3)", gradient: null }, opts);
    const r = (o.size - o.thickness) / 2, c = 2 * Math.PI * r;
    const v = Math.max(0, Math.min(1, o.value));
    const id = "rg" + Math.random().toString(36).slice(2, 7);
    container.classList.add("ring-wrap");
    container.innerHTML = `
      <svg width="${o.size}" height="${o.size}" viewBox="0 0 ${o.size} ${o.size}" style="transform:rotate(-90deg)">
        ${o.gradient ? `<defs><linearGradient id="${id}" x1="0" x2="1"><stop offset="0" stop-color="${o.gradient[0]}"/><stop offset="1" stop-color="${o.gradient[1]}"/></linearGradient></defs>` : ""}
        <circle cx="${o.size / 2}" cy="${o.size / 2}" r="${r}" fill="none" stroke="${o.track}" stroke-width="${o.thickness}"/>
        <circle class="ring-arc" cx="${o.size / 2}" cy="${o.size / 2}" r="${r}" fill="none" stroke="${o.gradient ? `url(#${id})` : o.color}" stroke-width="${o.thickness}" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${c}" style="transition:stroke-dashoffset 1.6s var(--ease), stroke .4s"/>
      </svg>
      <div class="ring-center"><div><div class="v" ${o.display == null ? `data-count="${Math.round(v * 100)}" data-suffix="%"` : ""}>${o.display ?? "0%"}</div><div class="l">${o.label}</div></div></div>`;
    const arc = container.querySelector(".ring-arc");
    requestAnimationFrame(() => requestAnimationFrame(() => (arc.style.strokeDashoffset = c * (1 - v))));
    FD.animateCounts(container);
    return {
      set(val, color, display) {
        arc.style.strokeDashoffset = c * (1 - Math.max(0, Math.min(1, val)));
        if (color) arc.setAttribute("stroke", color);
        const vEl = container.querySelector(".v");
        if (display != null) vEl.innerHTML = display; else vEl.textContent = Math.round(val * 100) + "%";
      },
    };
  };

  /* ================= DONUT MULTI-SEGMENTS ================= */
  C.donut = function (container, opts) {
    const o = Object.assign({ size: 170, thickness: 22 }, opts);
    const total = o.items.reduce((s, i) => s + i.value, 0) || 1;
    const r = (o.size - o.thickness) / 2, c = 2 * Math.PI * r;
    let acc = 0;
    const arcs = o.items.map((it, i) => {
      const len = (it.value / total) * c, off = acc; acc += len;
      return `<circle cx="${o.size / 2}" cy="${o.size / 2}" r="${r}" fill="none" stroke="${it.color || FD.palette[i]}" stroke-width="${o.thickness}" stroke-dasharray="0 ${c}" data-len="${Math.max(0, len - 3)}" data-c="${c}" stroke-dashoffset="${-off}" style="transition:stroke-dasharray 1.2s var(--ease) ${i * 0.15}s"><title>${FD.esc(it.label)}: ${it.value}</title></circle>`;
    }).join("");
    container.innerHTML = `<div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap;justify-content:center">
      <div class="ring-wrap"><svg width="${o.size}" height="${o.size}" style="transform:rotate(-90deg)"><circle cx="${o.size / 2}" cy="${o.size / 2}" r="${r}" fill="none" stroke="var(--surface-3)" stroke-width="${o.thickness}"/>${arcs}</svg>
      <div class="ring-center"><div><div class="v" data-count="${o.center ?? total}">0</div><div class="l">${o.centerLabel || ""}</div></div></div></div>
      <div class="legend" style="flex-direction:column;gap:8px">${o.items.map((it, i) => `<span><i style="background:${it.color || FD.palette[i]}"></i>${FD.esc(it.label)} <b class="mono" style="color:var(--text)">${it.value}</b></span>`).join("")}</div></div>`;
    requestAnimationFrame(() => requestAnimationFrame(() => container.querySelectorAll("circle[data-len]").forEach((e) => e.setAttribute("stroke-dasharray", `${e.dataset.len} ${e.dataset.c}`))));
    FD.animateCounts(container);
  };

  /* ================= SPARKLINE ================= */
  C.spark = function (container, values, color = "var(--accent)", opts = {}) {
    const W = 200, H = opts.height || 38;
    const v = values.filter((x) => x != null && isFinite(x));
    if (!v.length) { container.innerHTML = ""; return; }
    const mn = Math.min(...v), mx = Math.max(...v);
    const pts = values.map((y, i) => (y == null ? null : [(i / (values.length - 1 || 1)) * W, H - 3 - ((y - mn) / (mx - mn || 1)) * (H - 6)]));
    let d = "", pen = false;
    pts.forEach((p) => { if (!p) { pen = false; return; } d += (pen ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); pen = true; });
    const id = "sp" + Math.random().toString(36).slice(2, 7);
    container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="width:100%;height:${H}px;display:block">
      <defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".3"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <path d="${d}L${W} ${H}L0 ${H}Z" fill="url(#${id})" class="${opts.animate === false ? "" : "area"}" style="opacity:${opts.animate === false ? 1 : 0}"/>
      <path d="${d}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;
    container.classList.add("chart");
    if (opts.animate !== false) setLen(container.querySelectorAll("path")[1], 1.4, opts.delay || 0);
  };

  /* ================= RADAR ================= */
  C.radar = function (container, opts) {
    const o = Object.assign({ size: 320 }, opts);
    const S = o.size, cx = S / 2, cy = S / 2, R = S / 2 - 48, n = o.axes.length;
    const ang = (i) => -Math.PI / 2 + (i / n) * Math.PI * 2;
    let html = `<svg viewBox="0 0 ${S} ${S}" style="width:100%;max-width:${S + 60}px;display:block;margin:auto;overflow:visible">`;
    [0.25, 0.5, 0.75, 1].forEach((f) => {
      html += `<polygon points="${o.axes.map((_, i) => `${cx + Math.cos(ang(i)) * R * f},${cy + Math.sin(ang(i)) * R * f}`).join(" ")}" fill="none" stroke="var(--grid)" />`;
    });
    o.axes.forEach((a, i) => {
      const x = cx + Math.cos(ang(i)) * R, y = cy + Math.sin(ang(i)) * R;
      const lx = cx + Math.cos(ang(i)) * (R + 22), ly = cy + Math.sin(ang(i)) * (R + 16);
      html += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="var(--grid)"/><text x="${lx}" y="${ly}" text-anchor="${Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end"}" fill="var(--muted)" style="font-size:10.5px">${FD.esc(a)}</text>`;
    });
    o.series.forEach((s, k) => {
      const col = s.color || FD.palette[k];
      const pts = s.values.map((v, i) => `${cx + Math.cos(ang(i)) * R * (v ?? 0)},${cy + Math.sin(ang(i)) * R * (v ?? 0)}`).join(" ");
      html += `<g style="transform-origin:${cx}px ${cy}px;animation:pop .9s var(--ease) ${k * 0.2}s both"><polygon points="${pts}" fill="${col}" fill-opacity=".16" stroke="${col}" stroke-width="2" stroke-linejoin="round"/></g>`;
    });
    html += `</svg>`;
    container.innerHTML = html + `<div class="legend" style="justify-content:center">${o.series.map((s, i) => `<span><i style="background:${s.color || FD.palette[i]}"></i>${FD.esc(s.name)}</span>`).join("")}</div>`;
  };
})();

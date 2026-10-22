/* UW·IQA demo front end: vanilla JS, hash routing, monochrome SVG charts. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (v, d = 3) => (v == null || Number.isNaN(+v) ? "—" : Number(v).toFixed(d));
const VIEW = $("#view");

async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const e = new Error((await r.text()) || r.statusText);
    e.status = r.status;
    throw e;
  }
  return r.json();
}

let STATUS = { samples: [], benchmark: [], names: {}, detector: false, funiegan: false };
const UPLOADS = [];
const S = { page: "overview", img: null, lab: "1", v: "raw", conf: 0.25, gt: false,
            p: { gamma: 0.6, angle: 15, lo: 50, hi: 150, k: 4 } };
let RENDER_ID = 0;

/* ------------------------------------------------------------------ routing */
function readHash() {
  const [page, q] = location.hash.replace(/^#\/?/, "").split("?");
  const p = new URLSearchParams(q || "");
  S.page = ["overview", "enhance", "quality", "lab", "detect"].includes(page) ? page : "overview";
  S.img = p.get("img") || S.img || (STATUS.samples[0] && STATUS.samples[0].id) || (UPLOADS[0] && UPLOADS[0].id) || null;
  if (p.get("lab")) S.lab = p.get("lab");
  if (p.get("v")) S.v = p.get("v");
}
function href(patch = {}) {
  const st = { ...S, ...patch };
  const q = new URLSearchParams();
  if (st.img) q.set("img", st.img);
  if (st.page === "lab") { q.set("lab", st.lab); q.set("v", st.v); }
  return `#/${st.page}?${q}`;
}
function go(patch) { location.hash = href(patch); }

/* ------------------------------------------------------------------ helpers */
const kindTag = (k) => (k === "enhancement helps" ? ["helps", "tag-helps"] : k === "all enhancers hurt" ? ["hurts", "tag-hurts"] : ["noise", "tag-flat"]);
function delta(v, tau = 0.05) {
  if (v == null || Number.isNaN(+v)) return '<span class="flat">—</span>';
  const s = (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(3);
  if (v > tau) return `<span class="up">▲ ${s}</span>`;
  if (v < -tau) return `<span class="down">▼ ${s}</span>`;
  return `<span class="flat">· ${s}</span>`;
}
const imgURL = (v, w = 1100) => `/api/img/${encodeURIComponent(S.img)}/${v}.jpg?w=${w}`;
function head(num, title, text) {
  return `<div class="page-head"><div class="eyebrow">${num}</div><h1>${title}</h1><p>${text}</p></div>`;
}
function loading(msg) { return `<div class="loading"><span class="spin"></span>${esc(msg)}</div>`; }
function card({ src, full, title, right = "", fn = "", raw = false, overlay = "", caption = "" }) {
  return `<div class="card${raw ? " raw" : ""}">
    <div class="media" data-full="${esc(full || src)}" data-caption="${esc(caption || title)}">
      <img src="${esc(src)}" alt="${esc(title)}" loading="eager">${overlay}</div>
    <div class="cap"><span class="t">${esc(title)}</span><span class="r">${right}</span></div>
    ${fn ? `<div class="fn">${esc(fn)}</div>` : ""}</div>`;
}
function foot() {
  return `<footer class="foot"><span>FCV Lab · CSE 3176 · Manipal Institute of Technology · 2026</span>
    <span>Akshant Beuria · Javvaji Aditya Banasri · Mansi Sinha</span></footer>`;
}
async function settle(id) {
  const imgs = $$("img", VIEW);
  await Promise.all(imgs.map((i) => (i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))));
  if (id === RENDER_ID) document.body.dataset.ready = "1";
}

/* ------------------------------------------------------------------ charts (SVG) */
function lineChart(series, { w = 340, h = 120, ymax, clip = false } = {}) {
  // clip: scale to the interior bins so a spike of pure black / saturated pixels does not flatten the rest
  const n = series[0].data.length;
  const top = ymax || Math.max(...series.flatMap((s) => (clip ? s.data.slice(1, -1) : s.data))) || 1;
  const pad = 4;
  const lines = series.map((s) => {
    const pts = s.data.map((y, i) => `${(pad + (i / (n - 1)) * (w - 2 * pad)).toFixed(1)},${(h - pad - (Math.min(y, top) / top) * (h - 2 * pad)).toFixed(1)}`).join(" ");
    return `<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="${s.width || 1.6}" ${s.dash ? `stroke-dasharray="${s.dash}"` : ""} stroke-linejoin="round"/>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" role="img"><line class="axis" x1="0" y1="${h - pad}" x2="${w}" y2="${h - pad}"/>${lines}</svg>`;
}
function barChart(rows, { w = 520, h = 210, d = 3 } = {}) {
  const max = Math.max(...rows.map((r) => r.value), 1e-9);
  const n = rows.length, gap = 14, left = 8, bottom = 26, top = 18;
  const bw = (w - left * 2 - gap * (n - 1)) / n;
  const bars = rows.map((r, i) => {
    const x = left + i * (bw + gap);
    const bh = Math.max(1, (r.value / max) * (h - bottom - top));
    const y = h - bottom - bh;
    const fill = r.raw ? "#0a0a0a" : "#ffffff";
    return `<rect x="${x}" y="${y}" width="${bw}" height="${bh}" fill="${fill}" stroke="#0a0a0a" stroke-width="1.2"/>
      <text x="${x + bw / 2}" y="${y - 5}" text-anchor="middle" style="fill:#0a0a0a">${r.value.toFixed(d)}</text>
      <text x="${x + bw / 2}" y="${h - 9}" text-anchor="middle">${esc(r.name)}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" role="img"><line class="axis" x1="0" y1="${h - bottom}" x2="${w}" y2="${h - bottom}"/>${bars}</svg>`;
}

/* ------------------------------------------------------------------ picker + chrome */
function renderPicker() {
  const items = [...UPLOADS.map((u) => ({ ...u, upload: true })), ...STATUS.samples];
  $("#pickcount").textContent = `${items.length} available`;
  $("#thumbs").innerHTML = items.map((s) => {
    const [t, cls] = s.upload ? ["upload", "tag-flat"] : kindTag(s.kind);
    const sub = s.upload ? "no ground truth" : `${s.n_objects} objects · best ${esc(s.best)}`;
    return `<button class="thumb${s.id === S.img ? " active" : ""}" data-id="${esc(s.id)}" title="${esc(s.id)}">
      <div class="ph"><img src="/api/thumb/${encodeURIComponent(s.id)}.jpg" alt=""><span class="tag ${cls}">${t}</span></div>
      <div class="meta"><div class="id">${esc(s.upload ? "uploaded" : s.id)}</div><div class="sub">${sub}</div></div></button>`;
  }).join("") || `<div class="muted small">No sample images found. Upload one above, or add the demo assets.</div>`;
}
function renderChrome() {
  $$("#nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.page === S.page);
    a.href = href({ page: a.dataset.page });
  });
  $$(".thumb").forEach((b) => b.classList.toggle("active", b.dataset.id === S.img));
  $("#sys").innerHTML = `<span class="${STATUS.detector ? "on" : "off"}">YOLO11-s</span><span class="${STATUS.funiegan ? "on" : "off"}">FUnIE-GAN</span>`;
}

/* ------------------------------------------------------------------ pages */
async function pageOverview() {
  const s = STATUS.samples.find((x) => x.id === S.img);
  VIEW.innerHTML = `
    <section class="hero">
      <div>
        <div class="eyebrow">Mini project · Foundations of Computer Vision Lab · CSE 3176</div>
        <h1>Seeing better is not detecting better.</h1>
        <p class="lead">Underwater images are enhanced before analysis, and the enhancement is judged by quality metrics such
        as UIQM and UCIQE. Our study found that a better-<em>looking</em> image is often a <em>worse</em> image for an
        object detector. This application lets you inspect that effect one image at a time.</p>
        <div class="team">By <b>Akshant Beuria</b>, <b>Javvaji Aditya Banasri</b> and <b>Mansi Sinha</b> · School of Computer Engineering, MIT Manipal</div>
      </div>
      ${S.img ? `<figure class="hero-img" style="margin:0"><img src="${imgURL("raw", 900)}" alt="selected image">
        <figcaption><span>${esc(s ? s.id : "uploaded image")}</span><span>${s ? esc(s.kind) : "raw"}</span></figcaption></figure>`
        : `<div class="empty">Select or upload an image to begin.</div>`}
    </section>
    <div class="stats">
      <div class="stat"><div class="v">0.62</div><div class="l">Best agreement with human scores (URanker, Spearman)</div></div>
      <div class="stat"><div class="v">0.33</div><div class="l">UIQM and UCIQE agreement with human scores</div></div>
      <div class="stat"><div class="v">−0.022</div><div class="l">Mean detection AP change of the best enhancer (CLAHE)</div></div>
      <div class="stat"><div class="v">+0.025</div><div class="l">mAP an oracle could gain by choosing per image, about 10× label noise</div></div>
    </div>
    <div class="steps">
      <a class="step" href="${href({ page: "enhance" })}"><div class="n">01</div><h3>Enhancement</h3><p>Five enhancers applied exactly as in the study, with colour histograms.</p></a>
      <a class="step" href="${href({ page: "quality" })}"><div class="n">02</div><h3>Quality scores</h3><p>UIQM and UCIQE of every version next to the true change in detection.</p></a>
      <a class="step" href="${href({ page: "lab" })}"><div class="n">03</div><h3>Lab 1–5</h3><p>Histograms, filtering, edges, thresholding, k-means, SIFT, HOG and LBP.</p></a>
      <a class="step" href="${href({ page: "detect" })}"><div class="n">04</div><h3>Detection</h3><p>The trained YOLO11-s on every version, with per-image AP and ΔAP.</p></a>
    </div>${foot()}`;
}

async function pageEnhance(id) {
  VIEW.innerHTML = head("01 — Enhancement", "Six versions of one image",
    "The raw image and five enhanced versions, produced in memory at the study's working resolution of 1280 px. CLAHE, gray-world, UDCP and fusion are our OpenCV implementations; FUnIE-GAN uses the official weights.") + loading("Enhancing…");
  const d = await api(`/api/enhance/${encodeURIComponent(S.img)}`);
  if (id !== RENDER_ID) return;
  const cards = d.variants.map((v) => card({ src: imgURL(v.key, 900), full: imgURL(v.key, 1280), title: v.name,
    right: v.key === "raw" ? `${d.size[0]} × ${d.size[1]}` : "", raw: v.key === "raw" })).join("");
  const hists = d.variants.map((v) => `<div class="chart"><h4>${esc(v.name)}</h4>${lineChart([
      { data: d.hist[v.key][0], color: "#0a0a0a" }, { data: d.hist[v.key][1], color: "#8a8a8a" },
      { data: d.hist[v.key][2], color: "#b5b5b5", dash: "4 3" }], { clip: true })}</div>`).join("");
  VIEW.innerHTML = head("01 — Enhancement", "Six versions of one image",
    "The raw image and five enhanced versions, produced in memory at the study's working resolution of 1280 px. CLAHE, gray-world, UDCP and fusion are our OpenCV implementations; FUnIE-GAN uses the official weights.") +
    `<div class="grid g3">${cards}</div>
    <h2 class="sec">Colour histograms</h2>
    <p class="sec-sub">Pixel distribution of each channel, computed with <span class="mono">cv2.calcHist</span> (Lab 2). Raw underwater images have a weak red channel; each enhancer redistributes the channels differently. The y-axis ignores the first and last bin (pure black and saturated pixels).</p>
    <div class="keyline"><span><i></i>red</span><span><i class="g"></i>green</span><span><i class="b"></i>blue</span></div>
    <div class="charts grid g3">${hists}</div>${foot()}`;
}

async function pageQuality(id) {
  const intro = "UIQM and UCIQE are computed live with the study's own implementations at 512 px. Higher means better quality to the metric. Compare them with what actually happens to the detector.";
  VIEW.innerHTML = head("02 — Quality scores", "What the metrics say", intro) + loading("Scoring…");
  const d = await api(`/api/quality/${encodeURIComponent(S.img)}`);
  if (id !== RENDER_ID) return;
  const rows = d.rows.map((r) => `<tr${r.key === "raw" ? ' class="hl"' : ""}><td class="name">${esc(r.name)}</td>
      <td class="num">${fmt(r.uiqm)}</td><td class="num">${fmt(r.uicm)}</td><td class="num">${fmt(r.uism)}</td>
      <td class="num">${fmt(r.uiconm)}</td><td class="num">${fmt(r.uciqe)}</td>
      ${d.has_study ? `<td class="num">${r.key === "raw" ? '<span class="flat">baseline</span>' : delta(r.study_dap, d.tau)}</td>` : ""}</tr>`).join("");
  const bars = (key) => barChart(d.rows.map((r) => ({ name: r.name, value: r[key], raw: r.key === "raw" })), { d: key === "uiqm" ? 2 : 3 });
  const bench = STATUS.benchmark.map((b) => `<tr${b.metric === "uiqm" || b.metric === "uciqe" ? ' class="hl"' : ""}>
      <td class="name mono">${esc(b.metric)}</td>
      <td class="num"><div class="bar-cell">${fmt(b.srcc)}<span class="mini"><i style="width:${Math.max(0, b.srcc) * 100}%"></i></span></div></td>
      <td class="num">[${fmt(b.srcc_lo)}, ${fmt(b.srcc_hi)}]</td><td class="num">${fmt(b.intra_scene_srcc)}</td></tr>`).join("");
  VIEW.innerHTML = head("02 — Quality scores", "What the metrics say", intro) + `
    <div class="tbl-wrap"><table><thead><tr><th>Version</th><th class="num">UIQM</th><th class="num">UICM · colour</th>
      <th class="num">UISM · sharpness</th><th class="num">UIConM · contrast</th><th class="num">UCIQE</th>
      ${d.has_study ? '<th class="num">ΔAP detection</th>' : ""}</tr></thead><tbody>${rows}</tbody></table></div>
    ${d.has_study ? `<div class="callout"><span class="k">Read this</span><p>An enhancer can raise UIQM or UCIQE while lowering detection accuracy on the same image.
      ΔAP is the true change in per-image AP measured in the study (▲ helps, ▼ hurts by more than the noise threshold ${d.tau}).
      Across 7,000 images, the quality gain of an enhancement had no positive correlation with its detection gain for any metric.</p></div>`
      : `<p class="note">Uploaded images have no ground truth, so the true detection change is shown only for the sample images.</p>`}
    <div class="charts grid g2"><div class="chart"><h4>UIQM</h4>${bars("uiqm")}</div><div class="chart"><h4>UCIQE</h4>${bars("uciqe")}</div></div>
    ${bench ? `<h2 class="sec">How far can each metric be trusted?</h2>
    <p class="sec-sub">Study result on UID2021 (960 images, 77 observers): Spearman correlation with human opinion scores, its 95% bootstrap interval, and the mean correlation within each scene.</p>
    <div class="tbl-wrap"><table><thead><tr><th>Metric</th><th class="num">SRCC vs. humans</th><th class="num">95% CI</th><th class="num">Intra-scene</th></tr></thead><tbody>${bench}</tbody></table></div>` : ""}${foot()}`;
}

const LABS = [
  ["1", "OpenCV basics", "Reading, colour conversion, resizing, rotation and pixel access."],
  ["2", "Enhancement", "Point transformations, contrast stretching and histogram equalisation."],
  ["3", "Filtering", "Smoothing filters, gradients and edge detection."],
  ["4", "Segmentation", "Global and adaptive thresholding and k-means colour clustering."],
  ["5", "Features", "Keypoints, corners, gradient histograms and texture descriptors."],
  ["S", "Raw vs enhanced", "Low-level statistics of every version side by side."],
];
let labTimer = null;
function labControls(variants) {
  const seg = variants.map((v) => `<button data-v="${v.key}" class="${v.key === S.v ? "on" : ""}">${esc(v.name)}</button>`).join("");
  const rng = (key, label, min, max, step) => `<div class="ctl"><label>${label}</label><div class="range">
      <input type="range" data-p="${key}" min="${min}" max="${max}" step="${step}" value="${S.p[key]}"><output>${S.p[key]}</output></div></div>`;
  const extra = { "1": rng("angle", "Rotation (°)", -45, 45, 1), "2": rng("gamma", "Gamma γ", 0.2, 3, 0.1),
    "3": rng("lo", "Canny low", 0, 300, 5) + rng("hi", "Canny high", 0, 300, 5), "4": rng("k", "Clusters K", 2, 8, 1) }[S.lab] || "";
  return `<div class="controls">${S.lab !== "S" ? `<div class="ctl"><label>Image version</label><div class="seg" id="vseg">${seg}</div></div>` : ""}${extra}</div>`;
}
async function pageLab(id) {
  const intro = "Operations from Labs 1–5 of the FCV Lab manual, applied live to the raw image or any enhanced version (on a 640 px copy). Click an image to enlarge it.";
  const tabs = `<div class="tabs" id="labtabs">${LABS.map(([k, n]) => `<button data-lab="${k}" class="${k === S.lab ? "on" : ""}"><span>${k === "S" ? "Σ" : "L" + k}</span>${n}</button>`).join("")}</div>`;
  VIEW.innerHTML = head("03 — Lab 1–5 operations", "The lab, on underwater images", intro) + tabs + loading("Processing…");
  const enh = await api(`/api/enhance/${encodeURIComponent(S.img)}`);
  if (id !== RENDER_ID) return;
  if (!enh.variants.some((v) => v.key === S.v)) S.v = "raw";
  const meta = LABS.find((l) => l[0] === S.lab);
  VIEW.innerHTML = head("03 — Lab 1–5 operations", "The lab, on underwater images", intro) + tabs +
    `<p class="sec-sub" style="margin-top:18px">${esc(meta[2])}</p>${labControls(enh.variants)}<div id="labout">${loading("Processing…")}</div>${foot()}`;
  $$("#labtabs button").forEach((b) => b.onclick = () => go({ lab: b.dataset.lab }));
  $$("#vseg button").forEach((b) => b.onclick = () => go({ v: b.dataset.v }));
  $$(".controls input[type=range]").forEach((inp) => inp.oninput = () => {
    S.p[inp.dataset.p] = +inp.value;
    inp.nextElementSibling.textContent = inp.value;
    clearTimeout(labTimer);
    labTimer = setTimeout(() => labResults(RENDER_ID), 280);
  });
  await labResults(id);
}
async function labResults(id) {
  const out = $("#labout");
  if (!out) return;
  if (S.lab === "S") {
    const d = await api(`/api/features/${encodeURIComponent(S.img)}`);
    if (id !== RENDER_ID) return;
    const cols = ["Michelson contrast", "Canny edge density", "SIFT keypoints", "FAST corners", "Otsu threshold", "Otsu foreground %", "LBP entropy"];
    const dig = { "SIFT keypoints": 0, "FAST corners": 0, "Otsu threshold": 0, "Otsu foreground %": 1 };
    out.innerHTML = `<div class="tbl-wrap"><table><thead><tr><th>Version</th>${cols.map((c) => `<th class="num">${c}</th>`).join("")}</tr></thead>
      <tbody>${d.rows.map((r) => `<tr${r.key === "raw" ? ' class="hl"' : ""}><td class="name">${esc(r.name)}</td>${cols.map((c) => `<td class="num">${fmt(r[c], dig[c] ?? 3)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      <div class="callout"><span class="k">Takeaway</span><p>Enhancement usually raises contrast, edge density and keypoint counts. The Detection page shows that this does not translate into better detection.</p></div>`;
    return settle(id);
  }
  out.innerHTML = loading("Processing…");
  const q = new URLSearchParams({ variant: S.v, ...S.p });
  const d = await api(`/api/lab/${encodeURIComponent(S.img)}/${S.lab}?${q}`);
  if (id !== RENDER_ID) return;
  let pre = "", post = "";
  if (d.info) {
    const i = d.info;
    pre = `<div class="kv"><div><div class="k">Width</div><div class="v">${i.width}</div></div><div><div class="k">Height</div><div class="v">${i.height}</div></div>
      <div><div class="k">Channels</div><div class="v">${i.channels}</div></div><div><div class="k">Mean R</div><div class="v">${i["mean R"]}</div></div>
      <div><div class="k">Mean G</div><div class="v">${i["mean G"]}</div></div><div><div class="k">Mean B</div><div class="v">${i["mean B"]}</div></div></div>
      <div class="pixel"><span class="swatch" id="sw"></span><span id="px">Click the first image to read a pixel's RGB value.</span></div>`;
  }
  if (d.hist) post = `<h2 class="sec">Grey-level histogram</h2><div class="keyline"><span><i></i>equalised</span><span><i class="b"></i>original</span></div>
      <div class="chart">${lineChart([{ data: d.hist.original, color: "#b5b5b5", dash: "4 3" }, { data: d.hist.equalised, color: "#0a0a0a" }], { w: 900, h: 160, clip: true })}</div>`;
  if (d.centers) post = `<h2 class="sec">Cluster centres</h2><div class="swatches">${d.centers.map((c) => `<span style="background:rgb(${c.join(",")})" title="rgb(${c.join(", ")})"></span>`).join("")}</div>`;
  if (d.lbp_hist) post = `<h2 class="sec">LBP histogram</h2><div class="chart">${barChart(d.lbp_hist.map((v, i) => ({ name: String(i), value: v, raw: true })), { w: 900, h: 170, d: 2 })}</div>`;
  const ncol = d.items.length === 4 ? "g2" : d.items.length >= 7 ? "g4" : "g3";
  out.innerHTML = pre + `<div class="grid ${ncol}">${d.items.map((it) => card({ src: it.img, title: it.title, right: it.stat || "", fn: it.fn })).join("")}</div>` + post;
  if (d.info) {
    const first = $(".card .media img", out);
    first.parentElement.style.cursor = "crosshair";
    first.parentElement.onclick = (e) => {
      e.stopPropagation();
      const c = document.createElement("canvas");
      c.width = first.naturalWidth; c.height = first.naturalHeight;
      const ctx = c.getContext("2d");
      ctx.drawImage(first, 0, 0);
      const r = first.getBoundingClientRect();
      const x = Math.floor(((e.clientX - r.left) / r.width) * c.width), y = Math.floor(((e.clientY - r.top) / r.height) * c.height);
      const [R, G, B] = ctx.getImageData(x, y, 1, 1).data;
      $("#sw").style.background = `rgb(${R},${G},${B})`;
      $("#px").textContent = `(${x}, ${y})  →  R ${R}  G ${G}  B ${B}`;
    };
  }
  return settle(id);
}

function overlay(rec, gt, conf, classes) {
  const boxes = rec.boxes.filter((b) => b[4] >= conf);
  const rect = (b, outer, inner, dash) => {
    const [x1, y1, x2, y2] = b.map((v) => v * 100);
    return `<rect x="${x1}" y="${y1}" width="${x2 - x1}" height="${y2 - y1}" fill="none" stroke="${outer}" stroke-width="4" vector-effect="non-scaling-stroke"/>
      <rect x="${x1}" y="${y1}" width="${x2 - x1}" height="${y2 - y1}" fill="none" stroke="${inner}" stroke-width="1.6" ${dash ? 'stroke-dasharray="5 3"' : ""} vector-effect="non-scaling-stroke"/>`;
  };
  const svg = [...(gt || []).map((b) => rect(b, "#0a0a0a", "#ffffff", true)), ...boxes.map((b) => rect(b, "#0a0a0a", "#ffffff", false))].join("");
  // labels sit above the box; boxes touching the top get them inside, boxes on the right are right-aligned
  const lbl = boxes.map((b) => {
    const x = b[0] > 0.6 ? `right:${(1 - b[2]) * 100}%` : `left:${b[0] * 100}%`;
    return `<span class="lbl${b[1] < 0.08 ? " in" : ""}" style="${x};top:${b[1] * 100}%">${esc(classes[b[5]] || b[5])} ${b[4].toFixed(2)}</span>`;
  }).join("");
  return { html: `<div class="boxes"><svg viewBox="0 0 100 100" preserveAspectRatio="none">${svg}</svg>${lbl}</div>`, n: boxes.length,
           mean: boxes.length ? boxes.reduce((a, b) => a + b[4], 0) / boxes.length : null };
}
async function pageDetect(id) {
  const intro = "Our YOLO11-s detector, trained on raw RUOD images and then frozen, runs on every version. For sample images with ground truth, the per-image AP shows whether each enhancer helped or hurt.";
  VIEW.innerHTML = head("04 — Detection", "What the detector sees", intro) + loading("Running the detector on every version…");
  let d;
  try { d = await api(`/api/detect/${encodeURIComponent(S.img)}`); }
  catch (e) {
    if (id !== RENDER_ID) return;
    VIEW.innerHTML = head("04 — Detection", "What the detector sees", intro) +
      `<div class="empty">${e.status === 503 ? "Detector weights not found. Put <span class='mono'>best.pt</span> from Kaggle notebook 07 into <span class='mono'>app/assets/</span>." : esc(e.message)}</div>${foot()}`;
    return;
  }
  if (id !== RENDER_ID) return;
  const hasGT = !!d.gt;
  VIEW.innerHTML = head("04 — Detection", "What the detector sees", intro) + `
    <div class="controls"><div class="ctl"><label>Confidence threshold</label><div class="range">
      <input type="range" id="conf" min="0.05" max="0.9" step="0.05" value="${S.conf}"><output>${S.conf.toFixed(2)}</output></div></div>
      ${hasGT ? `<div class="ctl"><label>Ground truth</label><label class="check"><input type="checkbox" id="gt" ${S.gt ? "checked" : ""}>Show ground-truth boxes (dashed)</label></div>` : ""}</div>
    <div class="grid g3" id="detgrid"></div><div id="dettable"></div>${foot()}`;
  const draw = () => {
    const best = hasGT ? d.variants.reduce((a, b) => (b.ap > a.ap ? b : a)) : null;
    $("#detgrid").innerHTML = d.variants.map((rec) => {
      const o = overlay(rec, S.gt ? d.gt : null, S.conf, d.classes);
      rec._n = o.n; rec._mean = o.mean;
      return card({ src: imgURL(rec.key, 900), full: imgURL(rec.key, 1280), title: rec.name, raw: rec.key === "raw",
        right: `${o.n} det${hasGT ? ` · AP ${fmt(rec.ap)}` : ""}`, overlay: o.html, caption: `${rec.name} — detections at confidence ≥ ${S.conf.toFixed(2)}` });
    }).join("");
    const rows = d.variants.map((r) => `<tr${best && r.key === best.key ? ' class="hl"' : ""}><td class="name">${esc(r.name)}${best && r.key === best.key ? ' <span class="tag tag-helps" style="margin-left:6px">best</span>' : ""}</td>
      <td class="num">${r._n}</td><td class="num">${fmt(r._mean)}</td>
      ${hasGT ? `<td class="num">${fmt(r.ap)}</td><td class="num">${fmt(r.ap50)}</td><td class="num">${fmt(r.f1)}</td>
      <td class="num">${r.key === "raw" ? '<span class="flat">baseline</span>' : delta(r.dap, d.tau)}</td>
      ${Object.keys(d.study_dap).length ? `<td class="num">${r.key === "raw" ? '<span class="flat">—</span>' : delta(d.study_dap[r.key], d.tau)}</td>` : ""}` : ""}</tr>`).join("");
    $("#dettable").innerHTML = `<h2 class="sec">Per-version results</h2>
      <div class="tbl-wrap"><table><thead><tr><th>Version</th><th class="num">Detections ≥ ${S.conf.toFixed(2)}</th><th class="num">Mean confidence</th>
      ${hasGT ? `<th class="num">AP 50:95</th><th class="num">AP 50</th><th class="num">F1 @ 0.25</th><th class="num">ΔAP vs raw</th>${Object.keys(d.study_dap).length ? '<th class="num">ΔAP in study</th>' : ""}` : ""}</tr></thead><tbody>${rows}</tbody></table></div>
      ${hasGT ? `<div class="callout"><span class="k">This image</span><p>${d.gt.length} ground-truth objects. ${best.key === "raw"
          ? `No enhancer beats the raw image here (raw AP ${fmt(best.ap)}).`
          : `Best version for the detector: <b>${esc(best.name)}</b> (AP ${fmt(best.ap)} vs raw ${fmt(d.variants[0].ap)}).`}
        Across the 7,000 held-out images of the study every enhancer lowered mean AP, yet each helped about one image in nine by more than the noise threshold of ${d.tau}.</p></div>`
        : `<p class="note">Uploaded images have no ground truth, so only detection counts and confidences are shown.</p>`}`;
  };
  draw();
  $("#conf").oninput = (e) => { S.conf = +e.target.value; e.target.nextElementSibling.textContent = S.conf.toFixed(2); draw(); };
  if (hasGT) $("#gt").onchange = (e) => { S.gt = e.target.checked; draw(); };
}

/* ------------------------------------------------------------------ main loop */
async function render() {
  readHash();
  renderChrome();
  const id = ++RENDER_ID;
  document.body.dataset.ready = "0";
  window.scrollTo(0, 0);
  if (!S.img && S.page !== "overview") {
    VIEW.innerHTML = `<div class="empty">Select a sample image or upload one to begin.</div>`;
    return settle(id);
  }
  try {
    const fn = { overview: pageOverview, enhance: pageEnhance, quality: pageQuality, lab: pageLab, detect: pageDetect }[S.page];
    await fn(id);
  } catch (e) {
    if (id === RENDER_ID) VIEW.innerHTML = `<div class="empty">Something went wrong: ${esc(e.message)}</div>`;
  }
  if (S.page !== "lab") await settle(id);
}

async function upload(file) {
  const fd = new FormData();
  fd.append("file", file);
  const drop = $("#drop");
  drop.classList.add("over");
  try {
    const r = await api("/api/upload", { method: "POST", body: fd });
    if (!UPLOADS.some((u) => u.id === r.id)) UPLOADS.unshift({ id: r.id });
    renderPicker();
    go({ img: r.id, page: S.page === "overview" ? "enhance" : S.page });
  } catch (e) {
    alert("Upload failed: " + e.message);
  } finally {
    drop.classList.remove("over");
  }
}

function wire() {
  $("#thumbs").onclick = (e) => { const b = e.target.closest(".thumb"); if (b) go({ img: b.dataset.id }); };
  $("#file").onchange = (e) => e.target.files[0] && upload(e.target.files[0]);
  const drop = $("#drop");
  ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => e.dataTransfer.files[0] && upload(e.dataTransfer.files[0]));
  const lb = $("#lightbox");
  VIEW.addEventListener("click", (e) => {
    const m = e.target.closest(".media");
    if (!m || m.style.cursor === "crosshair") return;
    const box = $(".lb-media", lb);
    box.innerHTML = `<img alt="" src="${m.dataset.full}">`;
    const ov = $(".boxes", m);
    if (ov) box.appendChild(ov.cloneNode(true));  // keep detection boxes in the enlarged view
    $("figcaption", lb).textContent = m.dataset.caption;
    lb.hidden = false;
  });
  lb.onclick = () => (lb.hidden = true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") lb.hidden = true; });
  window.addEventListener("hashchange", render);
}

(async function init() {
  wire();
  try { STATUS = await api("/api/status"); } catch (e) { /* server offline */ }
  renderPicker();
  render();
})();

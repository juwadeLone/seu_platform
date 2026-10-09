/* orbit_seu 3D 引擎（index.html 与 /3d 独立页共用）
 * 特性：真实地表纹理 + 昼夜光照、SEU 危险度渐变体渲染、
 *       太阳/宇宙线粒子、卫星动画、拖拽旋转、滚轮以光标为中心缩放、
 *       平移（右键/Shift 拖拽）、视角预设（全景/近地/中轨）、单击定位卫星。
 */
(function () {
"use strict";

const RC_EQ = 14.9;
const M = Math.hypot(1450.9, -4652.7, 29404.8);
const POLE = [1450.9 / M, -4652.7 / M, 29404.8 / M];
const E1 = (() => { const r = [-POLE[1], POLE[0], 0], n = Math.hypot(...r) || 1;
                     return r.map(v => v / n); })();
const E2 = [POLE[1]*E1[2] - POLE[2]*E1[1], POLE[2]*E1[0] - POLE[0]*E1[2],
            POLE[0]*E1[1] - POLE[1]*E1[0]];
const SUN = (() => { const s = [-1.0, 0.35, 0.45], n = Math.hypot(...s);
                     return s.map(v => v / n); })();

function spinPole(p, ang) {
  const c = Math.cos(ang), s = Math.sin(ang);
  const dot = p[0] * POLE[0] + p[1] * POLE[1] + p[2] * POLE[2];
  const cx = POLE[1] * p[2] - POLE[2] * p[1];
  const cy = POLE[2] * p[0] - POLE[0] * p[2];
  const cz = POLE[0] * p[1] - POLE[1] * p[0];
  const k = 1 - c;
  return [p[0] * c + cx * s + POLE[0] * dot * k,
          p[1] * c + cy * s + POLE[1] * dot * k,
          p[2] * c + cz * s + POLE[2] * dot * k];
}
function dipPoint(r, lamDeg, phDeg) {
  const lam = lamDeg*Math.PI/180, ph = phDeg*Math.PI/180;
  const c = Math.cos(lam), s = Math.sin(lam);
  const cp = Math.cos(ph), sp = Math.sin(ph);
  return [ r*(c*(cp*E1[0] + sp*E2[0]) + s*POLE[0]),
           r*(c*(cp*E1[1] + sp*E2[1]) + s*POLE[1]),
           r*(c*(cp*E1[2] + sp*E2[2]) + s*POLE[2]) ];
}
function latlon2xyz(latDeg, lonDeg) {
  const la = latDeg*Math.PI/180, lo = lonDeg*Math.PI/180;
  return [Math.cos(la)*Math.cos(lo), Math.cos(la)*Math.sin(lo), Math.sin(la)];
}
function rcAt(p) {
  const r = Math.hypot(...p);
  const s = (p[0]*POLE[0] + p[1]*POLE[1] + p[2]*POLE[2]) / r;
  const c = Math.sqrt(Math.max(0, 1 - s*s));
  return RC_EQ * c**4 / (r*r);
}
const FLD = (() => {
  const lines = [];
  for (const L of [1.5, 1.8, 2.2, 2.6, 3.2, 4, 4.8, 5.6, 6]) for (const phi of [0, 45, 90, 135, 180, 225, 270, 315]) {
    const seg = [];
    for (let lam = -80; lam <= 80; lam += 3)
      seg.push(dipPoint(L * Math.cos(lam*Math.PI/180)**2, lam, phi));
    lines.push({ L, seg });
  }
  return lines;
})();
const SHELL_DEFS = [
  [0.5, "255,95,86"], [1, "255,138,92"], [2, "255,180,84"],
  [4, "255,210,63"], [8, "154,219,98"], [12, "77,163,255"]];
const VSH = (() => {           // 细化网格：λ 步 6°，φ 步 15°
  const shells = [];
  const lams = [];
  for (let l = -72; l <= 72; l += 6) lams.push(l);
  for (const [rc, rgb] of SHELL_DEFS) {
    const quads = [];
    for (let li = 0; li < lams.length - 1; li++) {
      const r0 = Math.sqrt(RC_EQ * Math.cos(lams[li]  *Math.PI/180)**4 / rc);
      const r1 = Math.sqrt(RC_EQ * Math.cos(lams[li+1]*Math.PI/180)**4 / rc);
      for (let ph = 0; ph < 360; ph += 15) {
        quads.push([ dipPoint(r0, lams[li], ph), dipPoint(r1, lams[li+1], ph),
                     dipPoint(r1, lams[li+1], ph+15), dipPoint(r0, lams[li], ph+15) ]);
      }
    }
    shells.push({ rc, rgb, quads });
  }
  return shells;
})();
const SAA = (() => {
  const pts = [];
  for (let t = 0; t <= 360; t += 6)
    pts.push(latlon2xyz(-26 + 24*Math.sin(t*Math.PI/180),
                        -45 + 34*Math.cos(t*Math.PI/180)));
  return pts;
})();
/* 辐射带（示意层，经典范艾伦带图风格）：
 * 内带 L≈1.3–2.6（蓝紫，质子带），外带 L≈3–6（橙红，电子带）。
 * 壳面沿偶极磁力线几何 r=L·cos²λ 勾画。粒子在各自镜点纬度之间反弹，并沿方位漂移；
 * 多数留在赤道，少数才到高纬。位置为公开常识示意，强度非模型计算。 */
const BELTS = (() => {
  const mk = (L0, L1, n, lamMax, rgb) => {
    const Ls = [];
    for (let k = 0; k < n; k++) Ls.push(L0 + (L1 - L0) * k / (n - 1));
    const quads = [];
    const lams = [];
    const midL = (L0 + L1) / 2, span = (L1 - L0) / 2 || 1;
    for (let l = -lamMax; l <= lamMax; l += 9) lams.push(l);
    for (const L of Ls)
      for (let li = 0; li < lams.length - 1; li++)
        for (let ph = 0; ph < 360; ph += 24) {
          const f = (lam) => dipPoint(L * Math.cos(lam*Math.PI/180)**2, lam, ph);
          const g = (lam) => dipPoint(L * Math.cos(lam*Math.PI/180)**2, lam, ph+24);
          const core = 0.18 + 0.82 * (1 - Math.abs(L - midL) / span);
          quads.push([ f(lams[li]), f(lams[li+1]), g(lams[li+1]), g(lams[li]), core ]);
        }
    return { rgb, quads };
  };
  return [ mk(1.3, 2.6, 8, 60, "118,140,255"),   // 内带：蓝紫
           mk(3.0, 6.0, 8, 55, "255,110,70") ];  // 外带：橙红
})();
function rcColor(rc) {
  if (rc < 1) return "#ff5f56";
  if (rc < 3) return "#ff9e64";
  if (rc < 8) return "#ffd23f";
  return "#4da3ff";
}
function rigColor(r) { return r > 15 ? "#bfe0ff" : r > 5 ? "#ffd23f" : "#ff9e64"; }
function randDir() {
  const u = Math.random()*2 - 1, ph = Math.random()*2*Math.PI, s = Math.sqrt(1-u*u);
  return [s*Math.cos(ph), s*Math.sin(ph), u];
}

/* 地球纹理（NASA Blue Marble，公有领域） */
const earthTex = { data: null, w: 0, h: 0, rc: null, key: "", veil: null, veilKey: "" };
(function loadEarth() {
  const im = new Image();
  im.onload = () => {
    const c = document.createElement("canvas");
    c.width = im.width; c.height = im.height;
    const g = c.getContext("2d");
    g.drawImage(im, 0, 0);
    earthTex.data = g.getImageData(0, 0, im.width, im.height).data;
    earthTex.w = im.width; earthTex.h = im.height;
  };
  im.src = "/static/earth.jpg";
})();

window.OrbitViewer = function (canvas, opts) {
  opts = opts || {};
  const S = {
    result: null, cmp: [],
    playing: true, speed: 1,
    frac: 0, last: 0, sel: -1,
    view: { yaw: -0.7, pitch: 0.42, zoom: 1, panX: 0, panY: 0, auto: true },
    drag: null, p3: [], showBelts: true
  };
  const readEl = opts.readout || null;
  const onSel = opts.onSelect || null;

  function setReadout(html) { if (readEl) readEl.innerHTML = html; }

  function ctxOf() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (w > 0 && canvas.width !== Math.round(w*dpr)) {
      canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return [ctx, canvas.clientWidth, canvas.clientHeight];
  }
  function proj(p) {
    const v = S.view;
    const cy = Math.cos(v.yaw), sy = Math.sin(v.yaw);
    const x = p[0]*cy - p[1]*sy, y = p[0]*sy + p[1]*cy, z = p[2];
    const cp = Math.cos(v.pitch), sp = Math.sin(v.pitch);
    return { x, y: y*cp - z*sp, z: y*sp + z*cp };
  }
  function sampleEarth(TD, TW, TH, u, v) {
    const x = ((u % TW) + TW) % TW;
    const y = Math.max(0, Math.min(TH - 1.001, v));
    const x0 = Math.floor(x), y0 = Math.floor(y);
    const tx = x - x0, ty = y - y0;
    const x1 = (x0 + 1) % TW, y1 = Math.min(TH - 1, y0 + 1);
    const pix = (px, py) => {
      const t = (py * TW + px) * 4;
      return [TD[t], TD[t + 1], TD[t + 2]];
    };
    const a = pix(x0, y0), b = pix(x1, y0), c = pix(x0, y1), d = pix(x1, y1);
    return [
      (a[0] * (1 - tx) + b[0] * tx) * (1 - ty) + (c[0] * (1 - tx) + d[0] * tx) * ty,
      (a[1] * (1 - tx) + b[1] * tx) * (1 - ty) + (c[1] * (1 - tx) + d[1] * tx) * ty,
      (a[2] * (1 - tx) + b[2] * tx) * (1 - ty) + (c[2] * (1 - tx) + d[2] * tx) * ty,
    ];
  }
  function renderEarthTex(sc, light) {
    const yawQ = Math.round(S.view.yaw / 0.04) * 0.04;
    const pitchQ = Math.round(S.view.pitch / 0.04) * 0.04;
    const N = Math.max(280, Math.min(1024, Math.round(sc * 2.6)));
    const key = `${N}|${yawQ.toFixed(3)}|${pitchQ.toFixed(3)}|` +
                `${light[0].toFixed(2)}|${light[1].toFixed(2)}|${light[2].toFixed(2)}`;
    if (earthTex.rc && earthTex.key === key) return earthTex.rc;
    const c = earthTex.rc || (earthTex.rc = document.createElement("canvas"));
    c.width = c.height = N;
    const g = c.getContext("2d");
    const img = g.createImageData(N, N);
    const D = img.data, TD = earthTex.data, TW = earthTex.w, TH = earthTex.h;
    const cy_ = Math.cos(yawQ), sy_ = Math.sin(yawQ);
    const cp = Math.cos(pitchQ), sp = Math.sin(pitchQ);
    const half = N / 2;
    for (let j = 0; j < N; j++) {
      const dy = (j - half + 0.5) / (half - 1);
      for (let i = 0; i < N; i++) {
        const dx = (i - half + 0.5) / (half - 1);
        const r2 = dx * dx + dy * dy, o = (j * N + i) * 4;
        if (r2 > 1) { D[o + 3] = 0; continue; }
        const nz = Math.sqrt(1 - r2), ny = -dy;
        const y1 = ny * cp + nz * sp, z1 = -ny * sp + nz * cp;
        const gx = dx * cy_ + y1 * sy_, gy = -dx * sy_ + y1 * cy_, gz = z1;
        const lat = Math.asin(Math.max(-1, Math.min(1, gz)));
        const u = (Math.atan2(gy, gx) * 180 / Math.PI + 180) / 360 * TW;
        const v = (90 - lat * 180 / Math.PI) / 180 * TH;
        const rgb = sampleEarth(TD, TW, TH, u, v);
        const ndot = dx * light[0] + ny * light[1] + nz * light[2];
        const day = Math.max(0, ndot);
        const cr = rgb[0], cg = rgb[1], cb = rgb[2];
        const t = Math.max(0, Math.min(1, (ndot + 0.08) / 0.28));
        const lam = t * t * (3 - 2 * t);
        const water = rgb[2] > rgb[0] + 6 && rgb[2] > rgb[1];
        const spec = water ? Math.pow(day, 16) * 90 : Math.pow(day, 48) * 28;
        const rim = r2 > 0.82 ? (r2 - 0.82) / 0.18 : 0;
        const air = rim * rim;
        const cityGate = Math.abs(Math.sin(u * 0.41) * Math.sin(v * 0.33));
        const city2 = Math.abs(Math.sin(u * 0.17 + 1.2) * Math.sin(v * 0.23));
        const city = (!water && lam < 0.42 && rgb[0] + rgb[1] > 60
          && (cityGate > 0.86 || city2 > 0.9))
          ? (0.42 - lam) / 0.42 * 255 : 0;
        const warm = Math.exp(-((ndot - 0.02) * (ndot - 0.02)) / 0.02);
        const blueTw = (ndot < 0 && ndot > -0.35) ? Math.sin((ndot + 0.35) / 0.35 * Math.PI) * rim : 0;
        const lit = 0.06 + 0.94 * lam;
        D[o]     = Math.min(255, cr * lit * (1 - air * 0.45) + spec + 55 * air + city + warm * 110);
        D[o + 1] = Math.min(255, cg * lit * (1 - air * 0.25) + spec * 0.85 + 120 * air + city * 0.72 + warm * 28 + blueTw * 18);
        D[o + 2] = Math.min(255, cb * lit + spec * 0.45 + 200 * air + city * 0.32 + blueTw * 48);
        D[o + 3] = 255;
      }
    }
    g.putImageData(img, 0, 0);
    earthTex.key = key;
    return c;
  }
  function renderCloudVeil(light, tNow) {
    const yawQ = Math.round(S.view.yaw / 0.04) * 0.04;
    const pitchQ = Math.round(S.view.pitch / 0.04) * 0.04;
    const bucket = Math.floor(tNow / 180);
    const shift = bucket * 2.6;
    const N = 512;
    const key = `${yawQ.toFixed(3)}|${pitchQ.toFixed(3)}|${bucket}|` +
                `${light[0].toFixed(2)}|${light[1].toFixed(2)}|${light[2].toFixed(2)}`;
    if (earthTex.veil && earthTex.veilKey === key) return earthTex.veil;
    const c = earthTex.veil || (earthTex.veil = document.createElement("canvas"));
    c.width = c.height = N;
    const g = c.getContext("2d");
    const img = g.createImageData(N, N);
    const D = img.data, TW = earthTex.w, TH = earthTex.h;
    const cy_ = Math.cos(yawQ), sy_ = Math.sin(yawQ);
    const cp = Math.cos(pitchQ), sp = Math.sin(pitchQ);
    const half = N / 2;
    for (let j = 0; j < N; j++) {
      const dy = (j - half + 0.5) / (half - 1);
      for (let i = 0; i < N; i++) {
        const dx = (i - half + 0.5) / (half - 1);
        const r2 = dx * dx + dy * dy, o = (j * N + i) * 4;
        if (r2 > 1) { D[o + 3] = 0; continue; }
        const nz = Math.sqrt(1 - r2), ny = -dy;
        const y1 = ny * cp + nz * sp, z1 = -ny * sp + nz * cp;
        const gx = dx * cy_ + y1 * sy_, gy = -dx * sy_ + y1 * cy_, gz = z1;
        const lat = Math.asin(Math.max(-1, Math.min(1, gz)));
        const u = (Math.atan2(gy, gx) * 180 / Math.PI + 180) / 360 * TW + shift;
        const v = (90 - lat * 180 / Math.PI) / 180 * TH;
        const ndot = dx * light[0] + ny * light[1] + nz * light[2];
        const day = Math.max(0, ndot);
        const uu = u;
        const n1 = Math.sin(uu * 0.021) * Math.sin(v * 0.017);
        const n2 = Math.sin(uu * 0.053 + v * 0.02) * Math.sin(v * 0.041 + 1.3);
        const n3 = Math.sin((uu + v) * 0.09) * Math.sin((uu - v) * 0.07 + 2.2);
        const n4 = Math.sin(uu * 0.13 + 0.6) * Math.sin(v * 0.11);
        const front = Math.exp(-((((v / TH) - 0.38 - 0.06 * Math.sin(uu * 0.012)) * 22) ** 2));
        const front2 = Math.exp(-((((v / TH) - 0.62 - 0.05 * Math.sin(uu * 0.009 + 1.4)) * 26) ** 2));
        const cl = n1 * 0.42 + n2 * 0.26 + n3 * 0.16 + n4 * 0.22 + front * 0.55 + front2 * 0.42;
        const us = uu + 22, vs = v + 14;
        const n1s = Math.sin(us * 0.021) * Math.sin(vs * 0.017);
        const n2s = Math.sin(us * 0.053 + vs * 0.02) * Math.sin(vs * 0.041 + 1.3);
        const n4s = Math.sin(us * 0.13 + 0.6) * Math.sin(vs * 0.11);
        const frontS = Math.exp(-((((vs / TH) - 0.38 - 0.06 * Math.sin(us * 0.012)) * 22) ** 2));
        const front2S = Math.exp(-((((vs / TH) - 0.62 - 0.05 * Math.sin(us * 0.009 + 1.4)) * 26) ** 2));
        const sh = Math.max(0, (n1s * 0.42 + n2s * 0.26 + n3 * 0.16 + n4s * 0.22 + frontS * 0.55 + front2S * 0.42) - 0.18) * day;
        const cw = Math.max(0, cl - 0.1) * (0.48 + 0.52 * day);
        const uh = uu + shift * 0.85;
        const high = Math.max(0, Math.sin(uh * 0.037) * Math.sin(v * 0.029 + 0.7) - 0.42) * (0.25 + 0.75 * day);
        const highSh = Math.max(0, Math.sin((uh + 40) * 0.037) * Math.sin((v + 22) * 0.029 + 0.7) - 0.42) * day;
        if (cw > 0.03) {
          D[o] = 246; D[o + 1] = 248; D[o + 2] = 252;
          D[o + 3] = Math.min(210, Math.round(cw * 255));
        } else if (high > 0.03) {
          D[o] = 255; D[o + 1] = 255; D[o + 2] = 255;
          D[o + 3] = Math.min(130, Math.round(high * 240));
        } else if (highSh > 0.04) {
          D[o] = 8; D[o + 1] = 12; D[o + 2] = 24;
          D[o + 3] = Math.min(150, Math.round(highSh * 210));
        } else if (sh > 0.04) {
          D[o] = 6; D[o + 1] = 10; D[o + 2] = 22;
          D[o + 3] = Math.min(180, Math.round(sh * 230));
        } else D[o + 3] = 0;
      }
    }
    g.putImageData(img, 0, 0);
    earthTex.veilKey = key;
    return c;
  }
  function spawnP3(rmax) {
    const dir = Math.random() < 0.7 ? SUN : randDir();
    const r0 = rmax * (1.5 + Math.random()*0.8);
    return { p: dir.map(v => v*r0), v: 0.5 + Math.random()*0.55,
             rig: Math.pow(10, 0.3 + Math.random()*1.9), fade: 1 };
  }

  function draw(tNow) {
    try {
    const [ctx, w, h] = ctxOf();
    if (w === 0) { requestAnimationFrame(draw); return; }
    const dt = Math.min((tNow - (S.last || tNow)) / 1000, 0.05);
    S.last = tNow;
    if (!Number.isFinite(S.view.zoom) || S.view.zoom <= 0) S.view.zoom = 1;
    if (!Number.isFinite(S.view.panX) || !Number.isFinite(S.view.panY)) {
      S.view.panX = 0; S.view.panY = 0;
    }
    if (S.view.auto && !S.drag) S.view.yaw += 0.0009;
    ctx.clearRect(0, 0, w, h);
    if (!S.stars || S.stars.w !== w || S.stars.h !== h) {
      const scv = document.createElement("canvas");
      scv.width = w; scv.height = h;
      const sg = scv.getContext("2d");
      sg.fillStyle = "#05070c";
      sg.fillRect(0, 0, w, h);
      let seed = 20260820;
      const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
      for (let n = 0; n < Math.floor(w * h / 900); n++) {
        const x = rnd() * w, y = rnd() * h, m = rnd();
        sg.fillStyle = m > 0.97 ? "rgba(255,244,220,0.95)"
          : m > 0.8 ? "rgba(190,210,255,0.7)" : "rgba(255,255,255,0.45)";
        sg.fillRect(x, y, m > 0.97 ? 1.6 : 1, m > 0.97 ? 1.6 : 1);
      }
      S.stars = { w, h, cvs: scv };
    }
    ctx.drawImage(S.stars.cvs, 0, 0);

    const tracks = S.cmp.length
      ? S.cmp.map(c => ({ color: c.color, pts: c.track, solid: true }))
      : (S.result && (S.result.series.orbit_track_xyz_re || []).length)
        ? [{ pts: S.result.series.orbit_track_xyz_re, solid: false }] : [];
    const rmax = Math.max(2.2, ...tracks.map(t =>
      Math.max(...t.pts.map(p => Math.hypot(p[0], p[1], p[2]))))) * 1.15;
    const cx = w/2 + S.view.panX, cy = h/2 + S.view.panY;
    const sc = Math.min(w, h) * 0.42 * S.view.zoom / rmax;
    const Lq = proj(SUN);
    const Ln = Math.hypot(Lq.x, Lq.y, Lq.z) || 1;
    const light = [Lq.x/Ln, Lq.y/Ln, Lq.z/Ln];
    const hidden = q => q.z < 0 && Math.hypot(q.x, q.y) < 1;

    // 等截止壳体仍叠在星空上，不再铺一整块红底盖住地表
    const quads = [];
    for (const sh of VSH) for (const q of sh.quads) {
      const a = proj(q[0]), b = proj(q[1]), c = proj(q[2]), d = proj(q[3]);
      const z = (a.z + b.z + c.z + d.z) / 4;
      if (Math.abs(a.x)+Math.abs(b.x)+Math.abs(c.x)+Math.abs(d.x) > 4*rmax) continue;
      quads.push({ a, b, c, d, rgb: sh.rgb, z });
    }
    if (S.showBelts)
      BELTS.forEach((belt, bi) => {
        const ang = tNow * (bi ? 0.00009 : 0.0002);
        for (const q of belt.quads) {
          const p0 = spinPole(q[0], ang), p1 = spinPole(q[1], ang);
          const p2 = spinPole(q[2], ang), p3 = spinPole(q[3], ang);
          const a = proj(p0), b = proj(p1), c = proj(p2), d = proj(p3);
          const z = (a.z + b.z + c.z + d.z) / 4;
          if (Math.abs(a.x)+Math.abs(b.x)+Math.abs(c.x)+Math.abs(d.x) > 4*rmax) continue;
          const midZ = (p0[2] + p1[2] + p2[2] + p3[2]) / 4;
          const eq0 = Math.max(0.06, 1 - Math.abs(midZ) / 2.2);
          const ph = Math.atan2(q[0][1], q[0][0]);
          const wave = 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(ph * 4 - tNow * 0.0012));
          quads.push({ a, b, c, d, rgb: belt.rgb, z, belt: true, eq: eq0 * wave * (q[4] || 1) });
        }
      });
    quads.sort((u, v) => u.z - v.z);
    const paintQuads = (list, alphaF) => {
      for (const q of list) {
        ctx.fillStyle = `rgba(${q.rgb},${alphaF(q)})`;
        ctx.beginPath();
        ctx.moveTo(cx + sc*q.a.x, cy - sc*q.a.y);
        ctx.lineTo(cx + sc*q.b.x, cy - sc*q.b.y);
        ctx.lineTo(cx + sc*q.c.x, cy - sc*q.c.y);
        ctx.lineTo(cx + sc*q.d.x, cy - sc*q.d.y);
        ctx.closePath(); ctx.fill();
      }
    };
    paintQuads(quads.filter(q => q.z < 0), q => 0.035);
    const paintBeltVolume = (front) => {
      if (!S.showBelts) return;
      const ribbons = [
        { L0: 1.55, L1: 2.25, rgb: "150,180,255", spin: 0.0002 },
        { L0: 3.7, L1: 5.3, rgb: "255,150,100", spin: 0.00009 },
      ];
      for (const sh of ribbons) {
        const ang = tNow * sh.spin;
        for (const lam of [-16, 0, 16]) {
          const a = (front ? 0.2 : 0.07) * (lam === 0 ? 1 : 0.4);
          for (let ph = 0; ph < 360; ph += 8) {
            const sample = (L, p) => proj(spinPole(
              dipPoint(L * Math.cos(lam * Math.PI / 180) ** 2, lam, p), ang));
            const q00 = sample(sh.L0, ph);
            const q01 = sample(sh.L0, ph + 8);
            const q10 = sample(sh.L1, ph);
            const q11 = sample(sh.L1, ph + 8);
            const z = (q00.z + q01.z + q10.z + q11.z) * 0.25;
            if ((z >= 0) !== front) continue;
            ctx.fillStyle = `rgba(${sh.rgb},${a.toFixed(3)})`;
            ctx.beginPath();
            ctx.moveTo(cx + sc * q00.x, cy - sc * q00.y);
            ctx.lineTo(cx + sc * q10.x, cy - sc * q10.y);
            ctx.lineTo(cx + sc * q11.x, cy - sc * q11.y);
            ctx.lineTo(cx + sc * q01.x, cy - sc * q01.y);
            ctx.closePath();
            ctx.fill();
          }
        }
        const Lskin = (sh.L0 + sh.L1) * 0.5;
        for (const lam1 of [18, -18]) {
          const a = front ? 0.16 : 0.05;
          for (let ph = 0; ph < 360; ph += 10) {
            const sample = (lam, p) => proj(spinPole(
              dipPoint(Lskin * Math.cos(lam * Math.PI / 180) ** 2, lam, p), ang));
            const q00 = sample(0, ph);
            const q01 = sample(0, ph + 10);
            const q10 = sample(lam1, ph);
            const q11 = sample(lam1, ph + 10);
            const z = (q00.z + q01.z + q10.z + q11.z) * 0.25;
            if ((z >= 0) !== front) continue;
            ctx.fillStyle = `rgba(${sh.rgb},${a.toFixed(3)})`;
            ctx.beginPath();
            ctx.moveTo(cx + sc * q00.x, cy - sc * q00.y);
            ctx.lineTo(cx + sc * q10.x, cy - sc * q10.y);
            ctx.lineTo(cx + sc * q11.x, cy - sc * q11.y);
            ctx.lineTo(cx + sc * q01.x, cy - sc * q01.y);
            ctx.closePath();
            ctx.fill();
          }
        }
      }
      const shells = [
        { L0: 1.45, L1: 2.35, n: 4, rgb: "130,160,255", spin: 0.0002, thick: 0.32 },
        { L0: 3.5, L1: 5.5, n: 5, rgb: "255,130,80", spin: 0.00009, thick: 0.62 },
      ];
      for (const sh of shells) {
        const ang = tNow * sh.spin;
        for (let k = 0; k < sh.n; k++) {
          const u = sh.n === 1 ? 0.5 : k / (sh.n - 1);
          const L = sh.L0 + (sh.L1 - sh.L0) * u;
          const core = 0.28 + 0.72 * (1 - Math.abs(u - 0.5) * 2);
          const lats = Math.abs(u - 0.5) < 0.2 ? [0, 24, -24, 42, -42] : [0];
          for (const lam of lats) {
          const latFade = Math.cos(lam * Math.PI / 180) ** 2;
          const step = lam === 0 ? 20 : 36;
          for (let ph = 0; ph < 360; ph += step) {
            const r = L * Math.cos(lam * Math.PI / 180) ** 2;
            const q = proj(spinPole(dipPoint(r, lam, ph), ang));
            if ((q.z >= 0) !== front) continue;
            const X = cx + sc * q.x, Y = cy - sc * q.y;
            const R = Math.max(3, sc * sh.thick * (0.62 + 0.38 * core) * latFade);
            const a = (front ? 0.24 : 0.1) * core * (0.4 + 0.6 * latFade);
            const g = ctx.createRadialGradient(X, Y, 0, X, Y, R);
            g.addColorStop(0, `rgba(${sh.rgb},${a.toFixed(3)})`);
            g.addColorStop(0.45, `rgba(${sh.rgb},${(a * 0.35).toFixed(3)})`);
            g.addColorStop(1, `rgba(${sh.rgb},0)`);
            ctx.fillStyle = g;
            ctx.beginPath();
            ctx.arc(X, Y, R, 0, 6.28);
            ctx.fill();
          }
          }
        }
      }
    };
    paintBeltVolume(false);

    // 地球
    ctx.beginPath(); ctx.arc(cx, cy, sc, 0, 2*Math.PI);
    ctx.save(); ctx.clip();
    if (earthTex.data) {
      ctx.drawImage(renderEarthTex(sc, light), cx-sc, cy-sc, sc*2, sc*2);
      ctx.drawImage(renderCloudVeil(light, tNow), cx-sc, cy-sc, sc*2, sc*2);
    }
    else {
      const grad = ctx.createRadialGradient(cx-sc*0.35, cy-sc*0.35, sc*0.2, cx, cy, sc);
      grad.addColorStop(0, "#2a5d8f"); grad.addColorStop(1, "#0d2237");
      ctx.fillStyle = grad; ctx.fill();
    }
    [[32, 20], [41, 90], [-18, 150], [12, 210], [48, 250], [-28, 310], [8, 50], [36, 175]].forEach(([lam, ph], i) => {
      const p = dipPoint(1.004, lam, ph);
      const sun = p[0] * SUN[0] + p[1] * SUN[1] + p[2] * SUN[2];
      const q = proj(p);
      if (q.z < 0.04 || sun > 0.08) return;
      const tw = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(tNow / 260 + i * 1.4));
      const X = cx + sc * q.x, Y = cy - sc * q.y;
      const rad = Math.max(4, sc * 0.045) * (0.75 + 0.35 * tw);
      const halo = ctx.createRadialGradient(X, Y, 0, X, Y, rad);
      halo.addColorStop(0, `rgba(255,200,120,${0.5 * tw})`);
      halo.addColorStop(1, "rgba(255,180,80,0)");
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(X, Y, rad, 0, 6.28);
      ctx.fill();
      ctx.fillStyle = `rgba(255,236,210,${tw})`;
      ctx.beginPath();
      ctx.arc(X, Y, 1.3, 0, 6.28);
      ctx.fill();
    });
    if (light[2] > 0.05) {
      const wob = Math.sin(tNow / 700) * sc * 0.015;
      const gx = cx + light[0] * sc * 0.42 + wob, gy = cy - light[1] * sc * 0.42;
      const galpha = 0.2 + 0.16 * (0.5 + 0.5 * Math.sin(tNow / 420));
      const glint = ctx.createRadialGradient(gx, gy, 1, gx, gy, sc * 0.11);
      glint.addColorStop(0, `rgba(255,250,230,${galpha})`);
      glint.addColorStop(1, "rgba(255,250,230,0)");
      ctx.fillStyle = glint;
      ctx.beginPath();
      ctx.ellipse(gx, gy, sc * 0.07, sc * 0.028, Math.atan2(-light[1], light[0]), 0, 6.28);
      ctx.fill();
    }
    const innerLimb = ctx.createRadialGradient(cx, cy, sc * 0.82, cx, cy, sc);
    innerLimb.addColorStop(0, "rgba(220,236,255,0)");
    innerLimb.addColorStop(0.78, "rgba(190,220,255,0)");
    innerLimb.addColorStop(1, "rgba(214,232,255,0.42)");
    ctx.fillStyle = innerLimb;
    ctx.beginPath();
    ctx.arc(cx, cy, sc, 0, 6.28);
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, sc * 1.22, 0, Math.PI * 2);
    ctx.arc(cx, cy, sc * 0.99, 0, Math.PI * 2, true);
    ctx.clip();
    const limb = ctx.createRadialGradient(cx, cy, sc * 0.99, cx, cy, sc * 1.22);
    limb.addColorStop(0, "rgba(236,248,255,0.95)");
    limb.addColorStop(0.16, "rgba(180,214,255,0.62)");
    limb.addColorStop(0.34, "rgba(168,140,220,0.28)");
    limb.addColorStop(0.58, "rgba(70,120,210,0.2)");
    limb.addColorStop(1, "rgba(30,70,150,0)");
    ctx.fillStyle = limb;
    ctx.fillRect(cx - sc * 1.26, cy - sc * 1.26, sc * 2.52, sc * 2.52);
    const sunX = cx + light[0] * sc * 0.85, sunY = cy - light[1] * sc * 0.85;
    const dayLimb = ctx.createRadialGradient(sunX, sunY, sc * 0.55, sunX, sunY, sc * 1.26);
    dayLimb.addColorStop(0, "rgba(255,236,190,0)");
    dayLimb.addColorStop(0.68, "rgba(255,220,160,0.5)");
    dayLimb.addColorStop(1, "rgba(255,220,160,0)");
    ctx.fillStyle = dayLimb;
    ctx.fillRect(cx - sc * 1.26, cy - sc * 1.26, sc * 2.52, sc * 2.52);
    const nightX = cx - light[0] * sc * 0.9, nightY = cy + light[1] * sc * 0.9;
    const airglow = ctx.createRadialGradient(nightX, nightY, sc * 0.35, nightX, nightY, sc * 1.24);
    airglow.addColorStop(0, "rgba(90,230,150,0)");
    airglow.addColorStop(0.78, "rgba(70,210,130,0.4)");
    airglow.addColorStop(1, "rgba(70,210,130,0)");
    ctx.fillStyle = airglow;
    ctx.fillRect(cx - sc * 1.26, cy - sc * 1.26, sc * 2.52, sc * 2.52);
    ctx.restore();
    const beltPulse = 0.05 + 0.03 * (0.5 + 0.5 * Math.sin(tNow / 650));
    paintQuads(quads.filter(q => q.z >= 0), q => q.belt ? beltPulse * 3.4 * q.eq : beltPulse);
    paintBeltVolume(true);
    if (S.showBelts) {
      if (!S.beltP) S.beltP = [];
      while (S.beltP.length < 1400) {
        const inner = Math.random() < 0.42;
        const u = Math.random();
        const mirror = (inner ? 8 : 6) + Math.pow(u, 1.7) * (inner ? 42 : 50);
        S.beltP.push({
          L: inner ? 1.25 + Math.random() * 0.95 : 3.0 + Math.random() * 2.8,
          phi: Math.random() * 360,
          lam: mirror * (Math.random() * 2 - 1),
          dir: Math.random() < 0.5 ? 1 : -1,
          speed: (inner ? 22 : 12) + Math.random() * 18,
          inner: inner,
          rad: inner ? 0.7 + Math.random() * 1.4 : 0.55 + Math.random() * 1.5,
          mirror: mirror,
        });
      }
      for (const p of S.beltP) {
        if (p.mirror == null) {
          const u = Math.random();
          p.mirror = (p.inner ? 8 : 6) + Math.pow(u, 1.7) * (p.inner ? 42 : 50);
          p.lam = Math.max(-p.mirror, Math.min(p.mirror, p.lam));
        }
        p.lam += p.dir * p.speed * dt;
        p.phi = (p.phi + dt * (p.inner ? 8 : 3.5)) % 360;
        if (p.lam > p.mirror || p.lam < -p.mirror) {
          p.lam = Math.max(-p.mirror, Math.min(p.mirror, p.lam));
          p.dir *= -1;
        }
        const lat = p.lam * Math.PI / 180;
        const aheadLam = Math.max(-p.mirror, Math.min(p.mirror, p.lam + p.dir * 7));
        const alat = aheadLam * Math.PI / 180;
        const ang = tNow * (p.inner ? 0.0002 : 0.00009);
        const pos = spinPole(dipPoint(p.L * Math.cos(lat) ** 2, p.lam, p.phi), ang);
        const ahead = spinPole(dipPoint(p.L * Math.cos(alat) ** 2, aheadLam, p.phi), ang);
        const midLam = (p.lam + aheadLam) / 2;
        const mlat = midLam * Math.PI / 180;
        const mid = spinPole(dipPoint(p.L * Math.cos(mlat) ** 2, midLam, p.phi), ang);
        const q = proj(pos), q2 = proj(ahead), qm = proj(mid);
        if (hidden(q)) continue;
        const X = cx + sc * q.x, Y = cy - sc * q.y;
        const eqBright = 0.55 + 0.45 * (1 - Math.abs(p.lam) / (p.mirror || 1));
        const haze = Math.abs(p.lam) < 16 ? 2.4 : 1;
        ctx.globalAlpha = (p.inner ? 0.05 : 0.035) * eqBright * haze;
        ctx.fillStyle = p.inner ? "rgba(160,190,255,1)" : "rgba(255,120,60,1)";
        ctx.beginPath();
        ctx.arc(X, Y, p.rad * (1.1 + 2.4 * eqBright), 0, 2 * Math.PI);
        ctx.fill();
        ctx.globalAlpha = (p.inner ? 0.55 : 0.38) * eqBright;
        ctx.strokeStyle = p.inner ? "rgba(170,200,255,0.9)" : "rgba(255,140,70,0.85)";
        ctx.lineWidth = p.rad;
        ctx.beginPath();
        ctx.moveTo(X, Y);
        ctx.quadraticCurveTo(cx + sc * qm.x, cy - sc * qm.y, cx + sc * q2.x, cy - sc * q2.y);
        ctx.stroke();
        if (Math.abs(p.lam) < 14) {
          const d1 = proj(spinPole(dipPoint(p.L * Math.cos(lat) ** 2, p.lam, p.phi + 22), ang));
          const d2 = proj(spinPole(dipPoint(p.L * Math.cos(lat) ** 2, p.lam, p.phi + 46), ang));
          if (!hidden(d2)) {
            ctx.globalAlpha = 0.62 * eqBright;
            ctx.lineWidth = Math.max(1.15, p.rad * 0.8);
            ctx.beginPath();
            ctx.moveTo(X, Y);
            if (!hidden(d1)) ctx.quadraticCurveTo(cx + sc * d1.x, cy - sc * d1.y, cx + sc * d2.x, cy - sc * d2.y);
            else ctx.lineTo(cx + sc * d2.x, cy - sc * d2.y);
            ctx.stroke();
          }
        }
        const atMirror = Math.abs(Math.abs(p.lam) - p.mirror) < 3.5;
        ctx.globalAlpha = p.inner ? 0.85 : 0.7;
        ctx.fillStyle = atMirror ? "#ffffff" : (p.inner ? "#d6e4ff" : "#ffd0a8");
        ctx.beginPath();
        ctx.arc(cx + sc * q2.x, cy - sc * q2.y, Math.max(1.5, p.rad), 0, 6.28);
        ctx.fill();
        if (atMirror) {
          const mx = cx + sc * q2.x, my = cy - sc * q2.y;
          const arm = Math.max(3.2, sc * 0.02);
          ctx.strokeStyle = "rgba(255,255,255,0.9)";
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(mx - arm, my);
          ctx.lineTo(mx + arm, my);
          ctx.moveTo(mx, my - arm);
          ctx.lineTo(mx, my + arm);
          ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;
    }
    if (S.showBelts) {
      const flick = 0.28 + 0.18 * Math.sin(tNow / 380);
      ctx.lineCap = "round";
      ctx.lineWidth = Math.max(2.2, sc * 0.018);
      for (const sign of [1, -1]) {
        for (let ph = 0; ph < 360; ph += 20) {
          ctx.beginPath();
          let on = false;
          for (let lam = 66; lam <= 80; lam += 2) {
            const pos = dipPoint(1.05, sign * lam, ph + tNow * 0.003);
            const q = proj(pos);
            const sun = pos[0] * SUN[0] + pos[1] * SUN[1] + pos[2] * SUN[2];
            if (q.z < 0.02 || sun > 0.25) { on = false; continue; }
            const X = cx + sc * q.x, Y = cy - sc * q.y;
            on ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
            on = true;
          }
          ctx.strokeStyle = `rgba(80,255,160,${flick * 0.5})`;
          ctx.lineWidth = Math.max(7, sc * 0.045);
          ctx.stroke();
          ctx.strokeStyle = `rgba(180,255,210,${flick})`;
          ctx.lineWidth = Math.max(1.3, sc * 0.008);
          ctx.stroke();
          for (const lam of [70, 76]) {
            ctx.beginPath();
            let ray = false;
            for (let rr = 1.02; rr <= 1.09; rr += 0.015) {
              const pos = dipPoint(rr, sign * lam, ph + tNow * 0.003);
              const q = proj(pos);
              const sun = pos[0] * SUN[0] + pos[1] * SUN[1] + pos[2] * SUN[2];
              if (q.z < 0.02 || sun > 0.25) { ray = false; continue; }
              const X = cx + sc * q.x, Y = cy - sc * q.y;
              ray ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
              ray = true;
            }
            ctx.strokeStyle = `rgba(210,255,230,${Math.min(0.95, flick * 1.15)})`;
            ctx.lineWidth = Math.max(2.4, sc * 0.014);
            ctx.stroke();
          }
        }
      }
      ctx.lineCap = "butt";
      ctx.lineWidth = Math.max(1.6, sc * 0.012);
      for (const sign of [1, -1]) {
        for (let ph = 10; ph < 360; ph += 28) {
          ctx.beginPath();
          let on = false;
          for (let lam = 70; lam <= 82; lam += 2) {
            const pos = dipPoint(1.12, sign * lam, ph + tNow * 0.002);
            const q = proj(pos);
            const sun = pos[0] * SUN[0] + pos[1] * SUN[1] + pos[2] * SUN[2];
            if (q.z < 0.02 || sun > 0.2) { on = false; continue; }
            const X = cx + sc * q.x, Y = cy - sc * q.y;
            on ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
            on = true;
          }
          ctx.strokeStyle = `rgba(180,120,255,${flick * 0.42})`;
          ctx.lineWidth = Math.max(6, sc * 0.036);
          ctx.stroke();
          ctx.strokeStyle = `rgba(210,170,255,${flick * 0.75})`;
          ctx.lineWidth = Math.max(1.1, sc * 0.007);
          ctx.stroke();
          ctx.beginPath();
          let ray = false;
          for (let rr = 1.08; rr <= 1.16; rr += 0.02) {
            const pos = dipPoint(rr, sign * 76, ph + tNow * 0.002);
            const q = proj(pos);
            const sun = pos[0] * SUN[0] + pos[1] * SUN[1] + pos[2] * SUN[2];
            if (q.z < 0.02 || sun > 0.2) { ray = false; continue; }
            const X = cx + sc * q.x, Y = cy - sc * q.y;
            ray ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
            ray = true;
          }
          ctx.strokeStyle = `rgba(230,210,255,${flick * 0.7})`;
          ctx.lineWidth = 0.7;
          ctx.stroke();
        }
      }
      ctx.lineCap = "butt";
    }
    ctx.font = "11px sans-serif"; ctx.textAlign = "left";
    for (const rc of [1, 4, 12]) {
      const r = Math.sqrt(RC_EQ * Math.cos(55*Math.PI/180)**4 / rc);
      const lab = proj(dipPoint(r, 55, 210));
      if (lab.z > 0) {
        ctx.fillStyle = "rgba(200,216,232,0.55)";
        ctx.fillText(`Rc=${rc} GV`, cx + sc*lab.x + 5, cy - sc*lab.y);
      }
    }
    if (S.showBelts) {
      [[1.7, 0.0002, "170,196,255", 0.28], [4.4, 0.00009, "255,160,100", 0.55]].forEach(([L, w, rgb, half]) => {
        for (const dL of [-half, 0, half]) {
          ctx.strokeStyle = `rgba(${rgb},${dL === 0 ? 0.72 : 0.32})`;
          ctx.lineWidth = dL === 0 ? Math.max(2.6, sc * 0.018) : Math.max(1.1, sc * 0.008);
          ctx.beginPath();
          let on = false;
          for (let ph = 0; ph <= 360; ph += 8) {
            const q = proj(spinPole(dipPoint(L + dL, 0, ph), tNow * w));
            if (hidden(q)) { on = false; continue; }
            const X = cx + sc * q.x, Y = cy - sc * q.y;
            on ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
            on = true;
          }
          ctx.stroke();
        }
        ctx.fillStyle = `rgba(${rgb},0.9)`;
        ctx.lineWidth = Math.max(1.6, sc * 0.012);
        for (let k = 0; k < 12; k++) {
          const ph = (k * 30 + tNow * 0.025) % 360;
          const knot = proj(spinPole(dipPoint(L, 0, ph), tNow * w));
          const tail = proj(spinPole(dipPoint(L, 0, ph - 28), tNow * w));
          if (!hidden(knot) && !hidden(tail)) {
            ctx.strokeStyle = `rgba(${rgb},0.85)`;
            ctx.beginPath();
            ctx.moveTo(cx + sc * tail.x, cy - sc * tail.y);
            ctx.lineTo(cx + sc * knot.x, cy - sc * knot.y);
            ctx.stroke();
          }
          if (hidden(knot)) continue;
          ctx.beginPath();
          ctx.arc(cx + sc * knot.x, cy - sc * knot.y, Math.max(2.2, sc * 0.02), 0, 6.28);
          ctx.fill();
        }
      });
      ctx.setLineDash([4, 7]);
      ctx.strokeStyle = "rgba(190,198,206,0.45)";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      let slotOn = false;
      for (let ph = 0; ph <= 360; ph += 6) {
        const q = proj(spinPole(dipPoint(2.85, 0, ph), tNow * 0.00012));
        if (hidden(q)) { slotOn = false; continue; }
        const X = cx + sc * q.x, Y = cy - sc * q.y;
        slotOn ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
        slotOn = true;
      }
      ctx.stroke();
      ctx.setLineDash([]);
      const b1 = proj(dipPoint(2.6, 18, 200)), b2 = proj(dipPoint(6.0, 18, 200));
      const slot = proj(dipPoint(2.85, -12, 40));
      ctx.fillStyle = "rgba(180,190,200,0.7)";
      if (slot.z > 0) ctx.fillText("槽区（示意）", cx + sc * slot.x + 6, cy - sc * slot.y);
      ctx.fillStyle = "rgba(150,170,255,0.85)";
      if (b1.z > 0) ctx.fillText("内辐射带·质子（示意）", cx + sc*b1.x + 6, cy - sc*b1.y);
      ctx.fillStyle = "rgba(255,150,110,0.85)";
      if (b2.z > 0) ctx.fillText("外辐射带·电子（示意）", cx + sc*b2.x + 6, cy - sc*b2.y);
    }

    // 经纬网格（放大时自动加密）
    ctx.strokeStyle = "rgba(120,160,200,0.16)"; ctx.lineWidth = 0.8;
    const gStep = S.view.zoom > 4 ? 15 : 30;
    for (let la = -60; la <= 60; la += gStep) {
      ctx.beginPath(); let f = true;
      for (let lo = 0; lo <= 360; lo += 6) {
        const q = proj(latlon2xyz(la, lo));
        if (q.z < 0) { f = true; continue; }
        const X = cx + sc*q.x, Y = cy - sc*q.y;
        f ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y); f = false;
      }
      ctx.stroke();
    }
    for (let lo = 0; lo < 360; lo += gStep) {
      ctx.beginPath(); let f = true;
      for (let la = -90; la <= 90; la += 6) {
        const q = proj(latlon2xyz(la, lo));
        if (q.z < 0) { f = true; continue; }
        const X = cx + sc*q.x, Y = cy - sc*q.y;
        f ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y); f = false;
      }
      ctx.stroke();
    }

    // 磁轴
    {
      const a = proj(POLE.map(v => -1.18*v)), b = proj(POLE.map(v => 1.18*v));
      ctx.strokeStyle = "rgba(255,210,63,0.45)"; ctx.setLineDash([5,5]); ctx.lineWidth = 1.1;
      ctx.beginPath(); ctx.moveTo(cx + sc*a.x, cy - sc*a.y);
      ctx.lineTo(cx + sc*b.x, cy - sc*b.y); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = "rgba(255,210,63,0.65)";
      ctx.fillText("磁轴", cx + sc*b.x + 6, cy - sc*b.y);
    }
    // 偶极场力线
    ctx.lineWidth = 1;
    for (const fl of FLD) {
      if (fl.L > rmax) continue;
      const inBelt = (fl.L >= 1.3 && fl.L <= 2.6) || (fl.L >= 3 && fl.L <= 6);
      const ang = tNow * (fl.L <= 2.6 ? 0.0002 : 0.00009);
      ctx.beginPath(); let f = true;
      for (const p of fl.seg) {
        const q = proj(spinPole(p, ang));
        if (hidden(q)) { f = true; continue; }
        const X = cx + sc*q.x, Y = cy - sc*q.y;
        f ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y); f = false;
      }
      if (inBelt) {
        ctx.strokeStyle = fl.L <= 2.6 ? "rgba(140,170,255,0.16)" : "rgba(255,140,80,0.14)";
        ctx.lineWidth = Math.max(3.2, sc * 0.012);
        ctx.stroke();
        ctx.strokeStyle = fl.L <= 2.6 ? "rgba(190,210,255,0.7)" : "rgba(255,170,110,0.55)";
        ctx.lineWidth = 1.15;
      } else {
        ctx.strokeStyle = "rgba(70,100,135,0.22)";
        ctx.lineWidth = 0.7;
      }
      ctx.stroke();
      if (inBelt && fl.seg.length > 4) {
        const u = 0.5 + 0.5 * Math.sin(tNow * 0.0016 + fl.L * 2.2);
        const i = Math.min(fl.seg.length - 1, Math.floor(u * (fl.seg.length - 1)));
        const q = proj(spinPole(fl.seg[i], ang));
        const i0 = Math.max(0, i - 3);
        const i1 = Math.min(fl.seg.length - 1, i + 3);
        ctx.strokeStyle = fl.L <= 2.6 ? "rgba(230,238,255,0.9)" : "rgba(255,220,180,0.9)";
        ctx.lineWidth = Math.max(2.6, sc * 0.016);
        ctx.beginPath();
        let gon = false;
        for (let k = i0; k <= i1; k++) {
          const qq = proj(spinPole(fl.seg[k], ang));
          if (hidden(qq)) { gon = false; continue; }
          const X = cx + sc * qq.x, Y = cy - sc * qq.y;
          gon ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
          gon = true;
        }
        ctx.stroke();
        if (!hidden(q)) {
          ctx.fillStyle = fl.L <= 2.6 ? "rgba(230,238,255,0.95)" : "rgba(255,214,170,0.95)";
          ctx.beginPath();
          ctx.arc(cx + sc * q.x, cy - sc * q.y, Math.max(1.8, sc * 0.014), 0, 6.28);
          ctx.fill();
        }
      }
    }
    // SAA 示意
    {
      ctx.strokeStyle = "rgba(255,95,86,0.8)"; ctx.lineWidth = 1.6;
      ctx.beginPath(); let f = true, front = false;
      for (const p of SAA) {
        const q = proj(p);
        if (q.z < 0) { f = true; continue; }
        front = true;
        const X = cx + sc*q.x*1.003, Y = cy - sc*q.y*1.003;
        f ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y); f = false;
      }
      ctx.stroke();
      if (front) {
        const c0 = proj(SAA[0]);
        ctx.fillStyle = "rgba(255,95,86,0.85)";
        ctx.fillText("SAA（示意）", cx + sc*c0.x + 8, cy - sc*c0.y);
      }
    }
    // 粒子
    if (S.p3.length < 110) S.p3.push(spawnP3(rmax));
    for (const pt of S.p3) {
      if (pt.fade > 0.92) {
        const r = Math.hypot(...pt.p);
        const dirIn = pt.p.map(v => -v / r);
        const step = pt.v * dt * (0.5 + S.speed * 0.5);
        pt.p[0] += dirIn[0]*step; pt.p[1] += dirIn[1]*step; pt.p[2] += dirIn[2]*step;
      }
      const rr = Math.hypot(...pt.p);
      if (rr < 1.05 || rcAt(pt.p) > pt.rig || rr > rmax*2.5) {
        pt.fade -= dt * 2.2;
        if (pt.fade <= 0) Object.assign(pt, spawnP3(rmax));
        continue;
      }
      const dirIn = pt.p.map(v => -v / rr);
      const q0 = proj(pt.p), q1 = proj([pt.p[0]+dirIn[0]*0.4, pt.p[1]+dirIn[1]*0.4,
                                        pt.p[2]+dirIn[2]*0.4]);
      if (hidden(q0) && hidden(q1)) continue;
      ctx.globalAlpha = Math.max(0, pt.fade) * 0.9;
      ctx.strokeStyle = rigColor(pt.rig); ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(cx + sc*q0.x, cy - sc*q0.y);
      ctx.lineTo(cx + sc*q1.x, cy - sc*q1.y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    // 太阳方向指示
    {
      const d = Math.min(w, h) * 0.42;
      const sunP = SUN.map(v => v * rmax * 0.95);
      const qs = proj(sunP);
      const dx = qs.x, dy = -qs.y, n = Math.hypot(dx, dy) || 1;
      const ex = cx + dx/n*d, ey = cy + dy/n*d;
      const g2 = ctx.createRadialGradient(ex, ey, 2, ex, ey, 26);
      g2.addColorStop(0, "#ffe58a"); g2.addColorStop(1, "rgba(255,210,63,0)");
      ctx.fillStyle = g2;
      ctx.beginPath(); ctx.arc(ex, ey, 26, 0, 2*Math.PI); ctx.fill();
      ctx.fillStyle = "#ffd23f"; ctx.font = "12px sans-serif";
      ctx.fillText("☀ 太阳方向", ex + 12, ey - 10);
    }

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, sc * 0.99, 0, 6.28);
    ctx.clip();
    ctx.strokeStyle = "rgba(214,232,255,0.85)";
    ctx.lineWidth = 1.7;
    ctx.setLineDash([6, 5]);
    for (const tr of tracks) {
      if (!tr.pts.length) continue;
      ctx.beginPath();
      let on = false;
      const step = Math.max(1, Math.floor(tr.pts.length / 180));
      for (let i = 0; i < tr.pts.length; i += step) {
        const p = tr.pts[i];
        const r = Math.hypot(p[0], p[1], p[2]) || 1;
        const q = proj([p[0] / r, p[1] / r, p[2] / r]);
        if (q.z <= 0) { on = false; continue; }
        const X = cx + sc * q.x, Y = cy - sc * q.y;
        on ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
        on = true;
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.lineWidth = 1.2;
      const tickStep = Math.max(step * 10, 1);
      for (let i = tickStep; i < tr.pts.length - step; i += tickStep) {
        const p = tr.pts[i];
        const r = Math.hypot(p[0], p[1], p[2]) || 1;
        const q = proj([p[0] / r, p[1] / r, p[2] / r]);
        if (q.z <= 0) continue;
        const p2 = tr.pts[Math.max(0, i - step)];
        const r2 = Math.hypot(p2[0], p2[1], p2[2]) || 1;
        const q2 = proj([p2[0] / r2, p2[1] / r2, p2[2] / r2]);
        const dx = q.x - q2.x, dy = q2.y - q.y;
        const nlen = Math.hypot(dx, dy) || 1;
        const X = cx + sc * q.x, Y = cy - sc * q.y;
        ctx.beginPath();
        ctx.moveTo(X + dy / nlen * 5, Y - dx / nlen * 5);
        ctx.lineTo(X - dy / nlen * 5, Y + dx / nlen * 5);
        ctx.stroke();
      }
      ctx.setLineDash([6, 5]);
      ctx.lineWidth = 1.7;
    }
    ctx.setLineDash([]);
    ctx.restore();

    // 轨道 + 卫星
    const period = 70 / S.speed;
    if (S.playing && S.sel < 0) S.frac = (S.frac + dt/period) % 1;
    const lw = S.view.zoom > 3 ? 2.4 : 1.6;
    for (const tr of tracks) {
      if (!tr.pts.length) continue;
      for (let i = 0; i < tr.pts.length - 1; i++) {
        const a = tr.pts[i], b = tr.pts[i+1];
        const qa = proj(a), qb = proj(b);
        if (hidden(qa) && hidden(qb)) continue;
        ctx.strokeStyle = tr.solid ? tr.color : rcColor((a[3]+b[3])/2);
        // keep the rear half of the ring visible: on high orbits it sweeps the
        // whole sky and 35% alpha is nearly invisible on a dark starfield, so
        // use a clearly-visible semi-transparency instead of dropping it.
        ctx.globalAlpha = (qa.z + qb.z)/2 > -0.2 ? 0.95 : 0.6;
        ctx.lineWidth = tr.solid ? 2 : lw;
        ctx.beginPath();
        ctx.moveTo(cx + sc*qa.x, cy - sc*qa.y);
        ctx.lineTo(cx + sc*qb.x, cy - sc*qb.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      const idx = (S.sel >= 0 && !S.cmp.length)
        ? Math.min(S.sel, tr.pts.length-1)
        : Math.floor(S.frac * tr.pts.length) % tr.pts.length;
      const q = proj(tr.pts[idx]);
      // Draw the satellite continuously even behind the limb (semi-transparent),
      // so the loop never appears to "skip" when the craft passes behind Earth.
      const behind = hidden(q);
      const X = cx + sc*q.x, Y = cy - sc*q.y;
      if (S.sel >= 0 && !S.cmp.length) {
        ctx.strokeStyle = "#7ee787"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(X, Y, 11, 0, 2*Math.PI); ctx.stroke();
      }
      ctx.globalAlpha = behind ? 0.4 : 1;
      const gs = Math.max(16, Math.min(34, 8.5 * S.view.zoom));
      let aim = Math.PI / 2;
      if (!behind && !S.cmp.length) {
        const satp = tr.pts[idx];
        const sr0 = Math.hypot(satp[0], satp[1], satp[2]) || 1;
        const surf0 = proj([satp[0] / sr0, satp[1] / sr0, satp[2] / sr0]);
        if (surf0.z > 0) aim = Math.atan2((cy - sc * surf0.y) - Y, (cx + sc * surf0.x) - X);
      }
      ctx.save();
      ctx.translate(X, Y);
      ctx.rotate(aim - Math.PI / 2);
      ctx.fillStyle = "#0a1c36";
      const edge = gs * 0.07;
      ctx.fillRect(-gs * 2.7, -gs * 0.76 + edge, gs * 0.72, gs * 1.24);
      ctx.fillRect(-gs * 1.82, -gs * 0.62 + edge, gs * 0.64, gs * 1.24);
      ctx.fillRect(gs * 1.18, -gs * 0.62 + edge, gs * 0.64, gs * 1.24);
      ctx.fillRect(gs * 1.98, -gs * 0.76 + edge, gs * 0.72, gs * 1.24);
      ctx.fillStyle = "#16345f";
      ctx.fillRect(-gs * 2.7, -gs * 0.76, gs * 0.72, gs * 1.24);
      ctx.fillRect(-gs * 1.82, -gs * 0.62, gs * 0.64, gs * 1.24);
      ctx.fillRect(gs * 1.18, -gs * 0.62, gs * 0.64, gs * 1.24);
      ctx.fillRect(gs * 1.98, -gs * 0.76, gs * 0.72, gs * 1.24);
      ctx.strokeStyle = "rgba(170,210,255,0.75)";
      ctx.lineWidth = 0.6;
      const panels = [
        [-gs * 2.7, -gs * 1.98, -gs * 0.76],
        [-gs * 1.82, -gs * 1.18, -gs * 0.62],
        [gs * 1.18, gs * 1.82, -gs * 0.62],
        [gs * 1.98, gs * 2.7, -gs * 0.76],
      ];
      for (const [x0, x1, y0] of panels) {
        const cols = 4, rows = 6, ph = gs * 1.24;
        for (let i = 0; i < cols; i++) {
          for (let j = 0; j < rows; j++) {
            const shade = 24 + ((i * 2 + j) % 4) * 14;
            ctx.fillStyle = `rgb(${14},${38 + shade * 0.22},${76 + shade})`;
            const xa = x0 + (x1 - x0) * (i + 0.1) / cols;
            const xb = x0 + (x1 - x0) * (i + 0.9) / cols;
            const ya = y0 + ph * (j + 0.1) / rows;
            const yb = y0 + ph * (j + 0.9) / rows;
            ctx.fillRect(xa, ya, xb - xa, yb - ya);
            ctx.fillStyle = "rgba(230,240,255,0.55)";
            ctx.fillRect(xa, ya, Math.max(1, xb - xa), Math.max(1, gs * 0.028));
          }
        }
        ctx.strokeStyle = "rgba(3,6,12,0.92)";
        ctx.lineWidth = Math.max(1.15, gs * 0.055);
        ctx.beginPath();
        for (let i = 1; i < cols; i++) {
          const x = x0 + (x1 - x0) * i / cols;
          ctx.moveTo(x, y0 + 1);
          ctx.lineTo(x, y0 + ph - 1);
        }
        for (let j = 1; j < rows; j++) {
          const y = y0 + ph * j / rows;
          ctx.moveTo(x0 + 1, y);
          ctx.lineTo(x1 - 1, y);
        }
        ctx.stroke();
        ctx.strokeStyle = "rgba(214,222,232,0.75)";
        ctx.lineWidth = Math.max(0.7, gs * 0.045);
        ctx.strokeRect(x0, y0, x1 - x0, ph);
        ctx.strokeStyle = "rgba(214,220,228,0.8)";
        for (const f of [0.34, 0.66]) {
          const x = x0 + (x1 - x0) * f;
          ctx.beginPath();
          ctx.moveTo(x, y0 + gs * 0.06);
          ctx.lineTo(x, y0 + gs * 1.18);
          ctx.stroke();
        }
        ctx.lineWidth = Math.max(0.6, gs * 0.028);
        for (const f of [0.33, 0.66]) {
          const y = y0 + ph * f;
          ctx.beginPath();
          ctx.moveTo(x0 + gs * 0.04, y);
          ctx.lineTo(x1 - gs * 0.04, y);
          ctx.stroke();
        }
        const sheen = Math.sin(tNow / 900) * 0.5 + 0.5;
        const sy = y0 + gs * 1.24 * sheen * 0.78;
        ctx.fillStyle = "rgba(255,255,255,0.22)";
        ctx.fillRect(x0, sy, x1 - x0, gs * 0.11);
        const thick = Math.max(2.4, gs * 0.16);
        ctx.fillStyle = "#07101c";
        ctx.fillRect(x0, y0 + ph, x1 - x0, thick);
        ctx.fillStyle = "rgba(150,190,230,0.45)";
        ctx.fillRect(x0, y0 + ph, x1 - x0, Math.max(1, thick * 0.22));
        const outer = x0 < 0 ? x0 : x1;
        const dir = x0 < 0 ? -1 : 1;
        ctx.fillStyle = "#0c1c34";
        ctx.beginPath();
        ctx.moveTo(outer, y0);
        ctx.lineTo(outer + dir * thick, y0 + thick * 0.3);
        ctx.lineTo(outer + dir * thick, y0 + ph + thick * 0.3);
        ctx.lineTo(outer, y0 + ph);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(170,210,255,0.75)";
      }
      ctx.fillStyle = "#8d96a2";
      ctx.fillRect(-gs * 1.18, -gs * 0.07, gs * 0.76, gs * 0.14);
      ctx.fillRect(gs * 0.42, -gs * 0.07, gs * 0.76, gs * 0.14);
      ctx.fillStyle = "#5c656e";
      ctx.fillRect(-gs * 2.05, -gs * 0.18, gs * 0.14, gs * 0.36);
      ctx.fillRect(-gs * 1.22, -gs * 0.16, gs * 0.12, gs * 0.32);
      ctx.fillRect(gs * 1.1, -gs * 0.16, gs * 0.12, gs * 0.32);
      ctx.fillRect(gs * 1.9, -gs * 0.18, gs * 0.14, gs * 0.36);
      ctx.strokeStyle = "rgba(176,48,42,0.9)";
      ctx.lineWidth = Math.max(0.7, gs * 0.04);
      ctx.beginPath();
      ctx.moveTo(-gs * 1.1, 0);
      ctx.lineTo(-gs * 0.46, 0);
      ctx.moveTo(gs * 0.46, 0);
      ctx.lineTo(gs * 1.1, 0);
      ctx.stroke();
      ctx.fillStyle = "#e4e8ee";
      for (const hx of [-gs * 1.18, gs * 1.18]) {
        ctx.beginPath();
        ctx.arc(hx, 0, Math.max(1.4, gs * 0.08), 0, 6.3);
        ctx.fill();
        ctx.strokeStyle = "#5c646e";
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.moveTo(hx - gs * 0.05, 0);
        ctx.lineTo(hx + gs * 0.05, 0);
        ctx.stroke();
      }
      ctx.fillStyle = "#9aa4ae";
      ctx.fillRect(-gs * 0.42 + edge, -gs * 0.38 + edge, gs * 0.84, gs * 0.76);
      ctx.fillStyle = "#8e99a4";
      ctx.fillRect(-gs * 0.42, gs * 0.38, gs * 0.84, Math.max(2.2, gs * 0.14));
      ctx.fillStyle = "#d5dee6";
      ctx.fillRect(-gs * 0.42, -gs * 0.38, gs * 0.84, gs * 0.76);
      ctx.fillStyle = "#9aa6b0";
      ctx.beginPath();
      ctx.moveTo(gs * 0.42, -gs * 0.38);
      ctx.lineTo(gs * 0.56, -gs * 0.3);
      ctx.lineTo(gs * 0.56, gs * 0.46);
      ctx.lineTo(gs * 0.42, gs * 0.38);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "rgba(90,104,118,0.85)";
      ctx.lineWidth = Math.max(0.6, gs * 0.03);
      for (let i = 0; i < 5; i++) {
        const x = -gs * 0.3 + i * gs * 0.14;
        ctx.beginPath();
        ctx.moveTo(x, -gs * 0.3);
        ctx.lineTo(x, gs * 0.28);
        ctx.stroke();
      }
      ctx.fillStyle = "#c6a15a";
      ctx.fillRect(-gs * 0.38, -gs * 0.06, gs * 0.76, gs * 0.05);
      ctx.fillStyle = "rgba(198,161,90,0.65)";
      ctx.fillRect(-gs * 0.38, -gs * 0.2, gs * 0.76, gs * 0.025);
      ctx.fillRect(-gs * 0.38, gs * 0.12, gs * 0.76, gs * 0.025);
      ctx.fillStyle = "#1a1e24";
      ctx.fillRect(gs * 0.16, -gs * 0.34, gs * 0.18, gs * 0.14);
      ctx.fillStyle = "#7ec8ff";
      ctx.fillRect(gs * 0.2, -gs * 0.3, gs * 0.07, gs * 0.05);
      ctx.strokeStyle = "rgba(220,226,232,0.9)";
      ctx.lineWidth = 0.8;
      ctx.fillStyle = "#c5d0dc";
      ctx.beginPath();
      ctx.ellipse(0, -gs * 0.62, gs * 0.22, gs * 0.09, 0, 0, 6.28);
      ctx.fill();
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, -gs * 0.62);
      ctx.lineTo(0, -gs * 0.78);
      ctx.stroke();
      ctx.fillStyle = "#e8edf2";
      ctx.beginPath();
      ctx.arc(0, -gs * 0.8, Math.max(1.3, gs * 0.05), 0, 6.28);
      ctx.fill();
      ctx.strokeStyle = "rgba(212,175,90,0.95)";
      ctx.lineWidth = Math.max(0.7, gs * 0.045);
      ctx.beginPath();
      ctx.moveTo(-gs * 0.35, gs * 0.4);
      ctx.lineTo(gs * 0.35, gs * 0.4);
      ctx.moveTo(0, gs * 0.36);
      ctx.lineTo(0, gs * 0.42);
      ctx.stroke();
      ctx.fillStyle = "#5c6874";
      [[-0.78, -0.36], [-0.16, 0.16], [0.36, 0.78]].forEach(([u0, u1]) => {
        ctx.fillRect(gs * u0 + gs * 0.04, gs * 0.5, gs * (u1 - u0), gs * 0.72);
      });
      [[-0.78, -0.36], [-0.16, 0.16], [0.36, 0.78]].forEach(([u0, u1], pi) => {
        ctx.fillStyle = "#8ea0b4";
        ctx.fillRect(gs * u0, gs * 0.42, gs * (u1 - u0), gs * 0.72);
        for (let row = 0; row < 3; row++) {
          for (let col = 0; col < 2; col++) {
            const phase = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(row * 0.9 + col * 1.1 + pi - tNow / 220));
            const x = gs * (u0 + (u1 - u0) * (col + 0.16) / 2);
            const y = gs * (0.46 + row * 0.22);
            ctx.fillStyle = `rgba(220,238,255,${phase})`;
            ctx.fillRect(x, y, gs * (u1 - u0) * 0.28, gs * 0.14);
          }
        }
      });
      ctx.restore();
      if (!behind && S.view.zoom > 1.6) {
        ctx.fillStyle = "#8b98a5";
        ctx.fillText("SAT", X + gs * 2.6, Y + 3);
      }
      if (!behind && !S.cmp.length) {
        const sat = tr.pts[idx];
        const sr = Math.hypot(sat[0], sat[1], sat[2]) || 1;
        const surf = proj([sat[0] / sr, sat[1] / sr, sat[2] / sr]);
        if (surf.z > 0) {
          const hx = cx + sc * surf.x, hy = cy - sc * surf.y;
          const half = Math.max(12, 8 * S.view.zoom);
          const step1 = Math.max(1, Math.floor(tr.pts.length / 90));
          const prev = tr.pts[(idx - step1 + tr.pts.length) % tr.pts.length];
          const pr = Math.hypot(prev[0], prev[1], prev[2]) || 1;
          const pq = proj([prev[0] / pr, prev[1] / pr, prev[2] / pr]);
          const vx = hx - (cx + sc * pq.x), vy = hy - (cy - sc * pq.y);
          const ang = Math.atan2(vy, vx);
          const ax = Math.cos(ang + Math.PI / 2), ay = Math.sin(ang + Math.PI / 2);
          const tipX = X + Math.cos(aim) * gs * 0.92;
          const tipY = Y + Math.sin(aim) * gs * 0.92;
          const px = -Math.sin(aim) * gs * 0.72, py = Math.cos(aim) * gs * 0.72;
          const glow = 0.65 + 0.35 * (0.5 + 0.5 * Math.sin(tNow / 280));
          const nrm = [sat[0] / sr, sat[1] / sr, sat[2] / sr];
          let vx3 = sat[0] - prev[0], vy3 = sat[1] - prev[1], vz3 = sat[2] - prev[2];
          const vd = vx3 * nrm[0] + vy3 * nrm[1] + vz3 * nrm[2];
          vx3 -= nrm[0] * vd; vy3 -= nrm[1] * vd; vz3 -= nrm[2] * vd;
          const alen = Math.hypot(vx3, vy3, vz3) || 1;
          const along3 = [vx3 / alen, vy3 / alen, vz3 / alen];
          const cross3 = [
            nrm[1] * along3[2] - nrm[2] * along3[1],
            nrm[2] * along3[0] - nrm[0] * along3[2],
            nrm[0] * along3[1] - nrm[1] * along3[0],
          ];
          const cw = Math.max(0.1, 18 / Math.max(sc, 1));
          const aw = cw * 0.26;
          const spot = (alongA, crossA) => {
            const p = [
              nrm[0] + along3[0] * alongA + cross3[0] * crossA,
              nrm[1] + along3[1] * alongA + cross3[1] * crossA,
              nrm[2] + along3[2] * alongA + cross3[2] * crossA,
            ];
            const n = Math.hypot(p[0], p[1], p[2]) || 1;
            const q = proj([p[0] / n, p[1] / n, p[2] / n]);
            return [cx + sc * q.x, cy - sc * q.y, q.z];
          };
          const gPos = spot(0, cw), gNeg = spot(0, -cw), gMid = spot(0, 0);
          ctx.save();
          ctx.globalCompositeOperation = "lighter";
          const farBeam = ctx.createLinearGradient(tipX, tipY, gPos[0], gPos[1]);
          farBeam.addColorStop(0, `rgba(255,236,190,${0.32 * glow})`);
          farBeam.addColorStop(1, `rgba(255,160,50,${0.05 * glow})`);
          ctx.fillStyle = farBeam;
          ctx.beginPath();
          ctx.moveTo(tipX + px, tipY + py);
          ctx.lineTo(tipX - px, tipY - py);
          ctx.lineTo(gPos[0], gPos[1]);
          ctx.closePath();
          ctx.fill();
          const nearBeam = ctx.createLinearGradient(tipX, tipY, gNeg[0], gNeg[1]);
          nearBeam.addColorStop(0, `rgba(255,248,224,${0.5 * glow})`);
          nearBeam.addColorStop(1, `rgba(255,230,160,${0.28 * glow})`);
          ctx.fillStyle = nearBeam;
          ctx.beginPath();
          ctx.moveTo(tipX + px, tipY + py);
          ctx.lineTo(tipX - px, tipY - py);
          ctx.lineTo(gNeg[0], gNeg[1]);
          ctx.closePath();
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(tipX + px, tipY + py);
          ctx.lineTo(tipX - px, tipY - py);
          ctx.lineTo(gPos[0], gPos[1]);
          ctx.lineTo(gNeg[0], gNeg[1]);
          ctx.closePath();
          ctx.strokeStyle = "rgba(255,220,140,0.7)";
          ctx.lineWidth = 1.2;
          ctx.stroke();
          ctx.lineWidth = 0.7;
          for (let i = -2; i <= 2; i++) {
            const phase = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(i * 1.2 - tNow / 380));
            ctx.strokeStyle = `rgba(255,236,180,${0.45 * phase * glow})`;
            ctx.beginPath();
            ctx.moveTo(tipX, tipY);
            ctx.lineTo(spot(0, cw * i * 0.42)[0], spot(0, cw * i * 0.42)[1]);
            ctx.stroke();
          }
          const wx = -Math.sin(aim) * 1.8, wy = Math.cos(aim) * 1.8;
          ctx.fillStyle = `rgba(255,248,220,${0.4 * glow})`;
          ctx.beginPath();
          ctx.moveTo(tipX + wx, tipY + wy);
          ctx.lineTo(tipX - wx, tipY - wy);
          ctx.lineTo(gMid[0], gMid[1]);
          ctx.closePath();
          ctx.fill();
          const travel = (tNow / 900) % 1;
          for (let n = 0; n < 2; n++) {
            const u = (travel + n * 0.5) % 1;
            const fade = Math.sin(u * Math.PI);
            ctx.fillStyle = `rgba(255,248,220,${0.55 * fade * glow})`;
            ctx.beginPath();
            ctx.arc(tipX + (gMid[0] - tipX) * u, tipY + (gMid[1] - tipY) * u, 2.2 + 5.5 * u, 0, 6.28);
            ctx.fill();
          }
          ctx.restore();
          const ring = (a0, c0, alongW, crossW) => {
            ctx.beginPath();
            for (let k = 0; k <= 32; k++) {
              const t = (k / 32) * Math.PI * 2;
              const s = spot(a0 + Math.cos(t) * alongW, c0 + Math.sin(t) * crossW);
              k ? ctx.lineTo(s[0], s[1]) : ctx.moveTo(s[0], s[1]);
            }
            ctx.closePath();
          };
          ctx.save();
          ctx.beginPath();
          ctx.arc(cx, cy, sc * 0.995, 0, 6.3);
          ctx.clip();
          ctx.globalCompositeOperation = "lighter";
          for (let k = 6; k >= 1; k--) {
            const step = Math.max(1, Math.floor(tr.pts.length / 90));
            const j = (idx - k * step + tr.pts.length * 8) % tr.pts.length;
            const old = tr.pts[j];
            const orr = Math.hypot(old[0], old[1], old[2]) || 1;
            const onrm = [old[0] / orr, old[1] / orr, old[2] / orr];
            const oq = proj(onrm);
            if (oq.z <= 0) continue;
            ctx.fillStyle = `rgba(255,190,80,${0.12 * (1 - k / 7)})`;
            ctx.beginPath();
            for (let t = 0; t <= 24; t++) {
              const th = (t / 24) * Math.PI * 2;
              const p = [
                onrm[0] + along3[0] * Math.cos(th) * aw * 0.9 + cross3[0] * Math.sin(th) * cw * 0.85,
                onrm[1] + along3[1] * Math.cos(th) * aw * 0.9 + cross3[1] * Math.sin(th) * cw * 0.85,
                onrm[2] + along3[2] * Math.cos(th) * aw * 0.9 + cross3[2] * Math.sin(th) * cw * 0.85,
              ];
              const n = Math.hypot(p[0], p[1], p[2]) || 1;
              const qq = proj([p[0] / n, p[1] / n, p[2] / n]);
              const X = cx + sc * qq.x, Y = cy - sc * qq.y;
              t ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
            }
            ctx.closePath();
            ctx.fill();
          }
          ctx.strokeStyle = `rgba(255,220,150,${0.34 * glow})`;
          ctx.lineWidth = 1;
          for (const s of [0.92, -0.55]) {
            const a = spot(-aw * 1.05, cw * s);
            const b = spot(aw * 1.05, cw * s);
            ctx.beginPath();
            ctx.moveTo(a[0], a[1]);
            ctx.lineTo(b[0], b[1]);
            ctx.stroke();
          }
          const footG = ctx.createLinearGradient(gNeg[0], gNeg[1], gPos[0], gPos[1]);
          footG.addColorStop(0, `rgba(255,248,224,${0.55 * glow})`);
          footG.addColorStop(0.45, `rgba(255,196,80,${0.22 * glow})`);
          footG.addColorStop(1, `rgba(255,150,40,${0.05 * glow})`);
          ctx.fillStyle = footG;
          ring(0, 0, aw * 1.15, cw);
          ctx.fill();
          ctx.strokeStyle = `rgba(255,248,224,${0.8 * glow})`;
          ctx.lineWidth = Math.max(3, sc * 0.014);
          ctx.beginPath();
          for (let k = 0; k <= 18; k++) {
            const t = Math.PI + (k / 18) * Math.PI;
            const s = spot(Math.cos(t) * aw * 1.05, Math.sin(t) * cw * 0.92);
            k ? ctx.lineTo(s[0], s[1]) : ctx.moveTo(s[0], s[1]);
          }
          ctx.stroke();
          ctx.fillStyle = `rgba(255,236,190,${0.34 * glow})`;
          ring(0, -cw * 0.32, aw * 0.7, cw * 0.38);
          ctx.fill();
          ctx.fillStyle = `rgba(255,214,120,${0.4 * glow})`;
          ring(0, 0, aw * 0.72, cw * 0.55);
          ctx.fill();
          ctx.fillStyle = `rgba(255,244,210,${0.55 * glow})`;
          ring(0, 0, aw * 0.28, cw * 0.2);
          ctx.fill();
          ctx.fillStyle = `rgba(255,200,90,${0.16 * glow})`;
          for (const s of [1.15, -1.15, 1.55, -1.55]) {
            ring(0, cw * s, aw * 0.35, cw * (Math.abs(s) > 1.4 ? 0.1 : 0.16));
            ctx.fill();
          }
          ctx.strokeStyle = `rgba(255,244,210,${0.4 * glow})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          const ta = spot(-aw * 0.85, 0), tb = spot(aw * 0.85, 0);
          ctx.moveTo(ta[0], ta[1]);
          ctx.lineTo(tb[0], tb[1]);
          ctx.stroke();
          const gate = ((tNow / 420) % 9) - 4;
          for (let i = -4; i <= 4; i++) {
            const wgt = 1 - Math.abs(i) / 5;
            const hit = Math.exp(-((i - gate) ** 2) / 1.1);
            const span = cw * 0.8 * Math.sqrt(Math.max(0.05, 1 - (i / 5) ** 2));
            const s0 = spot(i * aw * 0.22, span);
            const s1 = spot(i * aw * 0.22, -span);
            const x0 = s0[0], y0 = s0[1];
            const x1 = s1[0], y1 = s1[1];
            const a = (0.08 + 0.32 * wgt + 0.4 * hit) * glow;
            const rg = ctx.createLinearGradient(x0, y0, x1, y1);
            rg.addColorStop(0, `rgba(255,236,180,${(a * 0.35).toFixed(3)})`);
            rg.addColorStop(1, `rgba(255,248,220,${Math.min(1, a * 1.25).toFixed(3)})`);
            ctx.strokeStyle = rg;
            ctx.beginPath();
            ctx.moveTo(x0, y0);
            ctx.lineTo(x1, y1);
            ctx.stroke();
          }
          ctx.fillStyle = `rgba(255,248,220,${0.75 * glow})`;
          for (let i = 0; i < 18; i++) {
            const u = ((i * 0.17 + tNow / 2800) % 1) - 0.5;
            const v = ((i * 0.41) % 1) - 0.5;
            ctx.fillRect(
              hx + Math.cos(ang) * half * u * 0.55 + ax * half * v * 0.85,
              hy + Math.sin(ang) * half * u * 0.55 + ay * half * v * 0.85,
              1.2, 1.2);
          }
          ctx.restore();
        }
      }
      ctx.globalAlpha = 1;
    }
    // 读数
    const mer = (S.result && S.result.series.orbit_track_meridian) || [];
    if (mer.length && !S.cmp.length) {
      const idx = S.sel >= 0 ? Math.min(S.sel, mer.length-1)
                             : Math.floor(S.frac * mer.length) % mer.length;
      const s = mer[idx];
      setReadout(
        `卫星当前位置：磁纬 <b>${s[0].toFixed(1)}°</b>，` +
        `地心距 <b>${s[1].toFixed(3)} R⊕</b>（高度 ${((s[1]-1)*6378).toFixed(1)} km），` +
        `垂直截止刚度 <b>${s[2].toFixed(2)} GV</b> — ` +
        (s[2] < 1 ? "弱屏蔽区，高能粒子可直达" :
         s[2] < 7 ? "中等屏蔽" : "强屏蔽区，仅极高刚度粒子可达") +
        (S.sel >= 0 ? "　（已暂停在选中点，点 ▶ 恢复）" : ""));
    } else if (S.cmp.length) {
      setReadout(`对比模式：${S.cmp.length} 条轨道叠加显示。`);
    }
    ctx.fillStyle = "#6b8aa5"; ctx.font = "11px sans-serif"; ctx.textAlign = "left";
    ctx.fillText("左键拖拽旋转 · 滚轮缩放（以光标为中心） · 右键/Shift 拖拽平移 · 单击轨道点定位 · 双击复位",
                 10, h - 10);
    ctx.fillText(`缩放 ${S.view.zoom.toFixed(1)}×`, 10, h - 28);
    } catch (err) {
      /* 单帧绘制异常不终止渲染循环，避免 3D 视图永久黑屏 */
      if (!Number.isFinite(S.view.zoom) || S.view.zoom <= 0) S.view.zoom = 1;
      if (!Number.isFinite(S.view.panX)) { S.view.panX = 0; S.view.panY = 0; }
      if (!draw._errAt || Date.now() - draw._errAt > 5000) {
        draw._errAt = Date.now();
        if (window.console) console.error("orbit 3d draw:", err);
        const r2 = canvas.getBoundingClientRect();
        if (r2.width > 0) {           // 画布仍有尺寸则恢复默认视角自救
          S.view.yaw = -0.7; S.view.pitch = 0.42;
          S.view.zoom = 1; S.view.panX = 0; S.view.panY = 0;
        }
      }
    }
    requestAnimationFrame(draw);
  }

  /* 交互 */
  function relPos(e) {
    const r = canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }
  canvas.addEventListener("mousedown", e => {
    S.drag = { x: e.clientX, y: e.clientY, moved: 0,
               pan: e.button === 2 || e.shiftKey };
    if (e.button === 2) e.preventDefault();
  });
  window.addEventListener("mousemove", e => {
    if (!S.drag) return;
    const dx = e.clientX - S.drag.x, dy = e.clientY - S.drag.y;
    S.drag.moved += Math.abs(dx) + Math.abs(dy);
    if (S.drag.pan) {
      S.view.panX += dx; S.view.panY += dy;
    } else {
      S.view.yaw += dx * 0.006;
      S.view.pitch = Math.max(-1.35, Math.min(1.35, S.view.pitch + dy * 0.006));
    }
    S.drag.x = e.clientX; S.drag.y = e.clientY;
  });
  window.addEventListener("mouseup", e => {
    if (S.drag && S.drag.moved < 6 && !S.drag.pan && !S.cmp.length) {
      const track = (S.result && S.result.series.orbit_track_xyz_re) || [];
      if (track.length) {
        const [mx, my] = relPos(e);
        const r = canvas.getBoundingClientRect();
        const rmax = Math.max(2.2, Math.max(...track.map(p =>
          Math.hypot(p[0], p[1], p[2])))) * 1.15;
        const ccx = r.width/2 + S.view.panX, ccy = r.height/2 + S.view.panY;
        const sc = Math.min(r.width, r.height) * 0.42 * S.view.zoom / rmax;
        let best = -1, bd = 32*32;
        track.forEach((p, i) => {
          const q = proj(p);
          if (q.z < 0 && Math.hypot(q.x, q.y) < 1) return;
          const d = (ccx + sc*q.x - mx)**2 + (ccy - sc*q.y - my)**2;
          if (d < bd) { bd = d; best = i; }
        });
        if (best >= 0) {
          S.sel = best; S.playing = false;
          if (onSel) onSel(false);
        }
      }
    }
    S.drag = null;
  });
  canvas.addEventListener("contextmenu", e => e.preventDefault());
  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    const [mx, my] = relPos(e);
    const r = canvas.getBoundingClientRect();
    const oldZ = S.view.zoom;
    const nz = Math.max(0.3, Math.min(60, oldZ * (e.deltaY < 0 ? 1.15 : 1/1.15)));
    // 以光标为中心缩放：保持光标下的点不动
    S.view.panX = mx - r.width/2 - (mx - r.width/2 - S.view.panX) * (nz / oldZ);
    S.view.panY = my - r.height/2 - (my - r.height/2 - S.view.panY) * (nz / oldZ);
    S.view.zoom = nz;
  }, { passive: false });
  canvas.addEventListener("dblclick", () => {
    S.view.yaw = -0.7; S.view.pitch = 0.42;
    S.view.zoom = 1; S.view.panX = 0; S.view.panY = 0;
  });

  requestAnimationFrame(t => { S.last = t; draw(t); });

  return {
    setResult(j) { S.result = j; S.sel = -1; },
    setCompare(list) { S.cmp = list || []; },
    clearCompare() { S.cmp = []; },
    setPlaying(v) { S.playing = v; if (v) S.sel = -1; },
    setSpeed(v) { S.speed = v; },
    setAutoRotate(v) { S.view.auto = v; },
    setBelts(v) { S.showBelts = v; },
    resetView() { S.view.yaw = -0.7; S.view.pitch = 0.42; S.view.zoom = 1;
                  S.view.panX = 0; S.view.panY = 0; },
    /* 视角预设：fitR = 画幅中要装下的地心半径（Re） */
    viewPreset(fitR) {
      const tracks = S.cmp.length
        ? S.cmp.map(c => c.track).filter(t => t && t.length)
        : ((S.result && S.result.series && S.result.series.orbit_track_xyz_re) || []).length
          ? [S.result.series.orbit_track_xyz_re]
          : [];
      let rmax = 2.2;
      for (const t of tracks) {
        for (let i = 0; i < t.length; i++) {
          const p = t[i];
          const rr = Math.hypot(p[0], p[1], p[2]);
          if (Number.isFinite(rr) && rr > rmax) rmax = rr;
        }
      }
      rmax *= 1.15;
      const z = rmax / fitR;
      S.view.zoom = Number.isFinite(z) ? Math.max(0.3, Math.min(60, z)) : 1;
      S.view.panX = 0; S.view.panY = 0;
    },
    get state() { return S; }
  };
};
})();

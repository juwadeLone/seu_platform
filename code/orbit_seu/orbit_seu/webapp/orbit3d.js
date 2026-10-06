/* orbit_seu 3D 视图（新版，接口与 engine.js 的 OrbitViewer 相同，可直接替换）
 *
 * 惯性系：地心，z 指北，x 指 t = 0 的本初子午线（与后端 orbit.py 的 gmst0 = 0 一致）。
 * 地球按 ω⊕ 自转；卫星沿后端返回的一圈 ECI 轨迹（series.orbit_track_xyz_re）按时间插值。
 * 磁场：IGRF-13 2020.0。
 *   - 截止刚度：与后端相同的中心倾斜偶极 Størmer 式 Rc = 14.9 · cos⁴λm / r²（GV）。
 *   - 辐射带位置与 SAA：偏心偶极（前两阶系数，Fraser-Smith 1987）与 500 km 高度 |B|。
 * 辐射带、宇宙线粒子只表现位置和运动方式，通量不是模型结果；SEU 闪点按后端算出的
 * 器件平均率做泊松抽样。
 */
(function () {
"use strict";

const OMEGA_E = 7.2921158553e-5;           // rad/s
const RE_KM = 6378.137;
const RC_EQ = 14.9;                         // GV，与后端 constants.py 一致
const IG = { g10: -29404.8, g11: -1450.9, h11: 4652.5,
             g20: -2499.6, g21: 2982.0, h21: -2991.6, g22: 1677.0, h22: -734.6 };

const V = {
  add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
  sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
  mul: (a, k) => [a[0] * k, a[1] * k, a[2] * k],
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
  cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
  len: a => Math.hypot(a[0], a[1], a[2]),
  norm: a => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
};
const rotZ = (p, t) => { const c = Math.cos(t), s = Math.sin(t); return [p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2]]; };
const geo = (latDeg, lonDeg, r = 1) => {
  const la = latDeg * Math.PI / 180, lo = lonDeg * Math.PI / 180;
  return [r * Math.cos(la) * Math.cos(lo), r * Math.cos(la) * Math.sin(lo), r * Math.sin(la)];
};

/* 偶极轴（地理系单位向量），与后端 magnetosphere.py 相同 */
const B0 = Math.hypot(IG.g10, IG.g11, IG.h11);
const POLE = [-IG.g11 / B0, -IG.h11 / B0, -IG.g10 / B0];
const PE1 = V.norm(V.cross([0, 0, 1], POLE));
const PE2 = V.cross(POLE, PE1);
/* 偏心偶极中心偏移（地球半径），约 590 km 指向西太平洋 */
const OFF = (() => {
  const { g10, g11, h11, g20, g21, h21, g22, h22 } = IG, s3 = Math.sqrt(3);
  const B2 = g10 * g10 + g11 * g11 + h11 * h11;
  const L0 = 2 * g10 * g20 + s3 * (g11 * g21 + h11 * h21);
  const L1 = -g11 * g20 + s3 * (g10 * g21 + g11 * g22 + h11 * h22);
  const L2 = -h11 * g20 + s3 * (g10 * h21 - h11 * g22 + g11 * h22);
  const E = (L0 * g10 + L1 * g11 + L2 * h11) / (4 * B2);
  return [(L1 - g11 * E) / (3 * B2), (L2 - h11 * E) / (3 * B2), (L0 - g10 * E) / (3 * B2)];
})();
function dipPoint(L, lam, mu) {            // 偏心偶极磁力线上的点（地固系）
  const r = L * Math.cos(lam) ** 2, h = r * Math.cos(lam);
  return [OFF[0] + h * (Math.cos(mu) * PE1[0] + Math.sin(mu) * PE2[0]) + r * Math.sin(lam) * POLE[0],
          OFF[1] + h * (Math.cos(mu) * PE1[1] + Math.sin(mu) * PE2[1]) + r * Math.sin(lam) * POLE[1],
          OFF[2] + h * (Math.cos(mu) * PE1[2] + Math.sin(mu) * PE2[2]) + r * Math.sin(lam) * POLE[2]];
}
function magOf(pe) {                        // 中心偶极：磁纬、L、截止刚度（与后端一致）
  const r = V.len(pe), s = Math.max(-1, Math.min(1, V.dot(pe, POLE) / r));
  const lam = Math.asin(s), c2 = Math.cos(lam) ** 2;
  return { lam, L: c2 > 1e-9 ? r / c2 : Infinity, rc: RC_EQ * c2 * c2 / (r * r), r };
}
/* 500 km 高度 |B|（IGRF 前两阶），用于画 SAA */
const SAA = (() => {
  const { g10, g11, h11, g20, g21, h21, g22, h22 } = IG;
  const pot = (r, th, ph) => {
    const c = Math.cos(th), s = Math.sin(th), s3 = Math.sqrt(3);
    const t1 = r ** -3 * (g10 * c + (g11 * Math.cos(ph) + h11 * Math.sin(ph)) * s);
    const t2 = r ** -4 * (g20 * (1.5 * c * c - 0.5) + (g21 * Math.cos(ph) + h21 * Math.sin(ph)) * s3 * c * s +
                          (g22 * Math.cos(2 * ph) + h22 * Math.sin(2 * ph)) * s3 / 2 * s * s);
    return t1 + t2;
  };
  const Bmag = (r, th, ph, e = 1e-5) => {
    const br = -(pot(r + e, th, ph) - pot(r - e, th, ph)) / (2 * e);
    const bt = -(pot(r, th + e, ph) - pot(r, th - e, ph)) / (2 * e) / r;
    const bp = -(pot(r, th, ph + e) - pot(r, th, ph - e)) / (2 * e) / (r * Math.sin(th));
    return Math.hypot(br, bt, bp);
  };
  const r = 1 + 500 / 6371.2, cells = [], thr = 21500;
  let min = { b: 1e9 };
  for (let la = -60; la <= 30; la += 3) for (let lo = -180; lo < 180; lo += 3) {
    const b = Bmag(r, (90 - la) * Math.PI / 180, lo * Math.PI / 180);
    if (b < min.b) min = { b, la, lo };
    if (b < thr) cells.push({ la, lo, w: (thr - b) / thr });
  }
  const wMax = Math.max(...cells.map(c => c.w));
  cells.forEach(c => { c.w /= wMax; });
  return { cells, min, thr };
})();
function rcColor(rc) {                      // Rc 低 → 红（弱屏蔽），高 → 蓝
  const t = Math.max(0, Math.min(1, Math.log10(Math.max(rc, 0.1) / 0.1) / Math.log10(150)));
  const stops = [[255, 95, 86], [255, 158, 100], [255, 210, 63], [126, 231, 135], [92, 200, 255], [120, 140, 255]];
  const x = t * (stops.length - 1), i = Math.min(stops.length - 2, Math.floor(x)), f = x - i;
  return stops[i].map((v, k) => Math.round(v + (stops[i + 1][k] - v) * f));
}
const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

window.OrbitViewer = function (canvas, opts) {
  opts = opts || {};
  const ctx = canvas.getContext("2d");
  const readEl = opts.readout || null, onSelect = opts.onSelect || null;
  const ec = document.createElement("canvas"), ectx = ec.getContext("2d");
  const cam = { yaw: -0.7, pitch: 0.42, dist: 7, target: "earth", auto: true };
  const S = {
    result: null, track: null, T: 5700, rate: null, cmp: [],
    playing: true, speed: 1, showBelts: true,
    layers: { belts: true, field: false, gcr: true, saa: true, ground: true },
    view: cam, simT: 0, events: [], nEvents: 0, flashes: []
  };
  let W = 0, H = 0, FOC = 0, CX = 0, CY = 0, lastT = 0, drag = null, lastRead = 0;

  /* 地表贴图 */
  let tex = null, TW = 0, TH = 0;
  const img = new Image();
  img.onload = () => {
    const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
    const g = c.getContext("2d"); g.drawImage(img, 0, 0);
    try { tex = g.getImageData(0, 0, c.width, c.height).data; TW = c.width; TH = c.height; } catch (e) { tex = null; }
  };
  img.src = "/static/earth.jpg";
  const SUN = V.norm([1, 0.25, 0.3]);
  const STARS = (() => { let s = 11; const r = () => (s = (s * 16807) % 2147483647) / 2147483647; const o = [];
    for (let i = 0; i < 500; i++) { const z = 2 * r() - 1, t = 2 * Math.PI * r(), q = Math.sqrt(1 - z * z); o.push([q * Math.cos(t), q * Math.sin(t), z, 0.25 + 0.75 * r()]); } return o; })();

  /* 捕获粒子：沿磁力线弹跳、绕地漂移（质子西漂、电子东漂） */
  const TRAP = (() => { let s = 5; const r = () => (s = (s * 16807) % 2147483647) / 2147483647; const o = [];
    for (let i = 0; i < 1700; i++) {
      const inner = i < 700;
      const L = inner ? 1.25 + 1.2 * r() : 3.0 + 3.6 * r();
      const lamMax = Math.acos(Math.sqrt(Math.min(1, 1.03 / L)));
      o.push({ inner, L, mu: 2 * Math.PI * r(), lm: lamMax * (0.25 + 0.7 * r()), ph: 2 * Math.PI * r(),
               bounce: 2.2 + 2.5 * r(), drift: (inner ? -1 : 1) * (0.05 + 0.05 * r()) });
    } return o; })();
  /* 宇宙线：各有刚度，低于当地截止刚度就被挡回 */
  const GCR = [];
  function spawnGCR(p) {
    const d = V.norm([Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1]);
    const aim = V.mul(V.norm([Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5]), Math.random() * 1.6);
    p.pos = V.mul(d, 7.5);
    p.vel = V.mul(V.norm(V.sub(aim, p.pos)), 2.6);
    p.R = 0.3 * Math.pow(10, Math.random() * 2.2);   // 0.3–50 GV，对数均匀
    p.back = false; p.trail = []; p.hit = 0;
    return p;
  }
  for (let i = 0; i < 70; i++) { const p = spawnGCR({}); p.pos = V.add(p.pos, V.mul(p.vel, -Math.random() * 2.5)); GCR.push(p); }

  /* ---------- 相机与投影 ---------- */
  function satAt(simT) {
    const tr = S.track; if (!tr || tr.length < 2) return null;
    const n = tr.length - 1, ph = ((simT % S.T) + S.T) % S.T / S.T * n, i = Math.floor(ph), f = ph - i;
    const a = tr[i], b = tr[Math.min(n, i + 1)];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }
  function camera(sat) {
    const T = cam.target === "sat" && sat ? sat : [0, 0, 0];
    const cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    const C = V.add(T, V.mul([cp * Math.cos(cam.yaw), cp * Math.sin(cam.yaw), sp], cam.dist));
    const fwd = V.norm(V.sub(T, C)), right = V.norm(V.cross(fwd, [0, 0, 1])), up = V.cross(right, fwd);
    return { C, fwd, right, up };
  }
  function proj(cm, p) {
    const r = V.sub(p, cm.C), z = V.dot(r, cm.fwd);
    if (z < 1e-3) return null;
    return [CX + FOC * V.dot(r, cm.right) / z, CY - FOC * V.dot(r, cm.up) / z, z];
  }
  function hidden(cm, p) {                  // 相机→p 被地球挡住
    const d = V.sub(p, cm.C), L = V.len(d), n = V.mul(d, 1 / L);
    const b = V.dot(cm.C, n), c = V.dot(cm.C, cm.C) - 1, disc = b * b - c;
    if (disc <= 0) return false;
    const t = -b - Math.sqrt(disc);
    return t > 0 && t < L - 1e-6;
  }
  const facing = (cm, p) => V.dot(p, V.sub(cm.C, p)) > 0;

  /* ---------- 地球（光线投射 + 自转） ---------- */
  function renderEarth(cm, theta) {
    const res = drag ? 0.36 : 0.5;
    const w = Math.max(2, Math.floor(W * res)), h = Math.max(2, Math.floor(H * res));
    if (ec.width !== w || ec.height !== h) { ec.width = w; ec.height = h; }
    const im = ectx.createImageData(w, h), px = im.data;
    const fl = FOC * res, cx = CX * res, cy = CY * res, C = cm.C, F = cm.fwd, R = cm.right, U = cm.up;
    const CC = V.dot(C, C) - 1, ct = Math.cos(-theta), st = Math.sin(-theta), IP = 1 / Math.PI;
    for (let j = 0; j < h; j++) {
      const yy = -(j + 0.5 - cy) / fl;
      const bx = F[0] + yy * U[0], by = F[1] + yy * U[1], bz = F[2] + yy * U[2];
      for (let i = 0; i < w; i++) {
        const xx = (i + 0.5 - cx) / fl;
        let dx = bx + xx * R[0], dy = by + xx * R[1], dz = bz + xx * R[2];
        const il = 1 / Math.sqrt(dx * dx + dy * dy + dz * dz); dx *= il; dy *= il; dz *= il;
        const b = C[0] * dx + C[1] * dy + C[2] * dz, disc = b * b - CC, o = (j * w + i) * 4;
        if (disc > 0 && -b - Math.sqrt(disc) > 0) {
          const t = -b - Math.sqrt(disc), x = C[0] + t * dx, y = C[1] + t * dy, z = C[2] + t * dz;
          const lam = x * SUN[0] + y * SUN[1] + z * SUN[2];
          const sh = 0.08 + 0.92 * Math.min(1, Math.max(0, (lam + 0.1) / 0.45));
          const mu = -(dx * x + dy * y + dz * z), haze = Math.pow(1 - Math.max(0, mu), 4) * 0.6 * Math.max(0.2, sh);
          let r = 25, g = 55, bb = 95;
          if (tex) {
            const ex = x * ct - y * st, ey = x * st + y * ct;
            const fu = (Math.atan2(ey, ex) * IP + 1) * 0.5 * TW - 0.5, fv = (0.5 - Math.asin(Math.max(-1, Math.min(1, z))) * IP) * TH - 0.5;
            let x0 = Math.floor(fu), y0 = Math.floor(fv); const ax = fu - x0, ay = fv - y0;
            if (x0 < 0) x0 += TW; const x1 = x0 + 1 >= TW ? 0 : x0 + 1;
            if (y0 < 0) y0 = 0; const y1 = y0 + 1 >= TH ? TH - 1 : y0 + 1;
            const k00 = (y0 * TW + x0) * 4, k10 = (y0 * TW + x1) * 4, k01 = (y1 * TW + x0) * 4, k11 = (y1 * TW + x1) * 4;
            const w00 = (1 - ax) * (1 - ay), w10 = ax * (1 - ay), w01 = (1 - ax) * ay, w11 = ax * ay;
            r = tex[k00] * w00 + tex[k10] * w10 + tex[k01] * w01 + tex[k11] * w11;
            g = tex[k00 + 1] * w00 + tex[k10 + 1] * w10 + tex[k01 + 1] * w01 + tex[k11 + 1] * w11;
            bb = tex[k00 + 2] * w00 + tex[k10 + 2] * w10 + tex[k01 + 2] * w01 + tex[k11 + 2] * w11;
          }
          px[o] = r * sh * (1 - haze) + 110 * haze; px[o + 1] = g * sh * (1 - haze) + 165 * haze;
          px[o + 2] = bb * sh * (1 - haze) + 255 * haze + (1 - sh) * 14; px[o + 3] = 255;
        } else if (b < 0) {
          const dm = Math.sqrt(Math.max(0, CC + 1 - b * b));
          if (dm < 1.06) {
            const qx = C[0] - b * dx, qy = C[1] - b * dy, qz = C[2] - b * dz;
            const lit = Math.max(0.12, Math.min(1, (qx * SUN[0] + qy * SUN[1] + qz * SUN[2]) / dm + 0.35));
            px[o] = 120; px[o + 1] = 175; px[o + 2] = 255; px[o + 3] = Math.min(255, Math.exp(-(dm - 1) / 0.014) * lit * 210);
          } else px[o + 3] = 0;
        } else px[o + 3] = 0;
      }
    }
    ectx.putImageData(im, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(ec, 0, 0, W, H);
  }

  /* ---------- 各图层 ---------- */
  function polyline(cm, pts, col, width, alphaHidden = 0) {
    // pts：惯性系点；被地球挡住的段按 alphaHidden 画（0 = 不画）
    let pen = false, penH = false;
    const vis = new Path2D(), hid = new Path2D();
    let prev = null;
    for (const p of pts) {
      const q = proj(cm, p);
      if (!q) { pen = penH = false; prev = null; continue; }
      const h = hidden(cm, p);
      if (!h) { if (pen && prev) vis.lineTo(q[0], q[1]); else vis.moveTo(q[0], q[1]); pen = true; penH = false; }
      else { if (penH && prev) hid.lineTo(q[0], q[1]); else hid.moveTo(q[0], q[1]); penH = true; pen = false; }
      prev = q;
    }
    ctx.lineWidth = width;
    if (alphaHidden > 0) { ctx.strokeStyle = col.replace(/[\d.]+\)$/, `${alphaHidden})`); ctx.stroke(hid); }
    ctx.strokeStyle = col; ctx.stroke(vis);
  }
  function drawSAA(cm, theta) {
    for (const c of SAA.cells) {
      const q = [[c.la - 1.5, c.lo - 1.5], [c.la - 1.5, c.lo + 1.5], [c.la + 1.5, c.lo + 1.5], [c.la + 1.5, c.lo - 1.5]]
        .map(([la, lo]) => rotZ(geo(la, lo, 1.004), theta));
      if (!facing(cm, V.mul(V.add(q[0], q[2]), 0.5))) continue;
      const s = q.map(p => proj(cm, p)); if (s.some(x => !x)) continue;
      ctx.beginPath(); s.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath();
      ctx.fillStyle = `rgba(255,70,150,${0.1 + 0.42 * c.w})`; ctx.fill();
    }
    const m = rotZ(geo(SAA.min.la, SAA.min.lo, 1.01), theta);
    if (facing(cm, m)) label(cm, m, "SAA", "#ff9ccf", 8, -8, "bold 12px");
  }
  function drawField(cm, theta, Ls, n, col, width) {
    for (const L of Ls) for (let k = 0; k < n; k++) {
      const mu = k / n * 2 * Math.PI, lm = Math.acos(Math.sqrt(Math.min(1, 1.0 / L))), pts = [];
      for (let i = 0; i <= 40; i++) {
        const p = dipPoint(L, -lm + 2 * lm * i / 40, mu);
        if (V.len(p) >= 1.0) pts.push(rotZ(p, theta));
      }
      polyline(cm, pts, col, width);
    }
  }
  function drawTrapped(cm, theta, tv) {
    for (const p of TRAP) {
      const lam = p.lm * Math.sin(p.ph + tv * p.bounce), mu = p.mu + tv * p.drift;
      const pe = dipPoint(p.L, lam, mu);
      if (V.len(pe) < 1.01) continue;
      const w = rotZ(pe, theta);
      if (hidden(cm, w)) continue;
      const q = proj(cm, w); if (!q) continue;
      ctx.fillStyle = p.inner ? "rgba(255,140,90,.7)" : "rgba(120,190,255,.6)";
      ctx.fillRect(q[0] - 0.9, q[1] - 0.9, 1.8, 1.8);
    }
  }
  function stepGCR(dt, theta) {
    for (const p of GCR) {
      p.trail.push(p.pos); if (p.trail.length > 7) p.trail.shift();
      p.pos = V.add(p.pos, V.mul(p.vel, dt));
      const r = V.len(p.pos);
      if (!p.back && r < 5) {
        const m = magOf(rotZ(p.pos, -theta));
        if (p.R < m.rc) {                              // 刚度不够：被挡回
          const n = V.mul(p.pos, 1 / r);
          p.vel = V.sub(p.vel, V.mul(n, 2 * V.dot(p.vel, n)));
          p.back = true;
        }
      }
      if (r < 1.0) { p.hit = 1; spawnGCR(p); continue; }
      if (r > 8 && V.dot(p.pos, p.vel) > 0) spawnGCR(p);
    }
  }
  function drawGCR(cm) {
    for (const p of GCR) {
      if (p.trail.length < 2) continue;
      const col = p.R > 15 ? [200, 220, 255] : p.R > 4 ? [255, 250, 230] : p.R > 1 ? [255, 214, 90] : [255, 150, 80];
      const pts = p.trail.concat([p.pos]);
      if (pts.some(x => hidden(cm, x))) continue;
      const s = pts.map(x => proj(cm, x)); if (s.some(x => !x)) continue;
      ctx.strokeStyle = rgba(col, p.back ? 0.35 : 0.85); ctx.lineWidth = p.back ? 1 : 1.4;
      ctx.beginPath(); s.forEach((q, k) => k ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])); ctx.stroke();
    }
  }
  function label(cm, p, text, col, dx = 6, dy = -6, font = "12px") {
    const q = proj(cm, p); if (!q || q[0] < -60 || q[0] > W + 60 || q[1] < -20 || q[1] > H + 20) return;
    ctx.font = `${font} "Microsoft YaHei",sans-serif`;
    ctx.lineWidth = 3; ctx.strokeStyle = "rgba(4,7,13,.85)"; ctx.strokeText(text, q[0] + dx, q[1] + dy);
    ctx.fillStyle = col; ctx.fillText(text, q[0] + dx, q[1] + dy);
  }
  function drawOrbit(cm, theta, tr, colorBy, col, width) {
    const n = tr.length;
    for (let i = 0; i < n - 1; i++) {
      const a = tr[i], b = tr[i + 1], m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
      const qa = proj(cm, a), qb = proj(cm, b); if (!qa || !qb) continue;
      const hid = hidden(cm, m);
      const c = colorBy ? rcColor(magOf(rotZ(m, -theta)).rc) : col;
      ctx.strokeStyle = rgba(c, hid ? 0.18 : 0.95); ctx.lineWidth = hid ? 1 : width;
      ctx.beginPath(); ctx.moveTo(qa[0], qa[1]); ctx.lineTo(qb[0], qb[1]); ctx.stroke();
    }
  }
  function drawGround(cm, theta) {             // 最近一圈的星下点轨迹
    const pts = [], N = 90;
    for (let k = N; k >= 0; k--) {
      const t = S.simT - S.T * k / N, p = satAt(t); if (!p) return;
      const pe = V.norm(rotZ(p, -OMEGA_E * t));   // 当时的地固系星下点
      pts.push(rotZ(V.mul(pe, 1.003), theta));
    }
    const vis = [];
    for (const p of pts) vis.push(facing(cm, p) ? p : null);
    ctx.setLineDash([5, 4]); ctx.strokeStyle = "rgba(230,240,255,.55)"; ctx.lineWidth = 1.2; ctx.beginPath();
    let pen = false;
    for (const p of vis) { const q = p && proj(cm, p); if (!q) { pen = false; continue; } if (pen) ctx.lineTo(q[0], q[1]); else { ctx.moveTo(q[0], q[1]); pen = true; } }
    ctx.stroke(); ctx.setLineDash([]);
  }
  function drawSat(cm, sat, tv) {
    if (hidden(cm, sat)) return;
    const q = proj(cm, sat); if (!q) return;
    const vdir = V.norm(V.sub(satAt(S.simT + S.T / 200), sat));
    const side = V.norm(V.cross(vdir, sat));
    const wing = s => proj(cm, V.add(sat, V.mul(side, s * 0.05 * Math.min(1, cam.dist / 3))));
    const a = wing(-1), b = wing(1);
    if (a && b) { ctx.strokeStyle = "#6fa8ff"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
    ctx.fillStyle = "#ffd27a"; ctx.fillRect(q[0] - 3, q[1] - 3, 6, 6);
    for (const f of S.flashes) {
      const age = tv - f; if (age > 0.9) continue;
      ctx.strokeStyle = `rgba(255,95,86,${1 - age / 0.9})`; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(q[0], q[1], 6 + 28 * age, 0, 6.3); ctx.stroke();
    }
    label(cm, sat, "卫星", "#ffe2a6", 8, -8);
  }

  /* ---------- 主循环 ---------- */
  function frame(ts) {
    const tv = ts / 1000, dt = lastT ? Math.min(0.05, tv - lastT) : 0; lastT = tv;
    const rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    W = Math.max(2, rect.width); H = Math.max(2, rect.height);
    const bw = Math.round(W * dpr), bh = Math.round(H * dpr);
    if (canvas.width !== bw || canvas.height !== bh) { canvas.width = bw; canvas.height = bh; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    FOC = H / (2 * Math.tan(20 * Math.PI / 180)); CX = W / 2; CY = H / 2;

    const k = S.T / 30 * S.speed;                        // 仿真秒 / 画面秒：一圈约 30 s
    if (S.playing && S.track) {
      S.simT += dt * k;
      if (S.rate) {                                      // 泊松抽样：按器件平均率
        const mu = S.rate * dt * k;
        let n = 0, p = Math.exp(-mu), u = Math.random(), cum = p;
        while (u > cum && n < 50) { n++; p *= mu / n; cum += p; }
        for (let i = 0; i < n; i++) S.flashes.push(tv + i * 0.05);
        S.nEvents += n;
      }
    }
    S.flashes = S.flashes.filter(f => tv - f < 1);
    if (cam.auto && !drag) cam.yaw += dt * 0.06;
    const theta = OMEGA_E * S.simT;
    const sat = satAt(S.simT);
    const cm = camera(sat);

    ctx.fillStyle = "#03050a"; ctx.fillRect(0, 0, W, H);
    for (const s of STARS) {
      const z = V.dot(s, cm.fwd); if (z <= 0) continue;
      const x = CX + FOC * V.dot(s, cm.right) / z, y = CY - FOC * V.dot(s, cm.up) / z;
      if (x < 0 || x > W || y < 0 || y > H) continue;
      ctx.fillStyle = `rgba(220,232,255,${s[3] * 0.75})`; ctx.fillRect(x, y, 1.2, 1.2);
    }
    renderEarth(cm, theta);
    if (S.layers.saa) drawSAA(cm, theta);
    if (S.layers.ground && S.track) drawGround(cm, theta);
    if (S.layers.field) drawField(cm, theta, [1.5, 2.5, 4, 6.6], 8, "rgba(170,200,255,.28)", 1);
    if (S.showBelts) {
      drawTrapped(cm, theta, tv);
    }
    if (S.layers.gcr) { stepGCR(dt, theta); drawGCR(cm); }
    for (const c of S.cmp) if (c.track && c.track.length > 1) {
      drawOrbit(cm, theta, c.track, false, c.rgb || [200, 200, 200], 1.5);
      label(cm, c.track[0], c.label, c.color || "#ccc", 6, -4, "11px");
    }
    if (S.track) { drawOrbit(cm, theta, S.track, true, null, 2.6); if (sat) drawSat(cm, sat, tv); }
    if (S.showBelts && cam.dist > 2.5) {
      label(cm, rotZ(dipPoint(1.8, 0, 0.6), theta), "内带（质子）", "#ffb08a", 6, 0, "11px");
      label(cm, rotZ(dipPoint(4.6, 0, 0.6), theta), "外带（电子）", "#9fd0ff", 6, 0, "11px");
    }
    if (sat && readEl && tv - lastRead > 0.2) { lastRead = tv; readout(sat, theta); }
    requestAnimationFrame(frame);
  }
  function readout(sat, theta) {
    const m = magOf(rotZ(sat, -theta));
    const s = Math.floor(S.simT), hh = Math.floor(s / 3600), mm = Math.floor(s / 60) % 60;
    const exp = S.rate ? S.rate * S.simT : null;
    readEl.innerHTML =
      `T+${hh}:${String(mm).padStart(2, "0")} · 高度 <b>${((m.r - 1) * RE_KM).toFixed(0)} km</b> · 磁纬 ${(m.lam * 180 / Math.PI).toFixed(1)}° · ` +
      `L ${m.L.toFixed(2)} · 截止刚度 <b style="color:rgb(${rcColor(m.rc).join(",")})">${m.rc.toFixed(2)} GV</b>` +
      (S.rate ? ` · 已翻转 <b>${S.nEvents}</b> 次（期望 ${exp.toFixed(1)}）` : "") +
      (S.result && S.result.synthetic_environment ? ` · <span style="color:#ffb454">演示谱，非工程数据</span>` : "");
  }

  /* ---------- 交互 ---------- */
  canvas.addEventListener("pointerdown", e => {
    drag = { x: e.clientX, y: e.clientY, yaw: cam.yaw, pitch: cam.pitch, moved: false };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    cam.yaw = drag.yaw - dx * 0.006;
    cam.pitch = Math.max(-1.5, Math.min(1.5, drag.pitch + dy * 0.006));
  });
  canvas.addEventListener("pointerup", e => {
    if (drag && !drag.moved && S.track) pickOrbit(e);
    drag = null;
  });
  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    const lo = cam.target === "sat" ? 0.08 : 1.25;
    cam.dist = Math.max(lo, Math.min(40, cam.dist * Math.exp(e.deltaY * 0.0012)));
  }, { passive: false });
  canvas.addEventListener("dblclick", () => api.resetView());
  function pickOrbit(e) {
    const r = canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    const cm = camera(satAt(S.simT));
    let best = -1, bd = 14 * 14;
    S.track.forEach((p, i) => { const q = proj(cm, p); if (!q) return; const d = (q[0] - x) ** 2 + (q[1] - y) ** 2; if (d < bd) { bd = d; best = i; } });
    if (best < 0) return;
    const n = S.track.length - 1;
    S.simT = Math.floor(S.simT / S.T) * S.T + best / n * S.T;
    S.playing = false;
    if (onSelect) onSelect(false);
  }
  function fitDist(R) { return R * 1.3 / Math.sin(20 * Math.PI / 180); }

  const api = {
    setResult(j) {
      S.result = j;
      S.track = ((j.series || {}).orbit_track_xyz_re || []).map(p => [p[0], p[1], p[2]]);
      S.T = ((j.orbit || {}).period_min || 95) * 60;
      const dev = (j.rates_per_s || {}).total_per_device;
      S.rate = dev === null || dev === undefined ? null : dev;
      S.simT = 0; S.nEvents = 0; S.flashes = [];
      const rmax = Math.max(1.2, ...S.track.map(p => V.len(p)));
      cam.target = "earth"; cam.dist = fitDist(rmax * 1.08);
    },
    setCompare(list) {
      S.cmp = (list || []).map(c => Object.assign({}, c, {
        track: (c.track || []).map(p => [p[0], p[1], p[2]]),
        rgb: (() => { const h = (c.color || "#cccccc").replace("#", ""); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); })()
      }));
    },
    clearCompare() { S.cmp = []; },
    setPlaying(v) { S.playing = !!v; },
    setSpeed(v) { S.speed = +v || 1; },
    setAutoRotate(v) { cam.auto = !!v; },
    setBelts(v) { S.showBelts = !!v; },
    setLayer(name, v) { if (name === "belts") S.showBelts = !!v; else S.layers[name] = !!v; },
    follow(v) { cam.target = v ? "sat" : "earth"; cam.dist = v ? 0.6 : fitDist(Math.max(1.2, ...(S.track || [[1.2, 0, 0]]).map(p => V.len(p))) * 1.08); },
    resetView() { cam.yaw = -0.7; cam.pitch = 0.42; api.follow(false); },
    viewPreset(fitR) { cam.target = "earth"; cam.dist = fitDist(fitR); },
    get state() { return S; }
  };
  requestAnimationFrame(frame);
  return api;
};
})();

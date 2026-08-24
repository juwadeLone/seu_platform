/* 3D chip + ion-track viewer. Occupancy is a bitmap on the die (blue/black). */
(function () {
"use strict";

function hexRgb(h) {
  const n = (h || "#3d7ec9").replace("#", "");
  return [parseInt(n.slice(0, 2), 16), parseInt(n.slice(2, 4), 16),
          parseInt(n.slice(4, 6), 16)];
}

window.ChipStrikeViewer = function (canvas, opts) {
  opts = opts || {};
  const S = {
    layout: null, strike: null,
    view: { yaw: 0.55, pitch: 1.15, zoom: 1, panX: 0, panY: 0 },
    drag: null, hover: -1, lockChip: false,
    x0: 12, y0: 20,
    occ: null, cellAt: null, cells: [],
    colorMode: "stage",
    showBboxes: false,
  };
  const onPick = opts.onPick || null;
  const readout = opts.readout || null;
  const onHover = opts.onHover || null;

  function ctxOf() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const bw = Math.round(w * dpr), bh = Math.round(h * dpr);
    // Height-only resizes used to leave the old backing store; trails piled up
    // at the bottom (ion ray is drawn from off-canvas).
    if (w > 0 && (canvas.width !== bw || canvas.height !== bh)) {
      canvas.width = bw; canvas.height = bh;
    }
    const ctx = canvas.getContext("2d");
    // Identity + device-pixel clear: WebView2 software 2D ignores CSS-space
    // clearRect while a long stroke sits outside the clip.
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return [ctx, w, h];
  }
  function origin() {
    const L = S.layout;
    return [L.ncols / 2, L.nrows / 2, 0];
  }
  function world(x, y, z) {
    const o = origin();
    return [x - o[0], y - o[1], z];
  }
  function proj(p) {
    const v = S.view;
    const cy = Math.cos(v.yaw), sy = Math.sin(v.yaw);
    const x = p[0] * cy - p[1] * sy, y = p[0] * sy + p[1] * cy, z = p[2];
    const cp = Math.cos(v.pitch), sp = Math.sin(v.pitch);
    return { x, y: y * cp - z * sp, z: y * sp + z * cp };
  }
  function screen(q, cx, cy, sc) {
    return [cx + sc * q.x, cy - sc * q.y];
  }

  function paintOcc() {
    if (!S.layout || !S.occ) return;
    const L = S.layout, W = L.ncols, H = L.nrows;
    const unused = hexRgb(L.color_unused || "#14181e");
    const resCols = L.resource_colors || {};
    const stageCols = L.stage_colors || [];
    const yel = [255, 210, 63], red = [255, 95, 86];
    const filt = S.domFilter;
    const cand = new Set(), flip = new Set();
    for (const e of (S.strike && S.strike.candidates) || []) {
      if (filt && !filt.has(e.domain)) continue;
      cand.add(e.unit_id);
    }
    for (const e of (S.strike && S.strike.flipped) || []) {
      if (filt && !filt.has(e.domain)) continue;
      flip.add(e.unit_id);
    }
    const g = S.occ.getContext("2d");
    const img = g.createImageData(W, H);
    const D = img.data;
    for (let i = 0; i < W * H; i++) {
      D[i * 4] = unused[0]; D[i * 4 + 1] = unused[1];
      D[i * 4 + 2] = unused[2]; D[i * 4 + 3] = 255;
    }
    for (const c of S.cells) {
      const x = c[0], y = c[1], uid = c[5];
      if (x < 0 || y < 0 || x >= W || y >= H) continue;
      const o = (y * W + x) * 4;
      let col;
      if (S.colorMode === "resource") {
        col = hexRgb(resCols[c[2]] || L.color_used || "#3d7ec9");
      } else {
        const st = c[7];
        col = (st > 0 && stageCols[st]) ? hexRgb(stageCols[st])
          : unused;
      }
      if (flip.has(uid)) col = red;
      else if (cand.has(uid)) col = yel;
      D[o] = col[0]; D[o + 1] = col[1]; D[o + 2] = col[2]; D[o + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    S.occDirty = false;
  }

  function dieAffine(cx, cy, sc) {
    const L = S.layout;
    const o = screen(proj(world(0, 0, 0.02)), cx, cy, sc);
    const vx = screen(proj(world(L.ncols, 0, 0.02)), cx, cy, sc);
    const vy = screen(proj(world(0, L.nrows, 0.02)), cx, cy, sc);
    return {
      ox: o[0], oy: o[1],
      a: vx[0] - o[0], b: vy[0] - o[0],
      c: vx[1] - o[1], d: vy[1] - o[1],
    };
  }
  function screenToDie(mx, my, cx, cy, sc) {
    const T = dieAffine(cx, cy, sc);
    const px = mx - T.ox, py = my - T.oy;
    const det = T.a * T.d - T.b * T.c;
    if (Math.abs(det) < 1e-8) return null;
    const u = (px * T.d - py * T.b) / det;
    const v = (py * T.a - px * T.c) / det;
    return [u * S.layout.ncols, v * S.layout.nrows];
  }

  function draw() {
    const [ctx, w, h] = ctxOf();
    if (w === 0 || !S.layout) { requestAnimationFrame(draw); return; }
    ctx.fillStyle = "#070b10";
    ctx.fillRect(0, 0, w, h);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, w, h);
    ctx.clip();

    const L = S.layout;
    const rmax = Math.hypot(L.ncols, L.nrows) * 0.55;
    const cx = w / 2 + S.view.panX, cy = h / 2 + S.view.panY;
    const sc = Math.min(w, h) * 0.42 * S.view.zoom / rmax;
    if (S.occDirty) paintOcc();

    const nx = L.ncols, ny = L.nrows;
    const T = dieAffine(cx, cy, sc);
    const dpr = window.devicePixelRatio || 1;
    ctx.save();
    ctx.setTransform(
      dpr * T.a / nx, dpr * T.c / nx,
      dpr * T.b / ny, dpr * T.d / ny,
      dpr * T.ox, dpr * T.oy);
    ctx.imageSmoothingEnabled = false;
    if (S.occ) ctx.drawImage(S.occ, 0, 0);
    ctx.restore();

    const q0 = proj(world(0, 0, 0.02)), q1 = proj(world(nx, 0, 0.02)),
          q2 = proj(world(nx, ny, 0.02)), q3 = proj(world(0, ny, 0.02));
    ctx.beginPath();
    [[q0], [q1], [q2], [q3]].forEach((qq, k) => {
      const P = screen(qq[0], cx, cy, sc);
      k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
    });
    ctx.closePath();
    ctx.strokeStyle = "#3d6b99"; ctx.lineWidth = 1.4; ctx.stroke();

    if (S.showBboxes && L.stage_bboxes) {
      for (const bb of L.stage_bboxes) {
        const pts = [
          screen(proj(world(bb.xmin, bb.ymin, 0.05)), cx, cy, sc),
          screen(proj(world(bb.xmax + 1, bb.ymin, 0.05)), cx, cy, sc),
          screen(proj(world(bb.xmax + 1, bb.ymax + 1, 0.05)), cx, cy, sc),
          screen(proj(world(bb.xmin, bb.ymax + 1, 0.05)), cx, cy, sc),
        ];
        ctx.beginPath();
        pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
        ctx.closePath();
        ctx.strokeStyle = bb.color || "#e8e8e8";
        ctx.lineWidth = 1.6;
        ctx.setLineDash([5, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
        const lab = screen(proj(world(bb.xmin + 1, bb.ymax + 0.2, 0.05)), cx, cy, sc);
        ctx.fillStyle = bb.color || "#e8e8e8";
        ctx.font = "11px sans-serif";
        ctx.fillText("s" + bb.stage, lab[0], lab[1]);
      }
    }

    if (S.hover >= 0 && S.cells[S.hover]) {
      const c = S.cells[S.hover];
      const pts = [
        screen(proj(world(c[0], c[1], 0.04)), cx, cy, sc),
        screen(proj(world(c[0] + 1, c[1], 0.04)), cx, cy, sc),
        screen(proj(world(c[0] + 1, c[1] + 1, 0.04)), cx, cy, sc),
        screen(proj(world(c[0], c[1] + 1, 0.04)), cx, cy, sc),
      ];
      ctx.beginPath();
      pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.5; ctx.stroke();
    }

    if (S.strike) {
      const a = S.strike.a, b = S.strike.b, phi = S.strike.phi_deg * Math.PI / 180;
      const x0 = S.strike.x0, y0 = S.strike.y0, ellZ = 0.06;
      ctx.beginPath();
      for (let k = 0; k <= 64; k++) {
        const t = k / 64 * 2 * Math.PI;
        const u = a * Math.cos(t), v = b * Math.sin(t);
        const px = x0 + u * Math.cos(phi) - v * Math.sin(phi);
        const py = y0 + u * Math.sin(phi) + v * Math.cos(phi);
        const P = screen(proj(world(px, py, ellZ)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "rgba(77,163,255,0.14)"; ctx.fill();
      ctx.strokeStyle = "#4da3ff"; ctx.lineWidth = 2; ctx.stroke();

      const th = S.strike.theta_deg * Math.PI / 180;
      const Lray = Math.max(nx, ny) * 0.45;
      const dx = Math.sin(th) * Math.cos(phi);
      const dy = Math.sin(th) * Math.sin(phi);
      const dz = -Math.cos(th);
      const pHit = world(x0, y0, ellZ);
      const p0 = [pHit[0] - dx * Lray, pHit[1] - dy * Lray, pHit[2] - dz * Lray];
      const A = screen(proj(p0), cx, cy, sc), H = screen(proj(pHit), cx, cy, sc);
      ctx.strokeStyle = "rgba(255,210,63,0.9)"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(H[0], H[1]); ctx.stroke();
      ctx.fillStyle = "#ffd23f";
      ctx.beginPath(); ctx.arc(H[0], H[1], 4, 0, 2 * Math.PI); ctx.fill();
    }

    ctx.restore();
    ctx.fillStyle = "#6b8aa5"; ctx.font = "11px sans-serif"; ctx.textAlign = "left";
    ctx.fillText(S.lockChip
      ? "俯视锁定：左键平移 · 滚轮缩放 · 单击选打击点"
      : "左键旋转 · 右键平移 · 滚轮缩放 · 单击选打击点", 10, h - 12);

    if (readout && S.strike) {
      const s = S.strike;
      const dom = Object.entries(s.by_domain || {})
        .map(([k, v]) => `${k} ${v.flip}/${v.cand}`).join(" · ");
      readout.innerHTML =
        `打击 <b>(${s.x0.toFixed(1)}, ${s.y0.toFixed(1)})</b>　` +
        `核 a=<b>${s.a.toFixed(2)}</b> b=<b>${s.b.toFixed(2)}</b>　` +
        `${s.kernel_model || ""} / ${s.flip_model || ""}　` +
        (s.area_um2 != null ? `A=${Number(s.area_um2).toFixed(3)} µm²　` : "") +
        `覆盖 Site <b>${s.n_sites_covered}</b>　` +
        `候选(域×Site) <b>${s.n_candidates}</b>　翻转 <b>${s.n_flipped}</b>` +
        (s.n_bits_flipped != null ? `（${s.n_bits_flipped} bit）` : "") + `　` +
        `跨级 ${ (s.stages_hit || []).length } [${(s.stages_hit || []).join(",")}]　` +
        `角色 [${(s.roles_hit || []).join(",")}]　` +
        `${s.preview_class}<br><span style="color:#8b98a5">域 翻转/候选：${dom}</span>` +
        ((s.n_candidates === 0 && (s.kernel_model || "anchored") === "anchored")
          ? `<br><span style="color:#ffb454">候选为 0 是预期：anchored 物理核半径 `
            + `${s.radius_um != null ? Number(s.radius_um).toFixed(2) : "~0.96"} µm `
            + `&lt; 1 个 Site 格（UG475 标定 `
            + `${s.rpm_to_um != null ? Number(s.rpm_to_um).toFixed(2) : "22.79"} µm/格），不是崩溃。</span>`
          : "") +
        (s.note ? `<br><span style="color:#8b98a5">${s.note}</span>` : "");
    }
    requestAnimationFrame(draw);
  }

  function relPos(e) {
    const r = canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }
  function pickCell(mx, my) {
    if (!S.layout || !S.cellAt) return -1;
    const r = canvas.getBoundingClientRect();
    const rmax = Math.hypot(S.layout.ncols, S.layout.nrows) * 0.55;
    const cx = r.width / 2 + S.view.panX, cy = r.height / 2 + S.view.panY;
    const sc = Math.min(r.width, r.height) * 0.42 * S.view.zoom / rmax;
    const die = screenToDie(mx, my, cx, cy, sc);
    if (!die) return -1;
    const ix = Math.floor(die[0]), iy = Math.floor(die[1]);
    const hit = S.cellAt.get(ix + "," + iy);
    return hit === undefined ? -1 : hit;
  }

  canvas.addEventListener("mousedown", e => {
    S.drag = { x: e.clientX, y: e.clientY, moved: 0,
               pan: e.button === 2 || e.shiftKey };
    if (e.button === 2) e.preventDefault();
  });
  window.addEventListener("mousemove", e => {
    if (!S.drag) {
      const [mx, my] = relPos(e);
      const i = pickCell(mx, my);
      S.hover = i;
      if (onHover) {
        if (i < 0) onHover(null);
        else {
          const c = S.cells[i];
          onHover({
            site: c[3], rtype: c[2], bels: c[4] + " primitives",
            domains: c[6] || "", used: 1, x: c[0], y: c[1],
            stage: c[7], role: c[8], shared: c[9],
          });
        }
      }
      return;
    }
    const dx = e.clientX - S.drag.x, dy = e.clientY - S.drag.y;
    S.drag.moved += Math.abs(dx) + Math.abs(dy);
    if (S.drag.pan || S.lockChip) { S.view.panX += dx; S.view.panY += dy; }
    else {
      S.view.yaw += dx * 0.006;
      S.view.pitch = Math.max(0.12, Math.min(1.45, S.view.pitch + dy * 0.006));
    }
    S.drag.x = e.clientX; S.drag.y = e.clientY;
  });
  window.addEventListener("mouseup", e => {
    if (S.drag && S.drag.moved < 6 && !S.drag.pan && S.layout) {
      const [mx, my] = relPos(e);
      const r = canvas.getBoundingClientRect();
      const rmax = Math.hypot(S.layout.ncols, S.layout.nrows) * 0.55;
      const cx = r.width / 2 + S.view.panX, cy = r.height / 2 + S.view.panY;
      const sc = Math.min(r.width, r.height) * 0.42 * S.view.zoom / rmax;
      const die = screenToDie(mx, my, cx, cy, sc);
      if (die && die[0] >= 0 && die[1] >= 0 &&
          die[0] < S.layout.ncols && die[1] < S.layout.nrows) {
        S.x0 = die[0]; S.y0 = die[1];
        if (onPick) onPick(S.x0, S.y0);
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
    const nz = Math.max(0.4, Math.min(16, oldZ * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
    S.view.panX = mx - r.width / 2 - (mx - r.width / 2 - S.view.panX) * (nz / oldZ);
    S.view.panY = my - r.height / 2 - (my - r.height / 2 - S.view.panY) * (nz / oldZ);
    S.view.zoom = nz;
  }, { passive: false });
  canvas.addEventListener("dblclick", () => {
    S.view = S.lockChip
      ? { yaw: 0, pitch: 1.35, zoom: 1, panX: 0, panY: 0 }
      : { yaw: 0.55, pitch: 1.15, zoom: 1, panX: 0, panY: 0 };
  });

  requestAnimationFrame(draw);
  return {
    setLayout(j) {
      S.layout = j;
      S.cells = j.cells || [];
      S.cellAt = new Map();
      S.cells.forEach((c, i) => S.cellAt.set(c[0] + "," + c[1], i));
      S.occ = document.createElement("canvas");
      S.occ.width = j.ncols; S.occ.height = j.nrows;
      S.occDirty = true;
    },
    setStrike(j) { S.strike = j; S.occDirty = true; if (j) { S.x0 = j.x0; S.y0 = j.y0; } },
    setColorMode(m) { S.colorMode = m === "resource" ? "resource" : "stage"; S.occDirty = true; },
    setShowBboxes(v) { S.showBboxes = !!v; },
    setDomainFilter(doms) {
      S.domFilter = doms ? new Set(doms) : null;
      S.occDirty = true;
    },
    resetView() {
      S.view = S.lockChip
        ? { yaw: 0, pitch: 1.35, zoom: 1, panX: 0, panY: 0 }
        : { yaw: 0.55, pitch: 1.15, zoom: 1, panX: 0, panY: 0 };
    },
    setLockChip(v) {
      S.lockChip = !!v;
      if (S.lockChip) S.view = { yaw: 0, pitch: 1.35, zoom: S.view.zoom, panX: 0, panY: 0 };
    },
    get xy() { return [S.x0, S.y0]; },
  };
};
})();

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
    colorMode: "resource", focusOn: true, focus: null, anim: null,
    showBboxes: false,
  };
  const onPick = opts.onPick || null;
  const readout = opts.readout || null;
  const onHover = opts.onHover || null;
  const onPhase = opts.onPhase || null;

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
    const mods = L.modules || [];
    const g = S.occ.getContext("2d");
    const img = g.createImageData(W, H);
    const D = img.data;
    for (let i = 0; i < W * H; i++) {
      D[i * 4] = unused[0]; D[i * 4 + 1] = unused[1];
      D[i * 4 + 2] = unused[2]; D[i * 4 + 3] = 255;
    }
    for (const c of S.cells) {
      const x = c[0], y = c[1];
      if (x < 0 || y < 0 || x >= W || y >= H) continue;
      const o = (y * W + x) * 4;
      const col = S.colorMode === "module"
        ? hexRgb((mods[c[10]] || {}).color || L.color_used || "#3d7ec9")
        : hexRgb(resCols[c[2]] || L.color_used || "#3d7ec9");
      D[o] = col[0]; D[o + 1] = col[1]; D[o + 2] = col[2]; D[o + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    S.occDirty = false;
  }

  function dieAffine(cx, cy, sc) {
    const L = S.layout;
    const zTop = Math.max(6, Math.min(L.ncols, L.nrows) * 0.035);
    const o = screen(proj(world(0, 0, zTop)), cx, cy, sc);
    const vx = screen(proj(world(L.ncols, 0, zTop)), cx, cy, sc);
    const vy = screen(proj(world(0, L.nrows, zTop)), cx, cy, sc);
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
    const L = S.layout;
    if (S.focus) {
      const f = S.focus, p = Math.min(1, (performance.now() - f.t0) / f.dur);
      const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      for (const k of ["zoom", "panX", "panY"]) S.view[k] = f.from[k] + (f.to[k] - f.from[k]) * e;
      if (p >= 1) S.focus = null;
    }
    const rmax = Math.hypot(L.ncols, L.nrows) * 0.55;
    const cx = w / 2 + S.view.panX, cy = h / 2 + S.view.panY;
    const sc = Math.min(w, h) * 0.42 * S.view.zoom / rmax;
    if (S.occDirty) { paintOcc(); S.occVer = (S.occVer || 0) + 1; }
    const zTop = Math.max(6, Math.min(L.ncols, L.nrows) * 0.035);
    const dprM = window.devicePixelRatio || 1;
    // 静态场景（板、封装、裸片、Site）只在视角或着色变化时重画；每帧只贴图 + 画打击层
    const key = [w, h, dprM, S.view.yaw, S.view.pitch, S.view.zoom, S.view.panX, S.view.panY, S.occVer].join("|");
    if (key !== S.sceneKey) { drawScene(w, h, cx, cy, sc, dprM); S.sceneKey = key; }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(S.scene, 0, 0);
    ctx.setTransform(dprM, 0, 0, dprM, 0, 0);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, w, h);
    ctx.clip();
    if (S.hover >= 0 && S.cells[S.hover]) {
      const c = S.cells[S.hover];
      const pts = [
        screen(proj(world(c[0], c[1], zTop + 0.2)), cx, cy, sc),
        screen(proj(world(c[0] + 1, c[1], zTop + 0.2)), cx, cy, sc),
        screen(proj(world(c[0] + 1, c[1] + 1, zTop + 0.2)), cx, cy, sc),
        screen(proj(world(c[0], c[1] + 1, zTop + 0.2)), cx, cy, sc),
      ];
      ctx.beginPath();
      pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.5; ctx.stroke();
    }

    drawStrike(ctx, cx, cy, sc, zTop);
    ctx.restore();
    ctx.fillStyle = "#5f7a98"; ctx.font = "11px sans-serif"; ctx.textAlign = "left";
    ctx.fillText("左键旋转 · 右键平移 · 滚轮缩放 · 单击芯片发射", 10, h - 10);
    requestAnimationFrame(draw);
  }

  function drawScene(w, h, cx, cy, sc, dprS) {
    if (!S.scene) S.scene = document.createElement("canvas");
    const bw = Math.round(w * dprS), bh = Math.round(h * dprS);
    if (S.scene.width !== bw || S.scene.height !== bh) { S.scene.width = bw; S.scene.height = bh; }
    const ctx = S.scene.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, bw, bh);
    ctx.setTransform(dprS, 0, 0, dprS, 0, 0);
    const L = S.layout;
    ctx.fillStyle = "#070b10";
    ctx.fillRect(0, 0, w, h);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, w, h);
    ctx.clip();

    const nx = L.ncols, ny = L.nrows;
    const zTop = Math.max(6, Math.min(nx, ny) * 0.035);
    const mx = nx * 0.14, my = ny * 0.16;
    const board = [
      [-mx, -my], [nx + mx, -my], [nx + mx, ny + my], [-mx, ny + my],
    ];
    const boardTop = board.map(([x, y]) => screen(proj(world(x, y, 0)), cx, cy, sc));
    const boardBot = board.map(([x, y]) => screen(proj(world(x, y, -zTop * 0.45)), cx, cy, sc));
    ctx.beginPath();
    boardBot.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#06281e";
    ctx.fill();
    ctx.beginPath();
    boardTop.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#0e4a34";
    ctx.fill();
    ctx.strokeStyle = "rgba(180,220,190,0.35)";
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.save();
    ctx.beginPath();
    boardTop.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.clip();
    ctx.strokeStyle = "rgba(186,228,196,0.38)";
    ctx.lineWidth = 1.1;
    const pitch = Math.max(nx, ny) / 42;
    for (let t = -ny; t <= nx; t += pitch) {
      const a = screen(proj(world(t, -my * 0.15, 0.04)), cx, cy, sc);
      const b = screen(proj(world(t + ny + my * 0.3, ny + my * 0.15, 0.04)), cx, cy, sc);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
    }
    for (let t = 0; t <= nx + ny; t += pitch) {
      const a = screen(proj(world(t, -my * 0.15, 0.04)), cx, cy, sc);
      const b = screen(proj(world(t - ny - my * 0.3, ny + my * 0.15, 0.04)), cx, cy, sc);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
    }
    ctx.restore();
    const holeR = Math.min(nx, ny) * 0.02;
    const holePad = Math.min(nx, ny) * 0.045;
    const holeAt = (x, y) => {
      const ring = (rad, z) => {
        ctx.beginPath();
        for (let k = 0; k <= 16; k++) {
          const t = (k / 16) * Math.PI * 2;
          const P = screen(proj(world(x + Math.cos(t) * rad, y + Math.sin(t) * rad, z)), cx, cy, sc);
          k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
        }
        ctx.closePath();
      };
      ring(holeR * 1.7, 0.08);
      ctx.fillStyle = "#c6a15a";
      ctx.fill();
      ring(holeR, 0.12);
      ctx.fillStyle = "#070b10";
      ctx.fill();
    };
    holeAt(-mx + holePad, -my + holePad);
    holeAt(nx + mx - holePad, -my + holePad);
    holeAt(nx + mx - holePad, ny + my - holePad);
    holeAt(-mx + holePad, ny + my - holePad);
    for (let i = 0; i < 4; i++) {
      const a = boardTop[i], b = boardTop[(i + 1) % 4];
      const c = boardBot[(i + 1) % 4], d = boardBot[i];
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.lineTo(c[0], c[1]); ctx.lineTo(d[0], d[1]);
      ctx.closePath();
      ctx.fillStyle = i % 2 ? "#083528" : "#0a3c2c";
      ctx.fill();
      ctx.strokeStyle = "rgba(198,161,90,0.8)";
      ctx.lineWidth = 1.15;
      for (const t of [0.28, 0.5, 0.72]) {
        ctx.beginPath();
        ctx.moveTo(a[0] + (d[0] - a[0]) * t, a[1] + (d[1] - a[1]) * t);
        ctx.lineTo(b[0] + (c[0] - b[0]) * t, b[1] + (c[1] - b[1]) * t);
        ctx.stroke();
      }
    }
    const holes = [[-mx * 0.55, -my * 0.55], [nx + mx * 0.55, -my * 0.55],
                   [nx + mx * 0.55, ny + my * 0.55], [-mx * 0.55, ny + my * 0.55]];
    const hr = Math.min(nx, ny) * 0.018;
    holes.forEach(([hx, hy]) => {
      ctx.beginPath();
      for (let k = 0; k <= 16; k++) {
        const t = k / 16 * Math.PI * 2;
        const P = screen(proj(world(hx + Math.cos(t) * hr * 1.65, hy + Math.sin(t) * hr * 1.65, 0.18)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.strokeStyle = "rgba(196,192,176,0.85)";
      ctx.lineWidth = 1.6;
      ctx.stroke();
      ctx.beginPath();
      for (let k = 0; k <= 16; k++) {
        const t = k / 16 * Math.PI * 2;
        const P = screen(proj(world(hx + Math.cos(t) * hr, hy + Math.sin(t) * hr, 0.15)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "#05080c";
      ctx.fill();
      ctx.strokeStyle = "rgba(210,190,120,0.7)";
      ctx.stroke();
      ctx.strokeStyle = "rgba(180,170,140,0.8)";
      ctx.lineWidth = 0.8;
      const slot = hr * 0.55;
      [[-slot, 0, slot, 0], [0, -slot, 0, slot]].forEach(([dx0, dy0, dx1, dy1]) => {
        const A = screen(proj(world(hx + dx0, hy + dy0, 0.22)), cx, cy, sc);
        const B = screen(proj(world(hx + dx1, hy + dy1, 0.22)), cx, cy, sc);
        ctx.beginPath();
        ctx.moveTo(A[0], A[1]);
        ctx.lineTo(B[0], B[1]);
        ctx.stroke();
      });
    });
    const fids = [[-mx * 0.45, -my * 0.35], [nx + mx * 0.45, -my * 0.35], [-mx * 0.45, ny * 0.45]];
    const fidR = Math.min(nx, ny) * 0.011;
    fids.forEach(([fx, fy]) => {
      ctx.beginPath();
      for (let k = 0; k <= 16; k++) {
        const t = k / 16 * Math.PI * 2;
        const P = screen(proj(world(fx + Math.cos(t) * fidR * 1.9, fy + Math.sin(t) * fidR * 1.9, 0.12)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "#e2c56a";
      ctx.fill();
      ctx.beginPath();
      for (let k = 0; k <= 16; k++) {
        const t = k / 16 * Math.PI * 2;
        const P = screen(proj(world(fx + Math.cos(t) * fidR * 0.5, fy + Math.sin(t) * fidR * 0.5, 0.16)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "#12100c";
      ctx.fill();
    });
    const padN = 18;
    {
      const bevel = [[-mx * 0.2, ny + my * 0.88], [nx + mx * 0.2, ny + my * 0.88],
                     [nx + mx * 0.15, ny + my], [-mx * 0.15, ny + my]]
        .map(([x, y]) => screen(proj(world(x, y, 0.08)), cx, cy, sc));
      ctx.beginPath();
      bevel.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = "#c4b48a";
      ctx.fill();
    }
    for (let i = 0; i < padN; i++) {
      const u0 = 0.18 + 0.64 * i / padN;
      const u1 = 0.18 + 0.64 * (i + 0.62) / padN;
      const y0 = ny + my * 0.35, y1 = ny + my * 0.82;
      const pad = [[nx * u0, y0], [nx * u1, y0], [nx * u1, y1], [nx * u0, y1]]
        .map(([x, y]) => screen(proj(world(x, y, 0.2)), cx, cy, sc));
      ctx.beginPath();
      pad.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = i % 2 ? "#c6a15a" : "#e6d7a2";
      ctx.fill();
      const lip0 = screen(proj(world(nx * u0, y1, 0.05)), cx, cy, sc);
      const lip1 = screen(proj(world(nx * u1, y1, 0.05)), cx, cy, sc);
      ctx.beginPath();
      ctx.moveTo(pad[3][0], pad[3][1]);
      ctx.lineTo(pad[2][0], pad[2][1]);
      ctx.lineTo(lip1[0], lip1[1]);
      ctx.lineTo(lip0[0], lip0[1]);
      ctx.closePath();
      ctx.fillStyle = i % 2 ? "#8a6430" : "#b49a58";
      ctx.fill();
      const yb0 = ny + my * 0.52, yb1 = ny + my * 0.64;
      const band = [[nx * u0, yb0], [nx * u1, yb0], [nx * u1, yb1], [nx * u0, yb1]]
        .map(([x, y]) => screen(proj(world(x, y, 0.22)), cx, cy, sc));
      ctx.beginPath();
      band.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = "rgba(80,52,18,0.4)";
      ctx.fill();
      ctx.strokeStyle = "rgba(255,246,214,0.75)";
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.moveTo(pad[0][0], pad[0][1]);
      ctx.lineTo(pad[1][0], pad[1][1]);
      ctx.stroke();
    }
    ctx.strokeStyle = "rgba(198,164,96,0.95)";
    ctx.lineWidth = 2.2;
    for (let i = 0; i < padN; i++) {
      const u = 0.18 + 0.64 * (i + 0.31) / padN;
      const jog = nx * 0.012 * (i % 2 ? 1 : -1);
      const a = screen(proj(world(nx * u, ny * 0.98, 0.25)), cx, cy, sc);
      const m = screen(proj(world(nx * u + jog, ny + my * 0.12, 0.25)), cx, cy, sc);
      const b = screen(proj(world(nx * u, ny + my * 0.35, 0.25)), cx, cy, sc);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(m[0], m[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
      ctx.fillStyle = "#e6d7a2";
      ctx.beginPath();
      ctx.arc(a[0], a[1], 2.1, 0, 6.3);
      ctx.fill();
      const vr = Math.min(nx, ny) * 0.0035;
      const vx = nx * u + jog, vy = ny + my * 0.12;
      ctx.beginPath();
      for (let k = 0; k <= 8; k++) {
        const t = k / 8 * Math.PI * 2;
        const P = screen(proj(world(vx + Math.cos(t) * vr, vy + Math.sin(t) * vr, 0.28)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "#c6a15a";
      ctx.fill();
      ctx.beginPath();
      for (let k = 0; k <= 8; k++) {
        const t = k / 8 * Math.PI * 2;
        const P = screen(proj(world(vx + Math.cos(t) * vr * 0.4, vy + Math.sin(t) * vr * 0.4, 0.3)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "#1a140c";
      ctx.fill();
    }
    [[-mx * 0.78, ny * 0.22, -mx * 0.38, ny * 0.22 + Math.min(nx, ny) * 0.045, "#141414"],
     [-mx * 0.78, ny * 0.36, -mx * 0.38, ny * 0.36 + Math.min(nx, ny) * 0.045, "#c8c2b4"],
     [nx + mx * 0.28, ny * 0.18, nx + mx * 0.72, ny * 0.18 + Math.min(nx, ny) * 0.07, "#2a2a2a"]
    ].forEach(([x0, y0, x1, y1, fill]) => {
      const q = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        .map(([x, y]) => screen(proj(world(x, y, 0.35)), cx, cy, sc));
      ctx.beginPath();
      q.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (fill === "#c8c2b4") {
        const capW = (x1 - x0) * 0.16;
        const band = [[x0, y0], [x0 + capW, y0], [x0 + capW, y1], [x0, y1]]
          .map(([x, y]) => screen(proj(world(x, y, 0.4)), cx, cy, sc));
        ctx.beginPath();
        band.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
        ctx.closePath();
        ctx.fillStyle = "#6e675c";
        ctx.fill();
        const px = x1 - (x1 - x0) * 0.28;
        const py = (y0 + y1) / 2;
        const arm = (y1 - y0) * 0.22;
        ctx.strokeStyle = "#3c342c";
        ctx.lineWidth = 1.1;
        const hz = [
          screen(proj(world(px - arm, py, 0.42)), cx, cy, sc),
          screen(proj(world(px + arm, py, 0.42)), cx, cy, sc),
        ];
        const vt = [
          screen(proj(world(px, py - arm, 0.42)), cx, cy, sc),
          screen(proj(world(px, py + arm, 0.42)), cx, cy, sc),
        ];
        ctx.beginPath();
        ctx.moveTo(hz[0][0], hz[0][1]);
        ctx.lineTo(hz[1][0], hz[1][1]);
        ctx.moveTo(vt[0][0], vt[0][1]);
        ctx.lineTo(vt[1][0], vt[1][1]);
        ctx.stroke();
      }
    });
    {
      const x0 = nx * 0.4, x1 = nx * 0.58;
      const y0 = -my * 0.42, y1 = -my * 0.42 + Math.min(nx, ny) * 0.035;
      const body = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        .map(([x, y]) => screen(proj(world(x, y, 0.32)), cx, cy, sc));
      ctx.beginPath();
      body.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = "#d4cbb8";
      ctx.fill();
      const side = [
        screen(proj(world(x0, y1, 0.32)), cx, cy, sc),
        screen(proj(world(x1, y1, 0.32)), cx, cy, sc),
        screen(proj(world(x1, y1, 0.58)), cx, cy, sc),
        screen(proj(world(x0, y1, 0.58)), cx, cy, sc),
      ];
      ctx.beginPath();
      side.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = "#8a8070";
      ctx.fill();
      const top = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        .map(([x, y]) => screen(proj(world(x, y, 0.58)), cx, cy, sc));
      ctx.beginPath();
      top.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = "#efe6d4";
      ctx.fill();
      const ew = (x1 - x0) * 0.14;
      for (const ex of [x0, x1 - ew]) {
        const band = [[ex, y0], [ex + ew, y0], [ex + ew, y1], [ex, y1]]
          .map(([x, y]) => screen(proj(world(x, y, 0.62)), cx, cy, sc));
        ctx.beginPath();
        band.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
        ctx.closePath();
        ctx.fillStyle = "#6a6458";
        ctx.fill();
      }
      ctx.strokeStyle = "rgba(198,164,96,0.9)";
      ctx.lineWidth = 1.1;
      const pa = screen(proj(world((x0 + x1) / 2, y1, 0.3)), cx, cy, sc);
      const pb = screen(proj(world((x0 + x1) / 2, 0, 0.3)), cx, cy, sc);
      ctx.beginPath();
      ctx.moveTo(pa[0], pa[1]);
      ctx.lineTo(pb[0], pb[1]);
      ctx.stroke();
      ctx.fillStyle = "rgba(230,228,210,0.9)";
      ctx.font = "11px sans-serif";
      ctx.fillText("C1", pa[0] + 8, pa[1]);
    }
    const silk = [[-nx * 0.02, -ny * 0.02], [nx * 1.02, -ny * 0.02],
                  [nx * 1.02, ny * 1.02], [-nx * 0.02, ny * 1.02]]
      .map(([x, y]) => screen(proj(world(x, y, 0.2)), cx, cy, sc));
    ctx.beginPath();
    silk.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.strokeStyle = "rgba(230,228,210,0.75)";
    ctx.setLineDash([5, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
    const fr = Math.min(nx, ny) * 0.012;
    [[-nx * 0.06, -ny * 0.06], [nx * 1.06, -ny * 0.06], [nx * 1.06, ny * 1.06], [-nx * 0.06, ny * 1.06]]
      .forEach(([fx, fy]) => {
        ctx.beginPath();
        for (let k = 0; k <= 12; k++) {
          const t = k / 12 * Math.PI * 2;
          const P = screen(proj(world(fx + Math.cos(t) * fr, fy + Math.sin(t) * fr, 0.22)), cx, cy, sc);
          k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
        }
        ctx.closePath();
        ctx.strokeStyle = "rgba(230,228,210,0.8)";
        ctx.lineWidth = 1;
        ctx.stroke();
        const C = screen(proj(world(fx, fy, 0.22)), cx, cy, sc);
        ctx.fillStyle = "rgba(230,228,210,0.9)";
        ctx.fillRect(C[0] - 1.2, C[1] - 1.2, 2.4, 2.4);
      });
    ctx.fillStyle = "rgba(166,132,72,0.85)";
    [[-nx * 0.15, -ny * 0.15, nx * 1.15, -ny * 0.105],
     [-nx * 0.15, ny * 1.105, nx * 1.15, ny * 1.15],
     [-nx * 0.15, -ny * 0.105, -nx * 0.105, ny * 1.105],
     [nx * 1.105, -ny * 0.105, nx * 1.15, ny * 1.105]].forEach(([x0, y0, x1, y1]) => {
      const q = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        .map(([x, y]) => screen(proj(world(x, y, 0.14)), cx, cy, sc));
      ctx.beginPath();
      q.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fill();
    });
    const viaR = Math.min(nx, ny) * 0.005;
    const stitch = [];
    for (let i = 0; i <= 16; i++) {
      const x = nx * i / 16;
      stitch.push([x, -ny * 0.11], [x, ny * 1.11]);
    }
    for (let i = 1; i < 20; i++) {
      const y = ny * i / 20;
      stitch.push([-nx * 0.11, y], [nx * 1.11, y]);
    }
    stitch.forEach(([sx, sy]) => {
      ctx.beginPath();
      for (let k = 0; k <= 8; k++) {
        const t = k / 8 * Math.PI * 2;
        const P = screen(proj(world(sx + Math.cos(t) * viaR, sy + Math.sin(t) * viaR, 0.16)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "#c6a15a";
      ctx.fill();
      ctx.beginPath();
      for (let k = 0; k <= 6; k++) {
        const t = k / 6 * Math.PI * 2;
        const P = screen(proj(world(sx + Math.cos(t) * viaR * 0.38, sy + Math.sin(t) * viaR * 0.38, 0.2)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fillStyle = "#1a140c";
      ctx.fill();
    });
    const open = [[-nx * 0.05, -ny * 0.05], [nx * 1.05, -ny * 0.05],
                  [nx * 1.05, ny * 1.05], [-nx * 0.05, ny * 1.05]]
      .map(([x, y]) => screen(proj(world(x, y, 0.12)), cx, cy, sc));
    ctx.beginPath();
    open.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#083428";
    ctx.fill();
    const ballR = Math.min(nx, ny) * 0.009;
    const step = Math.max(6, Math.round(Math.min(nx, ny) / 42));
    const ballAt = (x, y) => {
      ctx.beginPath();
      for (let k = 0; k <= 8; k++) {
        const t = k / 8 * Math.PI * 2;
        const P = screen(proj(world(x + Math.cos(t) * ballR, y + Math.sin(t) * ballR, zTop * 0.18)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.75)";
      ctx.beginPath();
      for (let k = 0; k <= 6; k++) {
        const t = k / 6 * Math.PI * 2;
        const P = screen(proj(world(
          x + ballR * 0.28 + Math.cos(t) * ballR * 0.28,
          y - ballR * 0.28 + Math.sin(t) * ballR * 0.28,
          zTop * 0.2)), cx, cy, sc);
        k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
      }
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#d4d0c4";
    };
    ctx.fillStyle = "#d4d0c4";
    for (let x = step; x < nx; x += step) {
      ballAt(x, -ny * 0.028);
      ballAt(x, ny + ny * 0.028);
      ballAt(x + step * 0.5, -ny * 0.058);
      ballAt(x + step * 0.5, ny + ny * 0.058);
      ballAt(x, -ny * 0.086);
      ballAt(x, ny + ny * 0.086);
    }
    for (let y = step; y < ny; y += step) {
      ballAt(-nx * 0.028, y);
      ballAt(nx + nx * 0.028, y);
      ballAt(-nx * 0.058, y + step * 0.5);
      ballAt(nx + nx * 0.058, y + step * 0.5);
      ballAt(-nx * 0.086, y);
      ballAt(nx + nx * 0.086, y);
    }
    const pkg = 0.045;
    const pkgTop = [
      [-nx * pkg, -ny * pkg], [nx * (1 + pkg), -ny * pkg],
      [nx * (1 + pkg), ny * (1 + pkg)], [-nx * pkg, ny * (1 + pkg)],
    ].map(([x, y]) => screen(proj(world(x, y, zTop * 0.55)), cx, cy, sc));
    ctx.beginPath();
    pkgTop.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#1c1f24";
    ctx.fill();
    ctx.strokeStyle = "rgba(180,186,196,0.45)";
    ctx.lineWidth = 1;
    ctx.stroke();
    const lip = 0.026;
    const lipTop = [
      [-nx * lip, -ny * lip], [nx * (1 + lip), -ny * lip],
      [nx * (1 + lip), ny * (1 + lip)], [-nx * lip, ny * (1 + lip)],
    ].map(([x, y]) => screen(proj(world(x, y, zTop * 0.66)), cx, cy, sc));
    ctx.beginPath();
    lipTop.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#2c323c";
    ctx.fill();
    const ringAt = (m) => [
      [-nx * m, -ny * m], [nx * (1 + m), -ny * m],
      [nx * (1 + m), ny * (1 + m)], [-nx * m, ny * (1 + m)],
    ].map(([x, y]) => screen(proj(world(x, y, zTop * 0.58)), cx, cy, sc));
    const uOuter = ringAt(0.043);
    const uInner = ringAt(0.03);
    ctx.beginPath();
    uOuter.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    uInner.reverse().forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#6a5438";
    ctx.fill("evenodd");
    const lid = 0.012;
    const lidTop = [
      [-nx * lid, -ny * lid], [nx * (1 + lid), -ny * lid],
      [nx * (1 + lid), ny * (1 + lid)], [-nx * lid, ny * (1 + lid)],
    ].map(([x, y]) => screen(proj(world(x, y, zTop * 0.78)), cx, cy, sc));
    const win = [
      [nx * 0.06, ny * 0.22], [nx * 0.94, ny * 0.22],
      [nx * 0.94, ny * 0.94], [nx * 0.06, ny * 0.94],
    ].map(([x, y]) => screen(proj(world(x, y, zTop * 0.78)), cx, cy, sc));
    ctx.beginPath();
    lidTop.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    [...win].reverse().forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    const lidSheen = ctx.createLinearGradient(lidTop[0][0], lidTop[0][1], lidTop[2][0], lidTop[2][1]);
    lidSheen.addColorStop(0, "#545c6a");
    lidSheen.addColorStop(0.42, "#2c313a");
    lidSheen.addColorStop(1, "#16191e");
    ctx.fillStyle = lidSheen;
    ctx.fill("evenodd");
    ctx.beginPath();
    win.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#10261c";
    ctx.fill();
    ctx.save();
    ctx.beginPath();
    win.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.clip();
    // 窗口内的 Site 点阵/连线被上层不透明的裸片图完全盖住，已删（每帧省数百 ms）
    ctx.restore();
    ctx.beginPath();
    win.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.strokeStyle = "rgba(12,14,18,0.85)";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.strokeStyle = "rgba(190,196,206,0.35)";
    ctx.lineWidth = 0.8;
    ctx.stroke();
    const pr = Math.min(nx, ny) * 0.04;
    ctx.beginPath();
    for (let k = 0; k <= 18; k++) {
      const t = k / 18 * Math.PI * 2;
      const P = screen(proj(world(nx * 0.12 + Math.cos(t) * pr, ny * 0.12 + Math.sin(t) * pr, zTop * 0.82)), cx, cy, sc);
      k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
    }
    ctx.closePath();
    ctx.fillStyle = "#d7c48a";
    ctx.fill();
    ctx.strokeStyle = "#6d5c34";
    ctx.lineWidth = 1;
    ctx.stroke();
    const pin = [
      [-nx * pkg * 0.2, -ny * pkg * 0.2],
      [nx * 0.03, -ny * pkg * 0.15],
      [-nx * pkg * 0.15, ny * 0.03],
    ].map(([x, y]) => screen(proj(world(x, y, zTop * 0.62)), cx, cy, sc));
    ctx.beginPath();
    pin.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();
    ctx.fillStyle = "#c6a15a";
    ctx.fill();
    const ref = screen(proj(world(-nx * 0.08, ny * 0.08, zTop * 0.8)), cx, cy, sc);
    ctx.fillStyle = "rgba(230,228,210,0.9)";
    ctx.font = "12px sans-serif";
    ctx.fillText("U1", ref[0], ref[1]);
    const mark = screen(proj(world(nx * 0.62, ny * 0.18, zTop * 0.82)), cx, cy, sc);
    ctx.fillStyle = "rgba(210,206,190,0.8)";
    ctx.font = "11px sans-serif";
    ctx.fillText("FPGA", mark[0], mark[1]);
    const corners = [
      [0, 0], [nx, 0], [nx, ny], [0, ny],
    ];
    const sideFaces = [];
    for (let i = 0; i < 4; i++) {
      const a = corners[i], b = corners[(i + 1) % 4];
      const pts = [
        world(a[0], a[1], 0), world(b[0], b[1], 0),
        world(b[0], b[1], zTop), world(a[0], a[1], zTop),
      ];
      const qs = pts.map(p => proj(p));
      sideFaces.push({
        z: qs.reduce((s, q) => s + q.z, 0) / 4,
        pts: qs.map(q => screen(q, cx, cy, sc)),
        shade: 0.35 + 0.2 * i,
      });
    }
    sideFaces.sort((u, v) => u.z - v.z);
    for (const f of sideFaces) {
      ctx.beginPath();
      f.pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      const g = Math.round(28 + 40 * f.shade);
      const edge = (t, i0, i1) => [
        f.pts[i0][0] + (f.pts[i1][0] - f.pts[i0][0]) * t,
        f.pts[i0][1] + (f.pts[i1][1] - f.pts[i0][1]) * t,
      ];
      [[0, 0.72, `rgb(${g},${g + 6},${g + 28})`],
       [0.72, 0.88, `rgb(${Math.min(255, g + 70)},${Math.min(255, g + 72)},${Math.min(255, g + 64)})`],
       [0.88, 1, `rgb(${Math.min(255, g + 90)},${g + 55},48)`]].forEach(([t0, t1, col]) => {
        const quad = [edge(t0, 0, 3), edge(t0, 1, 2), edge(t1, 1, 2), edge(t1, 0, 3)];
        ctx.beginPath();
        quad.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
        ctx.closePath();
        ctx.fillStyle = col;
        ctx.fill();
      });
      ctx.beginPath();
      f.pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.strokeStyle = "rgba(160,190,220,0.35)";
      ctx.lineWidth = 1;
      ctx.stroke();
      const layers = [
        [0.3, "rgba(80,110,140,0.55)"],
        [0.72, "rgba(220,226,232,0.75)"],
        [0.88, "rgba(212,186,110,0.8)"],
      ];
      ctx.lineWidth = 0.9;
      for (const [t, col] of layers) {
        const Lx = f.pts[0][0] + (f.pts[3][0] - f.pts[0][0]) * t;
        const Ly = f.pts[0][1] + (f.pts[3][1] - f.pts[0][1]) * t;
        const Rx = f.pts[1][0] + (f.pts[2][0] - f.pts[1][0]) * t;
        const Ry = f.pts[1][1] + (f.pts[2][1] - f.pts[1][1]) * t;
        ctx.strokeStyle = col;
        ctx.beginPath();
        ctx.moveTo(Lx, Ly);
        ctx.lineTo(Rx, Ry);
        ctx.stroke();
      }
    }
    const q0 = proj(world(0, 0, zTop)), q1 = proj(world(nx, 0, zTop)),
          q2 = proj(world(nx, ny, zTop)), q3 = proj(world(0, ny, zTop));
    ctx.beginPath();
    [q0, q1, q2, q3].forEach((qq, k) => {
      const P = screen(qq, cx, cy, sc);
      k ? ctx.lineTo(P[0], P[1]) : ctx.moveTo(P[0], P[1]);
    });
    ctx.closePath();
    ctx.strokeStyle = "rgba(210,230,255,0.55)"; ctx.lineWidth = 1.6; ctx.stroke();

    const T = dieAffine(cx, cy, sc);
    const dpr = window.devicePixelRatio || 1;
    ctx.save();
    ctx.setTransform(
      dpr * T.a / nx, dpr * T.c / nx,
      dpr * T.b / ny, dpr * T.d / ny,
      dpr * T.ox, dpr * T.oy);
    ctx.imageSmoothingEnabled = false;
    if (S.occ) ctx.drawImage(S.occ, 0, 0);
    const wash = ctx.createLinearGradient(0, 0, nx, ny);
    wash.addColorStop(0, "rgba(255,255,255,0.16)");
    wash.addColorStop(0.45, "rgba(0,0,0,0)");
    wash.addColorStop(1, "rgba(0,0,0,0.32)");
    ctx.fillStyle = wash;
    ctx.fillRect(0, 0, nx, ny);
    ctx.strokeStyle = "rgba(212,186,110,0.55)";
    ctx.lineWidth = Math.max(0.35, Math.min(nx, ny) * 0.004);
    ctx.strokeRect(1.2, 1.2, nx - 2.4, ny - 2.4);
    ctx.fillStyle = "rgba(226,197,106,0.8)";
    const padPitch = Math.max(6, Math.round(Math.min(nx, ny) / 48));
    for (let x = padPitch; x < nx - 2; x += padPitch) {
      ctx.fillRect(x, 1.45, 0.7, 0.42);
      ctx.fillRect(x, ny - 1.9, 0.7, 0.42);
    }
    for (let y = padPitch; y < ny - 2; y += padPitch) {
      ctx.fillRect(1.45, y, 0.42, 0.7);
      ctx.fillRect(nx - 1.9, y, 0.42, 0.7);
    }
    const cellEdge = screen(proj(world(1, 0, zTop)), cx, cy, sc);
    const cellOrigin = screen(proj(world(0, 0, zTop)), cx, cy, sc);
    const cellPx = Math.hypot(cellEdge[0] - cellOrigin[0], cellEdge[1] - cellOrigin[1]);
    if (cellPx > 7) {
      const dieTL = screenToDie(0, 0, cx, cy, sc) || [0, 0];
      const dieBR = screenToDie(w, h, cx, cy, sc) || [nx, ny];
      const xLo = Math.max(0, Math.floor(Math.min(dieTL[0], dieBR[0])) - 2);
      const xHi = Math.min(nx, Math.ceil(Math.max(dieTL[0], dieBR[0])) + 2);
      const yLo = Math.max(0, Math.floor(Math.min(dieTL[1], dieBR[1])) - 2);
      const yHi = Math.min(ny, Math.ceil(Math.max(dieTL[1], dieBR[1])) + 2);
      ctx.strokeStyle = "rgba(212,186,110,0.45)";
      ctx.lineWidth = 0.05;
      const yRail0 = Math.ceil(yLo / 8) * 8;
      for (let y = yRail0; y < yHi; y += 8) {
        ctx.beginPath();
        ctx.moveTo(xLo, y + 0.02);
        ctx.lineTo(xHi, y + 0.02);
        ctx.stroke();
      }
      ctx.lineWidth = 0.04;
      for (const c of S.cells) {
        if (c[0] < xLo || c[0] > xHi || c[1] < yLo || c[1] > yHi) continue;
        const x = c[0], y = c[1], kind = c[2];
        ctx.fillStyle = "rgba(6,8,12,0.45)";
        ctx.fillRect(x + 0.04, y + 0.04, 0.74, 0.92);
        ctx.strokeStyle = "rgba(186,196,210,0.5)";
        ctx.strokeRect(x + 0.05, y + 0.05, 0.72, 0.9);
        ctx.fillStyle = "rgba(40,48,58,0.55)";
        ctx.fillRect(x + 0.84, y + 0.06, 0.12, 0.88);
        if (cellPx < 18) {
          ctx.fillStyle = kind === "BRAM" ? "rgba(72,176,96,0.92)"
            : kind === "DSP" ? "rgba(214,146,54,0.92)"
            : "rgba(56,118,176,0.92)";
          ctx.fillRect(x + 0.08, y + 0.1, 0.68, 0.8);
          if (kind === "BRAM") {
            ctx.fillStyle = "rgba(210,255,216,0.7)";
            for (let row = 0; row < 4; row++) ctx.fillRect(x + 0.16, y + 0.2 + row * 0.17, 0.5, 0.07);
          } else if (kind === "DSP") {
            ctx.fillStyle = "rgba(255,214,150,0.85)";
            ctx.fillRect(x + 0.16, y + 0.24, 0.26, 0.52);
            ctx.fillRect(x + 0.48, y + 0.24, 0.18, 0.52);
          } else {
            ctx.fillStyle = "rgba(200,226,255,0.85)";
            ctx.fillRect(x + 0.12, y + 0.16, 0.07, 0.68);
            for (let k = 0; k < 4; k++) ctx.fillRect(x + 0.26, y + 0.18 + k * 0.17, 0.4, 0.09);
          }
        } else if (kind === "BRAM") {
          ctx.fillStyle = "rgba(126,231,135,0.85)";
          const word = Math.floor(performance.now() / 280) % 8;
          for (let row = 0; row < 8; row++) {
            for (let col = 0; col < 5; col++) {
              const alt = (row + col) % 2 ? 0.95 : 0.62;
              ctx.globalAlpha = row === word ? 1 : alt * 0.72;
              ctx.fillRect(x + 0.2 + col * 0.11, y + 0.1 + row * 0.1, 0.09, 0.08);
            }
          }
          ctx.globalAlpha = 1;
          ctx.fillStyle = "rgba(180,255,190,0.95)";
          ctx.fillRect(x + 0.1, y + 0.18, 0.08, 0.22);
          ctx.fillRect(x + 0.1, y + 0.58, 0.08, 0.22);
          ctx.fillStyle = "rgba(230,255,235,0.95)";
          for (let p = 0; p < 3; p++) {
            ctx.fillRect(x + 0.11, y + 0.21 + p * 0.05, 0.02, 0.02);
            ctx.fillRect(x + 0.11, y + 0.61 + p * 0.05, 0.02, 0.02);
          }
          ctx.strokeStyle = "rgba(200,255,210,0.9)";
          ctx.beginPath();
          ctx.moveTo(x + 0.18, y + 0.29);
          ctx.lineTo(x + 0.22, y + 0.29);
          ctx.moveTo(x + 0.18, y + 0.69);
          ctx.lineTo(x + 0.22, y + 0.69);
          ctx.stroke();
          ctx.lineWidth = 0.02;
          ctx.beginPath();
          ctx.moveTo(x + 0.74, y + 0.5);
          ctx.lineTo(x + 0.9, y + 0.5);
          ctx.stroke();
        } else if (kind === "DSP") {
          const st = Math.floor(performance.now() / 360) % 3;
          ctx.fillStyle = st === 0 ? "rgba(255,230,160,1)" : "rgba(255,180,84,0.75)";
          ctx.fillRect(x + 0.14, y + 0.14, 0.4, 0.32);
          ctx.fillStyle = st === 1 ? "rgba(255,245,220,1)" : "rgba(255,214,150,0.7)";
          ctx.fillRect(x + 0.56, y + 0.14, 0.18, 0.32);
          ctx.fillStyle = st === 2 ? "rgba(255,200,110,1)" : "rgba(255,150,60,0.7)";
          ctx.fillRect(x + 0.24, y + 0.52, 0.48, 0.26);
          ctx.strokeStyle = "rgba(80,36,0,0.75)";
          ctx.beginPath();
          ctx.moveTo(x + 0.24, y + 0.28);
          ctx.lineTo(x + 0.42, y + 0.4);
          ctx.moveTo(x + 0.42, y + 0.28);
          ctx.lineTo(x + 0.24, y + 0.4);
          ctx.moveTo(x + 0.4, y + 0.63);
          ctx.lineTo(x + 0.58, y + 0.63);
          ctx.moveTo(x + 0.49, y + 0.57);
          ctx.lineTo(x + 0.49, y + 0.69);
          ctx.stroke();
          ctx.fillStyle = "rgba(255,230,180,0.95)";
          ctx.fillRect(x + 0.18, y + 0.14, 0.08, 0.06);
          ctx.fillRect(x + 0.74, y + 0.14, 0.08, 0.06);
          ctx.fillRect(x + 0.46, y + 0.76, 0.1, 0.06);
          ctx.strokeStyle = "rgba(255,230,180,0.9)";
          ctx.beginPath();
          ctx.moveTo(x + 0.22, y + 0.2);
          ctx.lineTo(x + 0.22, y + 0.22);
          ctx.moveTo(x + 0.52, y + 0.34);
          ctx.lineTo(x + 0.56, y + 0.34);
          ctx.moveTo(x + 0.67, y + 0.46);
          ctx.lineTo(x + 0.5, y + 0.54);
          ctx.moveTo(x + 0.51, y + 0.72);
          ctx.lineTo(x + 0.51, y + 0.76);
          ctx.stroke();
          ctx.lineWidth = 0.02;
          ctx.strokeStyle = "rgba(255,220,160,0.95)";
          ctx.beginPath();
          ctx.moveTo(x + 0.78, y + 0.64);
          ctx.lineTo(x + 0.9, y + 0.64);
          ctx.stroke();
        } else {
          ctx.fillStyle = "rgba(90,160,210,0.95)";
          ctx.fillRect(x + 0.1, y, 0.06, 1);
          ctx.fillStyle = "rgba(230,245,255,0.95)";
          ctx.fillRect(x + 0.105, y + 0.08, 0.05, 0.032);
          ctx.fillRect(x + 0.105, y + 0.888, 0.05, 0.032);
          const clk = (performance.now() / 420) % 1 < 0.18;
          for (let k = 0; k < 4; k++) {
            const yy = y + 0.05 + k * 0.23;
            ctx.fillStyle = "rgba(159,212,255,0.92)";
            ctx.fillRect(x + 0.2, yy, 0.36, 0.18);
            ctx.fillStyle = "rgba(230,242,255,0.95)";
            for (let p = 0; p < 4; p++) ctx.fillRect(x + 0.205, yy + 0.02 + p * 0.03, 0.025, 0.018);
            ctx.fillRect(x + 0.51, yy + 0.05, 0.028, 0.04);
            ctx.fillStyle = "rgba(80,140,190,0.95)";
            ctx.fillRect(x + 0.58, yy + 0.01, 0.1, 0.12);
            ctx.fillRect(x + 0.72, yy + 0.01, 0.1, 0.12);
            ctx.fillStyle = clk ? "rgba(255,220,120,0.95)" : "rgba(16,32,48,0.95)";
            ctx.beginPath();
            ctx.moveTo(x + 0.585, yy + 0.04);
            ctx.lineTo(x + 0.62, yy + 0.07);
            ctx.lineTo(x + 0.585, yy + 0.1);
            ctx.moveTo(x + 0.725, yy + 0.04);
            ctx.lineTo(x + 0.76, yy + 0.07);
            ctx.lineTo(x + 0.725, yy + 0.1);
            ctx.fill();
            ctx.strokeStyle = "rgba(210,225,240,0.8)";
            ctx.beginPath();
            ctx.moveTo(x + 0.54, yy + 0.07);
            ctx.lineTo(x + 0.58, yy + 0.07);
            ctx.moveTo(x + 0.68, yy + 0.07);
            ctx.lineTo(x + 0.72, yy + 0.07);
            ctx.stroke();
            ctx.fillStyle = "rgba(220,230,240,0.8)";
            ctx.fillRect(x + 0.56, yy + 0.05, 0.02, 0.04);
          }
          ctx.lineWidth = 0.018;
          ctx.strokeStyle = "rgba(220,232,244,0.9)";
          for (let k = 0; k < 4; k++) {
            const yy = y + 0.14 + k * 0.23;
            ctx.beginPath();
            ctx.moveTo(x + 0.82, yy);
            ctx.lineTo(x + 0.9, yy);
            ctx.stroke();
          }
        }
        if (cellPx > 18) {
          ctx.fillStyle = "rgba(186,198,214,0.9)";
          for (let s = 0; s < 5; s++) ctx.fillRect(x + 0.86, y + 0.14 + s * 0.15, 0.05, 0.05);
        }
      }
      ctx.strokeStyle = "rgba(212,186,110,0.7)";
      ctx.lineWidth = 0.045;
      for (let y = yRail0; y < yHi; y += 8) {
        ctx.beginPath();
        ctx.moveTo(xLo, y + 0.5);
        ctx.lineTo(xHi, y + 0.5);
        ctx.stroke();
      }
      const xRail0 = Math.ceil(xLo / 12) * 12;
      for (let x = xRail0; x < xHi; x += 12) {
        ctx.beginPath();
        ctx.moveTo(x + 0.5, yLo);
        ctx.lineTo(x + 0.5, yHi);
        ctx.stroke();
      }
    }
    ctx.restore();

    ctx.strokeStyle = "rgba(214,186,110,0.9)";
    ctx.lineWidth = 1.6;
    const nBond = 26;
    for (let i = 1; i < nBond; i++) {
      const t = i / nBond;
      const pairs = [
        [nx * t, 0, nx * t, -my * 0.2],
        [nx * t, ny, nx * t, ny + my * 0.2],
        [0, ny * t, -mx * 0.2, ny * t],
        [nx, ny * t, nx + mx * 0.2, ny * t],
      ];
      for (const [x0, y0, x1, y1] of pairs) {
        const A = screen(proj(world(x0, y0, zTop * 0.92)), cx, cy, sc);
        const M = screen(proj(world((x0 + x1) / 2, (y0 + y1) / 2, zTop * 1.08)), cx, cy, sc);
        const B = screen(proj(world(x1, y1, 0.35)), cx, cy, sc);
        ctx.beginPath();
        ctx.moveTo(A[0], A[1]);
        ctx.quadraticCurveTo(M[0], M[1], B[0], B[1]);
        ctx.stroke();
        const pr = Math.min(nx, ny) * 0.0035;
        const pad = [[x0 - pr, y0 - pr], [x0 + pr, y0 - pr], [x0 + pr, y0 + pr], [x0 - pr, y0 + pr]]
          .map(([x, y]) => screen(proj(world(x, y, zTop * 0.94)), cx, cy, sc));
        ctx.beginPath();
        pad.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
        ctx.closePath();
        ctx.fillStyle = "#e2c56a";
        ctx.fill();
      }
    }

    ctx.restore();
  }

  /* ---------- 一次打击的动画：入射 → 电荷收集 → 位翻转 → 后果 → 恢复 ----------
     时间轴是教学节拍（秒），物理时间尺度写在页面的阶段条上。 */
  const PH = [0, 0.8, 1.5, 2.3, 3.6, 5.6];
  const REC_LABEL = { CFG: "刷新修复", BRAM_STATE: "ECC 纠正", FF_STATE: "已被覆盖" };
  function phaseAt(t) {
    if (t >= PH[5]) return 5;
    for (let i = 4; i >= 0; i--) if (t >= PH[i]) return i;
    return 0;
  }
  function fmtLet(v) { return v >= 10 ? v.toFixed(0) : v.toFixed(1); }
  function focusOn(x, y, zoomT) {
    const r = canvas.getBoundingClientRect(), L = S.layout;
    const rmax = Math.hypot(L.ncols, L.nrows) * 0.55;
    const sc = Math.min(r.width, r.height) * 0.42 * zoomT / rmax;
    const zTop = Math.max(6, Math.min(L.ncols, L.nrows) * 0.035);
    const q = proj(world(x, y, zTop));
    S.focus = { t0: performance.now(), dur: 750,
      from: { zoom: S.view.zoom, panX: S.view.panX, panY: S.view.panY },
      to: { zoom: zoomT, panX: -sc * q.x, panY: sc * q.y } };
  }
  function prepAnim(j) {
    const L = S.layout, eff = j.effects || {};
    const cands = [], seen = new Set();
    for (const e of j.candidates || []) {
      if (seen.has(e.unit_id)) continue;
      seen.add(e.unit_id);
      const ci = S.cellByUnit.get(e.unit_id);
      if (ci !== undefined) cands.push(ci);
    }
    // 刷新带只扫打击点附近 ±20 格（真实器件整片扫一遍要 ms 量级）
    const xa = Math.max(0, j.x0 - 20), xb = Math.min(L.ncols, j.x0 + 20);
    const flips = [];
    for (const f of j.flipped || []) {
      const ci = S.cellByUnit.get(f.unit_id);
      if (ci === undefined) continue;
      const c = S.cells[ci];
      let rec;
      if (f.domain === "CFG") rec = PH[4] + Math.max(0, Math.min(1, (c[0] + 0.5 - xa) / Math.max(1, xb - xa))) * (PH[5] - PH[4]);
      else if (f.domain === "BRAM_STATE") rec = PH[4] + 0.5;
      else rec = PH[4] + 0.15;
      flips.push({ ci, dom: f.domain, n: f.n_bits || 1, rec, modIdx: c[10],
                   bit: flips.length % 2 ? "1→0" : "0→1" });
    }
    let setPath = null;
    const setEff = (eff.effects || []).find(e => e.id === "set");
    if (setEff && setEff.status === "possible") {
      let best = null, bd = 1e9;
      const gx = Math.floor(j.x0), gy = Math.floor(j.y0);
      for (let dy = -2; dy <= 2; dy++) for (let dx = -12; dx <= 12; dx++) {
        if (Math.abs(dx) < 3) continue;
        const ci = S.cellAt.get((gx + dx) + "," + (gy + dy));
        if (ci === undefined || S.cells[ci][2] !== "SLICE") continue;
        const d = Math.abs(dx) + 2 * Math.abs(dy);
        if (d < bd) { bd = d; best = ci; }
      }
      if (best !== null) {
        const c = S.cells[best];
        setPath = [[j.x0, j.y0], [c[0] + 0.5, j.y0], [c[0] + 0.5, c[1] + 0.5]];
      }
    }
    const selEff = (eff.effects || []).find(e => e.id === "sel");
    return { t0: performance.now(), ph: -1, cands, flips, setPath, xa, xb,
             mods: [...new Set(flips.map(f => f.modIdx).filter(m => m >= 0))],
             sel: !!(selEff && selEff.status === "risk"), bits: eff.bits || 0 };
  }
  function drawStrike(ctx, cx, cy, sc, zTop) {
    const s = S.strike, A = S.anim;
    if (!s || !A) return;
    const L = S.layout, filt = S.domFilter;
    const t = A.paused != null ? A.paused : (performance.now() - A.t0) / 1000;
    const ph = phaseAt(t);
    if (ph !== A.ph) { A.ph = ph; if (onPhase) onPhase(ph); }
    const P = (x, y, z) => screen(proj(world(x, y, z)), cx, cy, sc);
    const line = (a, b) => { ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); };
    const poly = pts => { ctx.beginPath(); pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath(); };
    const label = (x, y, text, col, size = 12) => {
      ctx.font = `${size}px "Microsoft YaHei",sans-serif`; ctx.textAlign = "left";
      ctx.lineWidth = 3; ctx.strokeStyle = "rgba(4,7,13,.88)"; ctx.strokeText(text, x, y);
      ctx.fillStyle = col; ctx.fillText(text, x, y);
    };
    const cellQuad = (ci, grow, z) => {
      const c = S.cells[ci], g = (grow - 1) / 2;
      poly([[c[0] - g, c[1] - g], [c[0] + 1 + g, c[1] - g], [c[0] + 1 + g, c[1] + 1 + g], [c[0] - g, c[1] + 1 + g]].map(([x, y]) => P(x, y, z)));
    };
    const zS = zTop + 0.06;
    const th = s.theta_deg * Math.PI / 180, fi = s.phi_deg * Math.PI / 180;
    const dir = [Math.sin(th) * Math.cos(fi), Math.sin(th) * Math.sin(fi), -Math.cos(th)];
    const Lray = Math.max(L.ncols, L.nrows) * 0.55;
    const hit = [s.x0, s.y0, zS];
    const at = k => [hit[0] - dir[0] * k, hit[1] - dir[1] * k, hit[2] - dir[2] * k];
    const H = P(...hit);
    const kern = Math.max(2.5, s.b || 0);          // 电荷云按 ≥2.5 格示意放大（实际收集半径约 1 µm）
    ctx.lineCap = "round";

    // 1 入射
    if (t < PH[1]) {
      const p = t / PH[1], k = (1 - p * p) * Lray;
      const Hd = P(...at(k)), Tl = P(...at(Math.min(Lray * 1.3, k + Lray * 0.35)));
      const g = ctx.createLinearGradient(Tl[0], Tl[1], Hd[0], Hd[1]);
      g.addColorStop(0, "rgba(255,210,63,0)"); g.addColorStop(1, "rgba(255,246,210,.95)");
      ctx.strokeStyle = g; ctx.lineWidth = 6; line(Tl, Hd);
      ctx.lineWidth = 1.8; line(Tl, Hd);
      const gl = ctx.createRadialGradient(Hd[0], Hd[1], 0, Hd[0], Hd[1], 15);
      gl.addColorStop(0, "rgba(255,250,220,1)"); gl.addColorStop(1, "rgba(255,170,60,0)");
      ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(Hd[0], Hd[1], 15, 0, 6.3); ctx.fill();
      label(Hd[0] + 14, Hd[1] - 8, `离子  LET ${fmtLet(s.let)}`, "#ffe2a6");
    } else {
      const a = Math.max(0.14, 0.85 - (t - PH[1]) * 0.35);
      ctx.strokeStyle = `rgba(255,220,130,${a})`; ctx.lineWidth = 1.4; line(P(...at(Lray * 0.8)), H);
    }
    if (t >= PH[1] && t < PH[1] + 0.35) {
      const q = (t - PH[1]) / 0.35, r = 10 + 44 * q;
      const g = ctx.createRadialGradient(H[0], H[1], 0, H[0], H[1], r);
      g.addColorStop(0, `rgba(255,255,235,${0.95 * (1 - q)})`); g.addColorStop(1, "rgba(255,180,60,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(H[0], H[1], r, 0, 6.3); ctx.fill();
    }
    // 2 硅内径迹 + 电荷云（电子向上被结收集，空穴向衬底）
    if (t >= PH[1] && t < PH[3]) {
      const p = Math.min(1, (t - PH[1]) / (PH[2] - PH[1]));
      const fade = t < PH[2] ? 1 : 1 - (t - PH[2]) / (PH[3] - PH[2]);
      const depth = 3, kIn = depth / Math.max(0.3, Math.cos(th));
      const inside = f => [hit[0] + dir[0] * kIn * f, hit[1] + dir[1] * kIn * f, hit[2] + dir[2] * kIn * f];
      ctx.strokeStyle = `rgba(255,236,170,${0.85 * fade})`; ctx.lineWidth = 2.2; line(H, P(...inside(1)));
      for (let i = 0; i < 60; i++) {
        const f = (i * 0.6180339) % 1, ang = i * 2.39996;
        const rr = kern * Math.sqrt(p) * (0.3 + 0.7 * ((i * 0.3719) % 1));
        const b = inside(f), drift = (i % 2 ? 1 : -0.6) * Math.max(0, p - 0.35) * depth * 0.6;
        const q = P(b[0] + Math.cos(ang) * rr, b[1] + Math.sin(ang) * rr, b[2] + drift);
        ctx.fillStyle = i % 2 ? `rgba(92,200,255,${0.9 * fade})` : `rgba(255,123,114,${0.85 * fade})`;
        ctx.beginPath(); ctx.arc(q[0], q[1], 1.9, 0, 6.3); ctx.fill();
      }
      if (t < PH[2]) { label(H[0] + 22, H[1] + 30, "● 电子", "#5cc8ff", 11); label(H[0] + 72, H[1] + 30, "● 空穴", "#ff7b72", 11); label(H[0] + 22, H[1] + 46, "电荷云（放大示意）", "#7f93ab", 10); }
    }
    // 收集核（示意放大到至少 0.7 格）
    if (t >= PH[1] + 0.2) {
      const alpha = t < PH[4] ? Math.min(1, (t - PH[1] - 0.2) / 0.4) : 0.3;
      const ea = Math.max(s.a || 0, kern * 1.1), eb = kern;
      const pts = [];
      for (let k = 0; k < 48; k++) {
        const q = k / 48 * 6.2832, u = ea * Math.cos(q), v = eb * Math.sin(q);
        pts.push(P(s.x0 + u * Math.cos(fi) - v * Math.sin(fi), s.y0 + u * Math.sin(fi) + v * Math.cos(fi), zS + 0.02));
      }
      poly(pts); ctx.fillStyle = `rgba(77,163,255,${0.16 * alpha})`; ctx.fill();
      ctx.strokeStyle = `rgba(159,212,255,${0.9 * alpha})`; ctx.lineWidth = 1.4; ctx.stroke();
    }
    // 3 候选与翻转
    if (t >= PH[2]) {
      const a = t < PH[4] ? Math.min(1, (t - PH[2]) / 0.3) : 0.4;
      ctx.strokeStyle = `rgba(255,210,63,${a})`; ctx.lineWidth = 1.6;
      for (const ci of A.cands) { cellQuad(ci, 1, zS); ctx.stroke(); }
      A.flips.forEach((f, k) => {
        if (filt && !filt.has(f.dom)) return;
        const c = S.cells[f.ci], C = P(c[0] + 0.5, c[1] + 0.5, zS);
        if (t < f.rec) {
          const q = Math.min(1, (t - PH[2]) / 0.35);
          const pul = t >= PH[3] ? 0.72 + 0.28 * Math.sin(t * 9) : 1;
          cellQuad(f.ci, 1 + 0.9 * (1 - q), zS + 0.05);
          ctx.fillStyle = `rgba(255,95,86,${0.92 * pul})`; ctx.fill();
          ctx.strokeStyle = "#ffd0cc"; ctx.lineWidth = 1.2; ctx.stroke();
          if (q < 1) { ctx.strokeStyle = `rgba(255,120,110,${1 - q})`; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(C[0], C[1], 6 + 28 * q, 0, 6.3); ctx.stroke(); }
          if (t < PH[3] + 0.5) label(C[0] + 9, C[1] - 12 - 12 * q - k * 14, f.n > 1 ? `${f.bit} ×${f.n}` : f.bit, "#ffb3ab");
        } else if (t < f.rec + 0.9) {
          const q = (t - f.rec) / 0.9;
          cellQuad(f.ci, 1 + 0.7 * q, zS + 0.05);
          ctx.fillStyle = `rgba(126,231,135,${0.85 * (1 - q)})`; ctx.fill();
          label(C[0] + 9, C[1] - 12 - k * 14, REC_LABEL[f.dom] || "恢复", "#9ff0a6");
        }
      });
      if (!A.flips.length && t < PH[5])
        label(H[0] + 14, H[1] - 14, s.n_candidates ? "电荷没收够，没有位翻转" : "打在空闲区，没碰到资源", "#9fb3c8");
      if (A.bits >= 2 && t < PH[4]) label(H[0] + 14, H[1] + 44, `MCU：一颗离子翻 ${A.bits} bit`, "#ffd27a");
    }
    // 4 后果：受影响模块、FF 下一拍传播、SET 毛刺、SEL 风险
    if (t >= PH[3] && t < PH[4] + 0.5) {
      const q = Math.min(1, (t - PH[3]) / 0.4), pul = 0.6 + 0.4 * Math.sin(t * 6);
      for (const m of A.mods) {
        const b = S.modBox[m], mod = (L.modules || [])[m] || {};
        if (!b) continue;
        const pts = [[b[0], b[1]], [b[2] + 1, b[1]], [b[2] + 1, b[3] + 1], [b[0], b[3] + 1]].map(([x, y]) => P(x, y, zS + 0.1));
        poly(pts); ctx.strokeStyle = mod.color || "#fff"; ctx.globalAlpha = q * pul; ctx.lineWidth = 2.4;
        ctx.setLineDash([8, 5]); ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
        const cc = S.cells[A.flips.find(f => f.modIdx === m).ci];
        const Q = P(cc[0] + 0.5, cc[1] + 0.5, zS);
        label(Q[0] - 150, Q[1] + 34, `模块 ${mod.name || m} 出错`, mod.color || "#fff", 12);
      }
      const u = Math.min(1, (t - PH[3]) / ((PH[4] - PH[3]) * 0.8));
      for (const f of A.flips) {
        if (f.dom !== "FF_STATE" || (filt && !filt.has(f.dom))) continue;
        const c = S.cells[f.ci];
        const a = P(c[0] + 0.5, c[1] + 0.5, zS + 0.1), b = P(c[0] + 6.5, c[1] + 0.5, zS + 0.1);
        const m = [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u];
        ctx.strokeStyle = "rgba(255,150,120,.7)"; ctx.lineWidth = 2; line(a, m);
        ctx.fillStyle = "#ffb3ab"; ctx.beginPath(); ctx.arc(m[0], m[1], 3.6, 0, 6.3); ctx.fill();
        label(m[0] + 6, m[1] - 6, "下一拍传到下游", "#ffb3ab", 11);
      }
      if (A.setPath) {
        const pts = A.setPath.map(([x, y]) => P(x, y, zS + 0.12));
        const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
        const tot = seg.reduce((x, y) => x + y, 0) || 1;
        let d = u * tot, i = 0;
        while (i < seg.length - 1 && d > seg[i]) { d -= seg[i]; i++; }
        const r = Math.min(1, d / (seg[i] || 1));
        const hd = [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * r, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * r];
        ctx.strokeStyle = "rgba(255,236,120,.4)"; ctx.lineWidth = 1.2; ctx.setLineDash([3, 3]);
        ctx.beginPath(); pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.stroke(); ctx.setLineDash([]);
        const g = ctx.createRadialGradient(hd[0], hd[1], 0, hd[0], hd[1], 10);
        g.addColorStop(0, "rgba(255,250,200,1)"); g.addColorStop(1, "rgba(255,220,80,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(hd[0], hd[1], 10, 0, 6.3); ctx.fill();
        const e = pts[pts.length - 1];
        ctx.strokeStyle = u >= 1 ? "#ffd27a" : "rgba(200,210,220,.6)"; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(e[0] - 12, e[1] + 14); ctx.lineTo(e[0] - 6, e[1] + 14); ctx.lineTo(e[0] - 6, e[1] + 5);
        ctx.lineTo(e[0], e[1] + 5); ctx.lineTo(e[0], e[1] + 14); ctx.lineTo(e[0] + 6, e[1] + 14); ctx.stroke();
        label(e[0] + 10, e[1] + 16, u >= 1 ? "SET 到达触发器：碰上时钟沿才出错" : "SET 毛刺沿布线跑", "#ffe89a", 11);
      }
      if (A.sel) {
        const r = 18 + 6 * Math.sin(t * 8);
        ctx.strokeStyle = "rgba(255,95,86,.9)"; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(H[0], H[1], r, 0, 6.3); ctx.stroke();
        label(H[0] - 150, H[1] - 26, "⚠ SEL 风险：LET ≥ 15", "#ff9d94");
      }
    }
    // 5 恢复：配置刷新带扫过打击点附近
    if (t >= PH[4] && t < PH[5]) {
      const u = (t - PH[4]) / (PH[5] - PH[4]);
      const xs = A.xa + u * (A.xb - A.xa);
      const y0 = Math.max(0, s.y0 - 30), y1 = Math.min(L.nrows, s.y0 + 30);
      const band = [[Math.max(A.xa, xs - 3), y0], [xs, y0], [xs, y1], [Math.max(A.xa, xs - 3), y1]].map(([x, y]) => P(x, y, zS + 0.08));
      poly(band); ctx.fillStyle = "rgba(126,231,135,.16)"; ctx.fill();
      ctx.strokeStyle = "rgba(126,231,135,.85)"; ctx.lineWidth = 1.6; line(band[1], band[2]);
      const lb = P(xs, s.y0 - 6, zS);
      label(lb[0] + 6, lb[1], "配置刷新（按帧列扫）", "#9ff0a6");
    }
    if (t >= PH[5]) {
      ctx.strokeStyle = "rgba(255,220,130,.85)"; ctx.lineWidth = 1.2;
      line([H[0] - 8, H[1]], [H[0] + 8, H[1]]); line([H[0], H[1] - 8], [H[0], H[1] + 8]);
    }
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
    S.focus = null;
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
            module: ((S.layout.modules || [])[c[10]] || {}).name || "",
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
    S.focus = null;
    const nz = Math.max(0.4, Math.min(40, oldZ * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
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
      S.links = [];
      S.cellByUnit = new Map();
      S.modBox = {};
      S.cells.forEach((c, i) => {
        S.cellByUnit.set(c[5], i);
        const m = c[10];
        if (m === undefined || m < 0) return;
        const b = S.modBox[m] || (S.modBox[m] = [c[0], c[1], c[0], c[1]]);
        b[0] = Math.min(b[0], c[0]); b[1] = Math.min(b[1], c[1]);
        b[2] = Math.max(b[2], c[0]); b[3] = Math.max(b[3], c[1]);
      });
    },
    setStrike(j) {
      S.strike = j;
      if (!j) { S.anim = null; return; }
      S.x0 = j.x0; S.y0 = j.y0;
      S.anim = prepAnim(j);
      if (S.focusOn) focusOn(j.x0, j.y0, 20);
    },
    replay() { if (S.strike) S.anim = prepAnim(S.strike); },
    seekPhase(i) {                    // 跳到某一阶段开头继续播放
      if (!S.anim) return;
      S.anim.paused = null;
      S.anim.t0 = performance.now() - PH[Math.max(0, Math.min(4, i))] * 1000;
    },
    seek(t, pause) {                  // 调试：定格在 t 秒
      if (!S.anim) return;
      S.anim.t0 = performance.now() - t * 1000;
      S.anim.paused = pause ? t : null;
    },
    _bench() {           // 同步测一次静态场景 + 打击层耗时（调试用）
      const r = canvas.getBoundingClientRect(), L = S.layout, w = r.width, h = r.height;
      const rmax = Math.hypot(L.ncols, L.nrows) * 0.55;
      const cx = w / 2 + S.view.panX, cy = h / 2 + S.view.panY;
      const sc = Math.min(w, h) * 0.42 * S.view.zoom / rmax;
      const zTop = Math.max(6, Math.min(L.ncols, L.nrows) * 0.035);
      const t0 = performance.now();
      drawScene(w, h, cx, cy, sc, window.devicePixelRatio || 1);
      const t1 = performance.now();
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      if (S.anim) S.anim.t0 = performance.now() - 2600;
      drawStrike(c.getContext("2d"), cx, cy, sc, zTop);
      return { sceneMs: +(t1 - t0).toFixed(1), overlayMs: +(performance.now() - t1).toFixed(1), zoom: +S.view.zoom.toFixed(2) };
    },
    setFocus(v) { S.focusOn = !!v; },
    setColorMode(m) { S.colorMode = m === "module" ? "module" : "resource"; S.occDirty = true; },
    setShowBboxes(v) { S.showBboxes = !!v; },
    setDomainFilter(doms) {
      S.domFilter = doms ? new Set(doms) : null;
      S.occDirty = true;
    },
    resetView() {
      S.focus = null;
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

/* /live 页面的 STK 视角实时地球视图。
 *
 * 与 orbit_seu/webapp/orbit3d.js 同一渲染思路：2D canvas 软件光栅，
 * earth.jpg 等距圆柱贴图逐像素采样，正交投影，无外部依赖。
 * 区别：数据来源是 STK Connect 逐历元推送的 ECEF 位置（ECEF 系固定，
 * 地球不随时间自转——卫星坐标本身已在地球系），相机只由拖拽决定。
 *
 * 用法：
 *   const g = LiveGlobe(document.getElementById("cv"), {texture: "/static/earth.jpg"});
 *   g.push({ecef_km:[x,y,z], env:"gcr_dominant", rc:0.85, epoch:"..."});  // 每个采样点
 *   g.clear();   g.follow(true/false);
 */
(function () {
"use strict";

const RE = 6371.0;
const V = {
  dot: (a, b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2],
  len: a => Math.hypot(a[0], a[1], a[2]),
  norm: a => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0]/l, a[1]/l, a[2]/l]; },
  scale: (a, k) => [a[0]*k, a[1]*k, a[2]*k],
  /* 偏航(yaw,绕z)/俯仰(pitch)旋转后再投影到屏幕 */
};
const ENV_COLOR = { gcr_dominant:"#45c8ff", inner_belt_candidate:"#ffb454", saa_region_approx:"#ff7a7a" };
const ENV_LABEL = { gcr_dominant:"GCR 主导", inner_belt_candidate:"内带候选", saa_region_approx:"SAA 近似区" };
/* 与后端 orbit_attach._environment_tag 的 SAA 近似多边形一致 */
const SAA = { latMin: -55, latMax: 5, lonMin: -100, lonMax: 25, altMaxKm: 1500 };

function lla2ecef(latDeg, lonDeg, altKm) {
  const la = latDeg * Math.PI/180, lo = lonDeg * Math.PI/180, r = RE + altKm;
  return [r*Math.cos(la)*Math.cos(lo), r*Math.cos(la)*Math.sin(lo), r*Math.sin(la)];
}

window.LiveGlobe = function (canvas, opts) {
  opts = opts || {};
  const ctx = canvas.getContext("2d");
  const cam = { yaw: -0.6, pitch: 0.35, k: 42 };   /* k: px per RE */
  const track = [];                                 /* {p:[ecef km], env, rc, epoch} */
  const orbit = [];                                 /* 平台传播的完整轨道 */
  let orbitCur = 0, orbitFly = false, orbitSpd = 30, lastNow = 0;
  let followOn = true, drag = null, raf = 0;
  let W = 0, H = 0;

  /* 地球贴图 */
  let tex = null, TW = 0, TH = 0;
  const img = new Image();
  img.onload = () => {
    const c = document.createElement("canvas");
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    c.getContext("2d").drawImage(img, 0, 0);
    try { tex = c.getContext("2d").getImageData(0, 0, c.width, c.height).data; TW = c.width; TH = c.height; }
    catch (e) { tex = null; }
  };
  img.src = opts.texture || "/static/earth.jpg";
  const SUN = V.norm([1, 0.3, 0.35]);
  const STARS = (() => { let s = 7; const r = () => (s = (s*16807) % 2147483647) / 2147483647; const o = [];
    for (let i = 0; i < 420; i++) { const z = 2*r()-1, t = 2*Math.PI*r(), q = Math.sqrt(1-z*z);
      o.push([q*Math.cos(t), q*Math.sin(t), z, .25+.7*r()]); } return o; })();

  /* ECEF → 相机系 → 屏幕（yaw 绕 z，再 pitch 绕新 x；orthographic） */
  function proj(p) {
    const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
    const x1 = p[0]*cy + p[1]*sy, y1 = -p[0]*sy + p[1]*cy, z1 = p[2];
    const cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    const y2 = y1*cp - z1*sp, z2 = y1*sp + z1*cp;
    const u = x1 / RE, w = z2 / RE;               /* 以 RE 为单位 */
    return { x: W/2 + u*cam.k, y: H/2 - w*cam.k, front: y2 > 0 };
  }

  function draw(now) {
    const dt = lastNow ? now - lastNow : 0;
    lastNow = now;
    const dpr = window.devicePixelRatio || 1;
    const bw = canvas.clientWidth * dpr, bh = canvas.clientHeight * dpr;
    if (canvas.width !== bw || canvas.height !== bh) { canvas.width = bw; canvas.height = bh; }
    W = bw; H = bh;
    ctx.fillStyle = "#04070d"; ctx.fillRect(0, 0, W, H);

    /* 星空：与地球同相机旋转 */
    ctx.save();
    for (const s of STARS) {
      const q = proj([s[0]*RE*9, s[1]*RE*9, s[2]*RE*9]);
      if (!q.front) continue;
      ctx.globalAlpha = s[3]; ctx.fillStyle = "#aecbe8";
      ctx.fillRect(q.x, q.y, 1.4*dpr, 1.4*dpr);
    }
    ctx.restore();

    const Rpx = cam.k;                              /* 地球半径像素 */
    const CX = W/2, CY = H/2;
    /* 地球盘：逐像素采样贴图（背面剔除由 r<=Rpx 圆盘与光照完成） */
    if (tex) {
      const out = ctx.createImageData(Math.ceil(2*Rpx), Math.ceil(2*Rpx));
      const d = out.data;
      const cy_ = Math.cos(cam.yaw), sy_ = Math.sin(cam.yaw);
      const cp_ = Math.cos(cam.pitch), sp_ = Math.sin(cam.pitch);
      for (let py = 0; py < out.height; py++) for (let px = 0; px < out.width; px++) {
        const u = (px - Rpx) / Rpx, w = (Rpx - py) / Rpx;
        const rr = u*u + w*w;
        if (rr > 1) continue;
        const v = Math.sqrt(1 - rr);              /* 朝相机的深度 */
        /* 相机系 (u, v(深), w) 反旋转回 ECEF */
        const y1 = v*cp_ + w*sp_, z1 = -v*sp_ + w*cp_, x1 = u;
        const ex = x1*cy_ - y1*sy_, ey = x1*sy_ + y1*cy_, ez = z1;
        const lat = Math.asin(Math.max(-1, Math.min(1, ez)));
        const lon = Math.atan2(ey, ex);
        const tx = Math.min(TW-1, Math.max(0, ((lon + Math.PI) / (2*Math.PI)) * TW));
        const ty = Math.min(TH-1, Math.max(0, ((Math.PI/2 - lat) / Math.PI) * TH));
        const ti = ((ty|0) * TW + (tx|0)) * 4;
        const sun = Math.max(0, V.dot(V.norm([ex, ey, ez]), SUN));
        const shade = 0.16 + 0.84 * Math.pow(sun, 0.75);
        const oi = (py * out.width + px) * 4;
        d[oi] = tex[ti] * shade; d[oi+1] = tex[ti+1] * shade;
        d[oi+2] = tex[ti+2] * shade; d[oi+3] = 255;
      }
      ctx.putImageData(out, CX - Rpx, CY - Rpx);
      /* 晨昏大气边缘 */
      const g = ctx.createRadialGradient(CX, CY, Rpx*0.96, CX, CY, Rpx*1.06);
      g.addColorStop(0, "rgba(80,160,230,0)"); g.addColorStop(.5, "rgba(90,170,240,.18)");
      g.addColorStop(1, "rgba(80,160,230,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(CX, CY, Rpx*1.07, 0, 7); ctx.fill();
    } else {
      ctx.fillStyle = "#0d2438";
      ctx.beginPath(); ctx.arc(CX, CY, Rpx, 0, 7); ctx.fill();
      ctx.strokeStyle = "#1e5d8a"; ctx.stroke();
    }

    /* SAA 近似区边界（与后端同多边形，经纬网格边） */
    ctx.save();
    ctx.setLineDash([4*dpr, 4*dpr]);
    ctx.strokeStyle = "rgba(255,120,120,.55)"; ctx.lineWidth = 1*dpr;
    const saaEdge = [];
    const NP = 40;
    for (let i = 0; i <= NP; i++) saaEdge.push(lla2ecef(SAA.latMin, SAA.lonMin + (SAA.lonMax-SAA.lonMin)*i/NP, 0));
    for (let i = 0; i <= NP; i++) saaEdge.push(lla2ecef(SAA.latMin + (SAA.latMax-SAA.latMin)*i/NP, SAA.lonMax, 0));
    for (let i = NP; i >= 0; i--) saaEdge.push(lla2ecef(SAA.latMax, SAA.lonMin + (SAA.lonMax-SAA.lonMin)*i/NP, 0));
    for (let i = NP; i >= 0; i--) saaEdge.push(lla2ecef(SAA.latMin + (SAA.latMax-SAA.latMin)*i/NP, SAA.lonMin, 0));
    ctx.beginPath();
    let pen = false;
    for (const p of saaEdge) {
      const q = proj(p);
      if (!q.front) { pen = false; continue; }
      if (!pen) { ctx.moveTo(q.x, q.y); pen = true; } else ctx.lineTo(q.x, q.y);
    }
    ctx.stroke();
    ctx.restore();

    /* 轨道轨迹：按环境 tag 分段着色；背面段不画 */
    for (let i = 1; i < track.length; i++) {
      const a = proj(track[i-1].p), b = proj(track[i].p);
      if (!a.front && !b.front) continue;
      ctx.strokeStyle = ENV_COLOR[track[i].env] || "#45c8ff";
      ctx.lineWidth = 1.6 * dpr;
      ctx.globalAlpha = (a.front && b.front) ? 0.9 : 0.25;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    ctx.globalAlpha = 1;

    /* 平台传播的完整轨道：同一环境着色法，全程常显 */
    for (let i = 1; i < orbit.length; i++) {
      const a = proj(orbit[i-1].p), b = proj(orbit[i].p);
      if (!a.front && !b.front) continue;
      ctx.strokeStyle = ENV_COLOR[orbit[i].env] || "#45c8ff";
      ctx.lineWidth = 1.3 * dpr;
      ctx.globalAlpha = (a.front && b.front) ? 0.55 : 0.15;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    ctx.globalAlpha = 1;

    /* 光标沿轨道飞行 */
    if (orbit.length) {
      if (orbitFly) orbitCur = (orbitCur + dt / 1000 * orbitSpd) % orbit.length;
      const cur = orbit[Math.floor(orbitCur) % orbit.length], q = proj(cur.p);
      const col = ENV_COLOR[cur.env] || "#45c8ff";
      ctx.save();
      ctx.shadowColor = col; ctx.shadowBlur = 12 * dpr;
      ctx.fillStyle = "#fff";
      ctx.beginPath(); ctx.arc(q.x, q.y, 3.4*dpr, 0, 7); ctx.fill();
      ctx.restore();
      ctx.strokeStyle = col; ctx.lineWidth = 1.2*dpr;
      const pulse = (now/1000 % 1.6) / 1.6;
      ctx.globalAlpha = 1 - pulse;
      ctx.beginPath(); ctx.arc(q.x, q.y, (4 + 12*pulse)*dpr, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
      const alt = (V.len(cur.p) - RE).toFixed(0);
      ctx.font = `${11*dpr}px Consolas,monospace`; ctx.fillStyle = "#dff3ff";
      const lx = q.x + 10*dpr, ly = q.y - 10*dpr;
      ctx.fillText(`alt ${alt} km  Rc ${cur.rc == null ? "—" : cur.rc.toFixed(2)} GV`, lx, ly);
      if (cur.epoch) { ctx.fillStyle = "#7f93ab"; ctx.fillText(String(cur.epoch).slice(0, 26), lx, ly + 13*dpr); }
    }

    /* 当前位置标记（STK 推送的 track 尾点） */
    if (track.length) {
      const cur = track[track.length - 1], q = proj(cur.p);
      const col = ENV_COLOR[cur.env] || "#45c8ff";
      ctx.save();
      ctx.shadowColor = col; ctx.shadowBlur = 10 * dpr;
      ctx.fillStyle = "#fff";
      ctx.beginPath(); ctx.arc(q.x, q.y, 3.2*dpr, 0, 7); ctx.fill();
      ctx.restore();
      ctx.strokeStyle = col; ctx.lineWidth = 1.2*dpr;
      const pulse = (now/1000 % 1.6) / 1.6;
      ctx.globalAlpha = 1 - pulse;
      ctx.beginPath(); ctx.arc(q.x, q.y, (4 + 12*pulse)*dpr, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
      /* 标注 */
      const alt = (V.len(cur.p) - RE).toFixed(0);
      ctx.font = `${11*dpr}px Consolas,monospace`; ctx.fillStyle = "#dff3ff";
      const lx = q.x + 10*dpr, ly = q.y - 10*dpr;
      ctx.fillText(`alt ${alt} km  Rc ${cur.rc == null ? "—" : cur.rc.toFixed(2)} GV`, lx, ly);
      if (cur.epoch) { ctx.fillStyle = "#7f93ab"; ctx.fillText(String(cur.epoch).slice(0, 26), lx, ly + 13*dpr); }
    }

    raf = requestAnimationFrame(draw);
  }

  canvas.addEventListener("pointerdown", e => {
    canvas.setPointerCapture(e.pointerId);
    drag = { x: e.clientX, y: e.clientY, yaw: cam.yaw, pitch: cam.pitch };
  });
  canvas.addEventListener("pointermove", e => {
    if (!drag) return;
    cam.yaw = drag.yaw + (e.clientX - drag.x) * 0.008;
    cam.pitch = Math.max(-1.4, Math.min(1.4, drag.pitch - (e.clientY - drag.y) * 0.008));
  });
  canvas.addEventListener("pointerup", () => { drag = null; });
  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    cam.k = Math.max(8, Math.min(400, cam.k * (e.deltaY < 0 ? 1.12 : 0.89)));
  }, { passive: false });

  raf = requestAnimationFrame(draw);
  return {
    push(rec) {                                    /* rec: {ecef_km|lat,lon,alt, env, rc, epoch} */
      const p = rec.ecef_km || lla2ecef(rec.lat_deg ?? rec.lat, rec.lon_deg ?? rec.lon, rec.alt_km ?? rec.alt);
      track.push({ p, env: rec.env || rec.environment_tag, rc: rec.rc ?? rec.cutoff_gv, epoch: rec.epoch });
      if (track.length > 1800) track.splice(0, track.length - 1800);
      if (followOn && track.length) {
        const r = V.len(track[track.length-1].p) / RE;
        const fit = Math.min(canvas.clientWidth, canvas.clientHeight) * 0.42 / r;
        cam.k = Math.max(cam.k, Math.min(400, fit));
      }
    },
    clear() { track.length = 0; },
    /* 平台传播的轨道：整条载入 + 光标飞行控制 */
    setOrbit(pts) {
      orbit.length = 0; orbitCur = 0;
      for (const rec of pts) {
        const p = rec.ecef_km || lla2ecef(rec.lat_deg ?? rec.lat, rec.lon_deg ?? rec.lon, rec.alt_km ?? rec.alt);
        orbit.push({ p, env: rec.env || rec.environment_tag, rc: rec.rc ?? rec.cutoff_gv, epoch: rec.epoch });
      }
      if (followOn && orbit.length) {
        const r = V.len(orbit.reduce((m, o) => V.len(o.p) > V.len(m.p) ? o : m, orbit[0]).p) / RE;
        cam.k = Math.min(400, Math.min(canvas.clientWidth, canvas.clientHeight) * 0.42 / r);
      }
    },
    clearOrbit() { orbit.length = 0; orbitFly = false; },
    fly(v) { orbitFly = !!v; },
    speed(v) { orbitSpd = Math.max(1, +v || 30); },
    follow(v) { followOn = !!v; },
    saaBox: SAA,
    envColor: ENV_COLOR, envLabel: ENV_LABEL,
    stop() { cancelAnimationFrame(raf); }
  };
};
})();

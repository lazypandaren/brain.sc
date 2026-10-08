(() => {
  const canvas = document.getElementById("graph");
  const ctx = canvas.getContext("2d");
  const searchInput = document.getElementById("search");
  const panel = document.getElementById("panel");
  const panelTitle = document.getElementById("panel-title");
  const panelTldr = document.getElementById("panel-tldr");
  const panelMeta = document.getElementById("panel-meta");
  const panelTags = document.getElementById("panel-tags");
  const panelBody = document.getElementById("panel-body");

  let nodes = [];
  let edges = [];
  let hits = new Set();
  let selected = null;
  let pulse = 0;
  let unlocked = false;
  let hasPassword = true;
  let dragging = null;
  let panning = null; // { lx, ly } last screen coords while panning the map
  let transform = { x: 0, y: 0, k: 1 };
  let filterFocus = null; // null | { type: "hub"|"tag"|"mode", id: string }
  let panelCard = null; // last opened card payload
  let linkSuggestions = []; // [{id,title}]
  let physicsLeft = 0;
  let animPaused = false;
  let cachedById = null;

  function wakePhysics(frames) {
    physicsLeft = Math.max(physicsLeft, frames == null ? 150 : frames);
    cachedById = null;
  }

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + "px";
    canvas.style.height = rect.height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  async function api(path, opts) {
    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function hash01(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0) / 4294967295;
  }

  function isFresh(updated) {
    if (!updated) return false;
    const raw = String(updated);
    let t;
    if (raw.length <= 10) {
      t = Date.parse(raw + "T00:00:00Z");
    } else {
      t = Date.parse(raw);
    }
    if (Number.isNaN(t)) return false;
    return Date.now() - t <= 24 * 3600 * 1000;
  }

  // Hub-centric neural clusters (project hubs + related cards around them)
  function makeDendrites(seed, i) {
    const dendrites = [];
    const count = 5 + (i % 3);
    for (let d = 0; d < count; d++) {
      dendrites.push({
        a: (d / count) * Math.PI * 2 + hash01(seed + ":d" + d) * 0.55,
        len: 10 + hash01(seed + ":l" + d) * 10,
        bend: (hash01(seed + ":b" + d) - 0.5) * 0.9,
      });
    }
    return dendrites;
  }

  function buildAdj(edgeList) {
    const adj = new Map();
    const add = (a, b) => {
      if (!adj.has(a)) adj.set(a, new Set());
      if (!adj.has(b)) adj.set(b, new Set());
      adj.get(a).add(b);
      adj.get(b).add(a);
    };
    for (const e of edgeList) add(e.source, e.target);
    return adj;
  }

  function nearestHubId(startId, hubIds, adj) {
    const hubSet = new Set(hubIds);
    if (hubSet.has(startId)) return startId;
    const q = [startId];
    const seen = new Set([startId]);
    while (q.length) {
      const cur = q.shift();
      for (const nb of adj.get(cur) || []) {
        if (seen.has(nb)) continue;
        if (hubSet.has(nb)) return nb;
        seen.add(nb);
        q.push(nb);
      }
    }
    return hubIds[0] || null;
  }

  function initPhysics(graph, opts) {
    const keepPositions = !!(opts && opts.keepPositions);
    const prev = keepPositions
      ? new Map(nodes.map((n) => [n.id, { x: n.x, y: n.y, home: n.home }]))
      : null;
    const w = canvas.clientWidth || 800;
    const h = canvas.clientHeight || 600;
    const cx = w * 0.5, cy = h * 0.5;

    const idSet = new Set(graph.nodes.map((n) => n.id));
    edges = graph.edges.filter((e) => idSet.has(e.source) && idSet.has(e.target));
    const adj = buildAdj(edges);

    // Red hubs are cards tagged hub, not the 12 busiest nodes.
    let hubIds = graph.nodes
      .filter((n) => (n.tags || []).includes("hub"))
      .map((n) => n.id);
    const hubSet = new Set(hubIds);

    // Place hubs on a soft ring — space between project clusters
    const hubRing = Math.min(w, h) * 0.30;
    nodes = graph.nodes.map((n, i) => {
      const isHub = hubSet.has(n.id);
      return {
        ...n,
        hub: isHub,
        fresh: isFresh(n.updated),
        home: null,
        x: cx,
        y: cy,
        vx: 0,
        vy: 0,
        dendrites: makeDendrites(n.id, i),
        phase: hash01(n.id + ":p") * Math.PI * 2,
      };
    });
    const byId = nodeMap();

    if (hubIds.length === 0) {
      // No tag=hub yet — still show every card in a soft cloud (don't blank the graph)
      const ring = Math.min(w, h) * 0.28;
      nodes.forEach((n, i) => {
        const ang = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
        const rad = ring * (0.35 + hash01(n.id + ":nr") * 0.9);
        n.x = cx + Math.cos(ang) * rad;
        n.y = cy + Math.sin(ang) * rad;
      });
    } else {
      hubIds.forEach((hid, i) => {
        const n = byId.get(hid);
        if (!n) return;
        const ang = (i / hubIds.length) * Math.PI * 2 - Math.PI / 2;
        const jitter = (hash01(hid + ":hj") - 0.5) * 36;
        n.x = cx + Math.cos(ang) * hubRing + jitter;
        n.y = cy + Math.sin(ang) * hubRing + jitter * 0.7;
        n.home = hid;
      });

      // Assign each card to a home hub (prefer linked hub)
      for (const n of nodes) {
        if (hubSet.has(n.id)) continue;
        let best = null, bestScore = -1;
        for (const nb of adj.get(n.id) || []) {
          if (!hubSet.has(nb)) continue;
          const hn = byId.get(nb);
          const score = (hn && hn.degree) || 0;
          if (score > bestScore) {
            bestScore = score;
            best = nb;
          }
        }
        n.home = best || nearestHubId(n.id, hubIds, adj) || hubIds[0];
      }

      // Orbit satellites around their home hub
      const members = new Map();
      for (const n of nodes) {
        const hid = n.home || hubIds[0];
        if (!members.has(hid)) members.set(hid, []);
        members.get(hid).push(n);
      }
      for (const [hid, list] of members) {
        const hub = byId.get(hid);
        if (!hub) continue;
        const sats = list.filter((n) => n.id !== hid);
        const baseR = 78 + Math.min(70, sats.length * 4);
        sats.forEach((n, i) => {
          const ang = (i / Math.max(sats.length, 1)) * Math.PI * 2 + hash01(n.id + ":o") * 0.4;
          const rad = baseR * (0.65 + hash01(n.id + ":rr") * 0.7);
          n.x = hub.x + Math.cos(ang) * rad;
          n.y = hub.y + Math.sin(ang) * rad;
        });
      }
    }

    if (prev) {
      for (const n of nodes) {
        const p = prev.get(n.id);
        if (p) {
          n.x = p.x;
          n.y = p.y;
        }
      }
    }

    unlocked = graph.unlocked;
    updateUnlockBtn();
    refreshFilterControls();
    fillLinkSuggestions();
    wakePhysics(180);
  }

  function nodeMap() {
    const m = new Map();
    for (const n of nodes) m.set(n.id, n);
    return m;
  }

  function nodeById(id) {
    return nodes.find((n) => n.id === id);
  }

  function nodeInFocus(n) {
    if (!filterFocus) return true;
    if (filterFocus.type === "hub") {
      return n.id === filterFocus.id || n.home === filterFocus.id;
    }
    if (filterFocus.type === "tag") {
      return (n.tags || []).includes(filterFocus.id);
    }
    if (filterFocus.type === "mode") {
      if (filterFocus.id === "hubs") return !!n.hub;
      if (filterFocus.id === "orphans") return !!n.orphan;
    }
    return true;
    return true;
  }

  function fitNodes(list, pad) {
    const group = list && list.length ? list : nodes;
    if (!group.length) return;
    const margin = pad == null ? 72 : pad;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of group) {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.x > maxX) maxX = n.x;
      if (n.y > maxY) maxY = n.y;
    }
    const bw = Math.max(maxX - minX, 40);
    const bh = Math.max(maxY - minY, 40);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const k = Math.min(2.4, Math.max(0.35, Math.min((w - margin * 2) / bw, (h - margin * 2) / bh)));
    transform.k = k;
    transform.x = w / 2 - ((minX + maxX) / 2) * k;
    transform.y = h / 2 - ((minY + maxY) / 2) * k;
  }

  function focusCluster(hubId) {
    filterFocus = { type: "hub", id: hubId };
    const members = nodes.filter((n) => n.id === hubId || n.home === hubId);
    fitNodes(members);
    const hubSel = document.getElementById("filter-hub");
    const tagSel = document.getElementById("filter-tag");
    if (hubSel) hubSel.value = hubId;
    if (tagSel) tagSel.value = "";
  }

  function refreshFilterControls() {
    const hubSel = document.getElementById("filter-hub");
    const tagSel = document.getElementById("filter-tag");
    if (!hubSel || !tagSel) return;
    const hubs = nodes.filter((n) => n.hub).sort((a, b) => a.title.localeCompare(b.title));
    const tags = new Set();
    for (const n of nodes) for (const t of n.tags || []) tags.add(t);
    const hubVal = filterFocus && filterFocus.type === "hub" ? filterFocus.id : "";
    const tagVal = filterFocus && filterFocus.type === "tag" ? filterFocus.id : "";
    hubSel.innerHTML = '<option value="">Усі хаби</option>' + hubs.map((h) =>
      `<option value="${escapeHtml(h.id)}">${escapeHtml(h.title.slice(0, 40))}</option>`
    ).join("");
    tagSel.innerHTML = '<option value="">Усі теги</option>' + [...tags].sort().map((t) =>
      `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`
    ).join("");
    hubSel.value = hubVal;
    tagSel.value = tagVal;
  }

  function fillLinkSuggestions() {
    linkSuggestions = nodes.map((n) => ({ id: n.id, title: n.title || n.id }));
    const dl = document.getElementById("link-suggestions");
    if (!dl) return;
    dl.innerHTML = linkSuggestions.map((s) =>
      `<option value="${escapeHtml(s.id)}">${escapeHtml(s.title)}</option>`
    ).join("");
  }

  function resolveLinkTarget(raw) {
    const q = String(raw || "").trim().toLowerCase();
    if (!q) return null;
    const exact = linkSuggestions.find((s) => s.id.toLowerCase() === q);
    if (exact) return exact.id;
    const byTitle = linkSuggestions.find((s) => (s.title || "").toLowerCase() === q);
    if (byTitle) return byTitle.id;
    const partial = linkSuggestions.find((s) =>
      s.id.toLowerCase().includes(q) || (s.title || "").toLowerCase().includes(q)
    );
    return partial ? partial.id : null;
  }

  function tick() {
    if (physicsLeft <= 0 && !dragging) return;
    if (physicsLeft > 0) physicsLeft--;

    const byId = cachedById || nodeMap();
    cachedById = byId;
    const cutoff2 = 340 * 340;

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        const dist2 = dx * dx + dy * dy;
        const bothHub = a.hub && b.hub;
        if (!bothHub && dist2 > cutoff2) continue;
        let dist = Math.sqrt(dist2) || 0.01;
        const same = a.home && a.home === b.home;
        let minD = same ? 42 : 70;
        if (bothHub) minD = 140;
        const repulse = bothHub ? 9000 : same ? 2200 : 4800;
        const force = repulse / (dist * dist) + (dist < minD ? (minD - dist) * 0.5 : 0);
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        a.vx += dx; a.vy += dy;
        b.vx -= dx; b.vy -= dy;
      }
    }

    for (const e of edges) {
      const a = byId.get(e.source), b = byId.get(e.target);
      if (!a || !b) continue;
      let dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const homeEdge = (a.home === b.id && b.hub) || (b.home === a.id && a.hub);
      const sameCluster = a.home && a.home === b.home;
      let target = 150;
      let kSpring = 0.014;
      if (homeEdge) { target = 95; kSpring = 0.035; }
      else if (sameCluster) { target = 110; kSpring = 0.02; }
      else if (a.hub && b.hub) { target = 220; kSpring = 0.008; }
      const force = (dist - target) * kSpring;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      a.vx += dx; a.vy += dy;
      b.vx -= dx; b.vy -= dy;
    }

    for (const n of nodes) {
      if (n.hub || !n.home) continue;
      const hub = byId.get(n.home);
      if (!hub) continue;
      n.vx += (hub.x - n.x) * 0.006;
      n.vy += (hub.y - n.y) * 0.006;
    }

    const w = canvas.clientWidth, h = canvas.clientHeight;
    let energy = 0;
    for (const n of nodes) {
      n.vx += (w / 2 - n.x) * 0.00035;
      n.vy += (h / 2 - n.y) * 0.00035;
      if (dragging !== n) {
        n.vx *= 0.82;
        n.vy *= 0.82;
        n.x += n.vx;
        n.y += n.vy;
      }
      energy += n.vx * n.vx + n.vy * n.vy;
    }
    if (!dragging && energy < 0.04) physicsLeft = Math.min(physicsLeft, 1);
  }

  function draw() {
    if (animPaused || document.hidden) {
      requestAnimationFrame(draw);
      return;
    }
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    pulse += 0.04;
    tick();

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);
    ctx.lineCap = "round";
    ctx.shadowBlur = 0;

    const byId = cachedById || nodeMap();

    // --- axons + impulses (all edges) ---
    for (const e of edges) {
      const a = byId.get(e.source), b = byId.get(e.target);
      if (!a || !b) continue;
      const active = nodeInFocus(a) || nodeInFocus(b);
      ctx.globalAlpha = filterFocus && !active ? 0.08 : 1;
      const hit = hits.has(a.id) || hits.has(b.id);
      const hubEdge = a.hub || b.hub;
      const mx = (a.x + b.x) / 2 + (a.y - b.y) * 0.12;
      const my = (a.y + b.y) / 2 + (b.x - a.x) * 0.12;

      const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
      if (hit) {
        grad.addColorStop(0, "rgba(255, 122, 217, " + (0.65 + 0.2 * Math.sin(pulse)) + ")");
        grad.addColorStop(1, "rgba(122, 215, 240, " + (0.65 + 0.2 * Math.cos(pulse)) + ")");
      } else if (hubEdge) {
        grad.addColorStop(0, "rgba(255, 120, 180, 0.35)");
        grad.addColorStop(1, "rgba(100, 210, 240, 0.4)");
      } else {
        grad.addColorStop(0, "rgba(80, 200, 230, 0.28)");
        grad.addColorStop(0.5, "rgba(140, 220, 245, 0.38)");
        grad.addColorStop(1, "rgba(80, 200, 230, 0.28)");
      }
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.quadraticCurveTo(mx, my, b.x, b.y);
      ctx.strokeStyle = grad;
      ctx.lineWidth = hit ? 2.2 : hubEdge ? 1.35 : 1.1;
      ctx.stroke();

      // traveling impulse on every axon
      const t = (Math.sin(pulse * (hit ? 1.6 : 0.7) + a.phase) + 1) / 2;
      const it = 1 - t;
      const px = it * it * a.x + 2 * it * t * mx + t * t * b.x;
      const py = it * it * a.y + 2 * it * t * my + t * t * b.y;
      ctx.beginPath();
      ctx.arc(px, py, hit ? 3 : 1.8, 0, Math.PI * 2);
      ctx.fillStyle = hit ? "#ff7ad9" : "rgba(180, 240, 255, 0.9)";
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // --- somas + dendrites (all neurons) ---
    for (const n of nodes) {
      const active = nodeInFocus(n);
      ctx.globalAlpha = filterFocus && !active ? 0.12 : 1;
      const hit = hits.has(n.id) || selected === n.id;
      const fresh = n.fresh;
      const hub = !!n.hub;
      const locked = n.secure && !unlocked;
      const r = hit ? 12 : hub ? 10 : fresh ? 8 : 7;
      const breathe = 1 + 0.12 * Math.sin(pulse * 0.9 + n.phase);

      ctx.strokeStyle = locked
        ? "rgba(122, 140, 152, 0.35)"
        : hit ? "rgba(255, 160, 226, 0.7)"
        : hub ? "rgba(255, 140, 190, 0.55)"
        : fresh ? "rgba(255, 255, 255, 0.45)"
        : "rgba(122, 215, 240, 0.4)";
      ctx.lineWidth = hub ? 1.2 : 1;
      for (const d of n.dendrites || []) {
        const wobble = 0.15 * Math.sin(pulse * 0.6 + n.phase + d.a * 3);
        const a1 = d.a + wobble;
        const ex = n.x + Math.cos(a1) * (r + d.len);
        const ey = n.y + Math.sin(a1) * (r + d.len);
        const cx2 = n.x + Math.cos(a1 + d.bend) * (r + d.len * 0.5);
        const cy2 = n.y + Math.sin(a1 + d.bend) * (r + d.len * 0.5);
        ctx.beginPath();
        ctx.moveTo(n.x + Math.cos(a1) * r, n.y + Math.sin(a1) * r);
        ctx.quadraticCurveTo(cx2, cy2, ex, ey);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(ex, ey, 1.35, 0, Math.PI * 2);
        ctx.fillStyle = ctx.strokeStyle;
        ctx.fill();
      }

      const halo = ctx.createRadialGradient(n.x, n.y, r * 0.35, n.x, n.y, (r + (hub ? 18 : 14)) * breathe);
      if (locked) {
        halo.addColorStop(0, "rgba(122, 140, 152, 0.22)");
      } else if (hit) {
        halo.addColorStop(0, "rgba(255, 122, 217, 0.35)");
      } else if (hub) {
        halo.addColorStop(0, "rgba(255, 90, 160, 0.35)");
      } else if (fresh) {
        halo.addColorStop(0, "rgba(255, 255, 255, 0.28)");
      } else {
        halo.addColorStop(0, "rgba(90, 210, 240, 0.22)");
      }
      halo.addColorStop(1, "rgba(0,0,0,0)");
      ctx.beginPath();
      ctx.arc(n.x, n.y, (r + (hub ? 18 : 14)) * breathe, 0, Math.PI * 2);
      ctx.fillStyle = halo;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      const g = ctx.createRadialGradient(n.x - 2, n.y - 2, 1, n.x, n.y, r);
      if (locked) {
        g.addColorStop(0, "#5a6a72");
        g.addColorStop(1, "#2a353c");
      } else if (hit) {
        g.addColorStop(0, "#ffd6f2");
        g.addColorStop(1, "#ff7ad9");
      } else if (hub) {
        g.addColorStop(0, "#ffc4d8");
        g.addColorStop(0.45, "#ff5a9a");
        g.addColorStop(1, "#e01e6a");
      } else if (fresh) {
        g.addColorStop(0, "#ffffff");
        g.addColorStop(0.55, "#eef8ff");
        g.addColorStop(1, "#8fd4f0");
      } else {
        g.addColorStop(0, "#b8f0ff");
        g.addColorStop(1, "#3eb8e0");
      }
      ctx.fillStyle = g;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(n.x - r * 0.25, n.y - r * 0.25, r * 0.3, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
      ctx.fill();

      const showLabel = hit || hub || transform.k >= 1.4;
      if (showLabel && (active || !filterFocus)) {
        ctx.fillStyle = hub ? "#ffb3c9" : hit || fresh ? "#fff" : "rgba(220, 240, 250, 0.88)";
        ctx.font = (hub || hit ? "600 " : "500 ") + (hub ? "13" : "12") + 'px "IBM Plex Sans", sans-serif';
        ctx.fillText(n.title.slice(0, hub ? 30 : 26), n.x + r + 12, n.y + 4);
      }
    }
    ctx.globalAlpha = 1;
    ctx.restore();
    requestAnimationFrame(draw);
  }

  function screenToWorld(sx, sy) {
    return {
      x: (sx - transform.x) / transform.k,
      y: (sy - transform.y) / transform.k,
    };
  }

  function pick(sx, sy) {
    const p = screenToWorld(sx, sy);
    let best = null, bestD = 16;
    for (const n of nodes) {
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d < bestD) { best = n; bestD = d; }
    }
    return best;
  }

  canvas.addEventListener("pointerdown", (ev) => {
    const n = pick(ev.offsetX, ev.offsetY);
    if (n) {
      dragging = n;
      panning = null;
      wakePhysics(90);
      canvas.setPointerCapture(ev.pointerId);
      openCard(n.id);
      return;
    }
    // empty space / middle button / Alt → pan the map
    if (ev.button === 0 || ev.button === 1 || ev.altKey) {
      panning = { lx: ev.offsetX, ly: ev.offsetY };
      dragging = null;
      canvas.setPointerCapture(ev.pointerId);
      canvas.style.cursor = "grabbing";
    }
  });
  canvas.addEventListener("pointermove", (ev) => {
    if (panning) {
      transform.x += ev.offsetX - panning.lx;
      transform.y += ev.offsetY - panning.ly;
      panning.lx = ev.offsetX;
      panning.ly = ev.offsetY;
      return;
    }
    if (!dragging) return;
    const p = screenToWorld(ev.offsetX, ev.offsetY);
    dragging.x = p.x;
    dragging.y = p.y;
    dragging.vx = 0;
    dragging.vy = 0;
  });
  canvas.addEventListener("pointerup", () => {
    dragging = null;
    panning = null;
    canvas.style.cursor = "";
  });
  canvas.addEventListener("pointercancel", () => {
    dragging = null;
    panning = null;
    canvas.style.cursor = "";
  });
  // Zoom toward cursor (not world origin / top-left)
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const factor = ev.deltaY > 0 ? 0.92 : 1.08;
    const oldK = transform.k;
    const newK = Math.min(4, Math.max(0.25, oldK * factor));
    if (newK === oldK) return;
    const mx = ev.offsetX, my = ev.offsetY;
    transform.x = mx - (mx - transform.x) * (newK / oldK);
    transform.y = my - (my - transform.y) * (newK / oldK);
    transform.k = newK;
  }, { passive: false });
  canvas.addEventListener("dblclick", (ev) => {
    const n = pick(ev.offsetX, ev.offsetY);
    if (n) {
      if (n.hub) focusCluster(n.id);
      else if (n.home) focusCluster(n.home);
      openCard(n.id);
      return;
    }
    fitNodes(nodes);
  });

  function renderPanelLinks(card) {
    const list = document.getElementById("panel-links");
    const err = document.getElementById("link-err");
    if (err) err.textContent = "";
    if (!list) return;
    const links = card.links || [];
    if (!links.length) {
      list.innerHTML = '<li class="empty">No outbound links — add below or use [[wiki-links]] in the body</li>';
      return;
    }
    list.innerHTML = links.map((id) => {
      const n = nodeById(id);
      const label = n ? n.title : id;
      return `<li>
        <button type="button" class="link-open" data-id="${escapeHtml(id)}">${escapeHtml(label)}</button>
        <button type="button" class="link-unlink" data-id="${escapeHtml(id)}" title="Unlink">×</button>
      </li>`;
    }).join("");
    list.querySelectorAll(".link-open").forEach((btn) => {
      btn.onclick = () => openCard(btn.getAttribute("data-id"));
    });
    list.querySelectorAll(".link-unlink").forEach((btn) => {
      btn.onclick = async () => {
        if (!panelCard) return;
        try {
          await api("/api/unlink", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ a: panelCard.id, b: btn.getAttribute("data-id") }),
          });
          await reload({ keepPositions: true });
          await openCard(panelCard.id);
        } catch (e) {
          if (err) err.textContent = e.message;
        }
      };
    });
  }

  function renderPanelBacklinks(card) {
    const list = document.getElementById("panel-backlinks");
    if (!list) return;
    const bl = card.backlinks || [];
    if (!bl.length) {
      list.innerHTML = '<li class="empty">No backlinks yet</li>';
      return;
    }
    list.innerHTML = bl.map((b) => {
      const id = b.id || b;
      const label = b.title || id;
      return `<li><button type="button" class="link-open" data-id="${escapeHtml(id)}">${escapeHtml(label)}</button></li>`;
    }).join("");
    list.querySelectorAll(".link-open").forEach((btn) => {
      btn.onclick = () => openCard(btn.getAttribute("data-id"));
    });
  }

  async function openCard(id) {
    selected = id;
    try {
      const card = await api("/api/card/" + encodeURIComponent(id));
      panelCard = card;
      panel.classList.remove("hidden");
      panelTitle.textContent = card.title;
      panelTldr.textContent = card.tldr;
      panelMeta.textContent = (card.secure ? "secure · " : "") + (card.id + (card.updated ? " · " + card.updated : ""));
      panelTags.innerHTML = (card.tags || []).map((t) =>
        `<span data-tag="${escapeHtml(t)}">${escapeHtml(t)}</span>`
      ).join("");
      panelTags.querySelectorAll("[data-tag]").forEach((el) => {
        el.onclick = () => {
          filterFocus = { type: "tag", id: el.getAttribute("data-tag") };
          const hubSel = document.getElementById("filter-hub");
          const tagSel = document.getElementById("filter-tag");
          if (hubSel) hubSel.value = "";
          if (tagSel) tagSel.value = filterFocus.id;
          const members = nodes.filter((n) => nodeInFocus(n));
          fitNodes(members);
        };
      });
      renderPanelLinks(card);
      renderPanelBacklinks(card);
      panelBody.textContent = card.body || "";
      focusNode(id);
    } catch (e) {
      panelCard = null;
      panel.classList.remove("hidden");
      panelTitle.textContent = id;
      panelTldr.textContent = e.message;
      panelMeta.textContent = "locked / error";
      panelTags.innerHTML = "";
      const list = document.getElementById("panel-links");
      if (list) list.innerHTML = "";
      const bl = document.getElementById("panel-backlinks");
      if (bl) bl.innerHTML = "";
      panelBody.textContent = "";
    }
  }

  function focusNode(id) {
    const n = nodeById(id);
    if (!n) return;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    transform.x = w / 2 - n.x * transform.k;
    transform.y = h / 2 - n.y * transform.k;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  let searchTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, 80);
  });
  searchInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && hits.size) {
      openCard([...hits][0]);
    }
  });

  async function runSearch() {
    const q = searchInput.value.trim();
    if (!q) { hits = new Set(); return; }
    const data = await api("/api/search?q=" + encodeURIComponent(q) + "&limit=20");
    hits = new Set((data.results || []).map((r) => r.id));
    if (hits.size === 1) focusNode([...hits][0]);
  }

  document.getElementById("panel-close").onclick = () => {
    panel.classList.add("hidden");
    selected = null;
    panelCard = null;
  };

  document.getElementById("link-add-btn").onclick = async () => {
    const err = document.getElementById("link-err");
    if (!panelCard) {
      if (err) err.textContent = "Спочатку відкрий картку";
      return;
    }
    const raw = document.getElementById("link-target").value;
    const target = resolveLinkTarget(raw);
    if (!target) {
      if (err) err.textContent = "Картку не знайдено";
      return;
    }
    if (target === panelCard.id) {
      if (err) err.textContent = "Не можна звʼязати з собою";
      return;
    }
    try {
      await api("/api/link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ a: panelCard.id, b: target }),
      });
      document.getElementById("link-target").value = "";
      if (err) err.textContent = "";
      await reload({ keepPositions: true });
      await openCard(panelCard.id);
    } catch (e) {
      if (err) err.textContent = e.message;
    }
  };

  document.getElementById("filter-hub").onchange = (ev) => {
    const v = ev.target.value;
    const tagSel = document.getElementById("filter-tag");
    const modeSel = document.getElementById("filter-mode");
    if (tagSel) tagSel.value = "";
    if (modeSel) modeSel.value = "";
    if (!v) {
      filterFocus = null;
      return;
    }
    focusCluster(v);
  };
  document.getElementById("filter-tag").onchange = (ev) => {
    const v = ev.target.value;
    const hubSel = document.getElementById("filter-hub");
    const modeSel = document.getElementById("filter-mode");
    if (hubSel) hubSel.value = "";
    if (modeSel) modeSel.value = "";
    if (!v) {
      filterFocus = null;
      return;
    }
    filterFocus = { type: "tag", id: v };
    fitNodes(nodes.filter((n) => nodeInFocus(n)));
  };
  const filterMode = document.getElementById("filter-mode");
  if (filterMode) {
    filterMode.onchange = (ev) => {
      const v = ev.target.value;
      const hubSel = document.getElementById("filter-hub");
      const tagSel = document.getElementById("filter-tag");
      if (hubSel) hubSel.value = "";
      if (tagSel) tagSel.value = "";
      if (!v) {
        filterFocus = null;
        fitNodes(nodes);
        return;
      }
      filterFocus = { type: "mode", id: v };
      fitNodes(nodes.filter((n) => nodeInFocus(n)));
    };
  }
  document.getElementById("btn-fit").onclick = () => {
    const members = filterFocus ? nodes.filter((n) => nodeInFocus(n)) : nodes;
    fitNodes(members);
  };
  document.getElementById("btn-filter-clear").onclick = () => {
    filterFocus = null;
    const hubSel = document.getElementById("filter-hub");
    const tagSel = document.getElementById("filter-tag");
    const modeSel = document.getElementById("filter-mode");
    if (hubSel) hubSel.value = "";
    if (tagSel) tagSel.value = "";
    if (modeSel) modeSel.value = "";
    fitNodes(nodes);
  };
  const btnDaily = document.getElementById("btn-daily");
  if (btnDaily) {
    btnDaily.onclick = async () => {
      try {
        const data = await api("/api/daily", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        await reload({ keepPositions: true });
        await openCard(data.id);
      } catch (e) {
        console.error(e);
      }
    };
  }

  function updateUnlockBtn() {
    const btn = document.getElementById("btn-unlock");
    btn.textContent = unlocked ? "Lock" : (hasPassword ? "Unlock" : "Створити пароль");
  }

  document.getElementById("btn-unlock").onclick = async () => {
    if (unlocked) {
      await api("/api/lock", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      await refreshStatus();
      await reload();
      return;
    }
    const creating = !hasPassword;
    document.getElementById("unlock-title").textContent = creating ? "Створити мастер-пароль" : "Unlock secure";
    document.getElementById("unlock-note").textContent = creating
      ? "Пароль шифрує secure-картки. Мінімум 6 символів. Якщо забудеш — secure не відновити."
      : "Мастер-пароль лишається локально. Агент його не бачить.";
    document.getElementById("unlock-pass2").classList.toggle("hidden", !creating);
    document.getElementById("unlock-ok").textContent = creating ? "Створити" : "Unlock";
    document.getElementById("modal-unlock").classList.remove("hidden");
    document.getElementById("unlock-pass").value = "";
    document.getElementById("unlock-pass2").value = "";
    document.getElementById("unlock-err").textContent = "";
    document.getElementById("unlock-pass").focus();
  };
  document.getElementById("unlock-cancel").onclick = () => {
    document.getElementById("modal-unlock").classList.add("hidden");
  };
  document.getElementById("unlock-ok").onclick = async () => {
    const password = document.getElementById("unlock-pass").value;
    const creating = !hasPassword;
    try {
      if (creating) {
        const confirm = document.getElementById("unlock-pass2").value;
        await api("/api/set-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password, confirm }),
        });
      } else {
        await api("/api/unlock", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password }),
        });
      }
      document.getElementById("modal-unlock").classList.add("hidden");
      await refreshStatus();
      await reload();
    } catch (e) {
      document.getElementById("unlock-err").textContent = e.message;
    }
  };

  async function refreshStatus() {
    try {
      const st = await api("/api/status");
      hasPassword = !!st.has_password;
      unlocked = !!st.unlocked;
      updateUnlockBtn();
      return st;
    } catch (_) {
      return null;
    }
  }

  document.getElementById("btn-settings").onclick = async () => {
    const st = await api("/api/status");
    document.getElementById("root-path").value = st.root || "";
    document.getElementById("root-status").textContent = `cards: ${st.cards} · unlocked: ${st.unlocked}`;
    document.getElementById("settings-err").textContent = "";
    document.getElementById("doctor-out").classList.add("hidden");
    try {
      const cfg = await api("/api/config");
      document.getElementById("cfg-maxcards").value = cfg.max_cards_per_query;
      document.getElementById("cfg-detail").value = cfg.default_detail;
      document.getElementById("cfg-ttl").value = cfg.session_ttl_minutes;
      document.getElementById("cfg-port").value = cfg.ui_port;
    } catch (_) { /* config editable only when server is fresh */ }
    document.getElementById("modal-settings").classList.remove("hidden");
  };
  document.getElementById("settings-cancel").onclick = () => {
    document.getElementById("modal-settings").classList.add("hidden");
  };
  async function saveRoot(path, errEl, onOk) {
    const data = await api("/api/set-root", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, create: true }),
    });
    if (data.created) {
      notifyToast("Vault створено в цій папці");
    }
    onOk();
  }

  function notifyToast(msg) {
    try {
      document.getElementById("root-status").textContent = msg;
    } catch (_) { /* ignore */ }
  }

  document.getElementById("settings-save").onclick = async () => {
    const path = document.getElementById("root-path").value.trim();
    const errEl = document.getElementById("settings-err");
    try {
      await api("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_cards_per_query: Number(document.getElementById("cfg-maxcards").value) || 3,
          default_detail: document.getElementById("cfg-detail").value,
          session_ttl_minutes: Number(document.getElementById("cfg-ttl").value) || 60,
          ui_port: Number(document.getElementById("cfg-port").value) || 8765,
        }),
      });
      if (path) {
        await saveRoot(path, errEl, async () => {});
      }
      document.getElementById("modal-settings").classList.add("hidden");
      await reload();
    } catch (e) {
      errEl.textContent = e.message;
    }
  };

  document.getElementById("btn-reindex").onclick = async () => {
    const errEl = document.getElementById("settings-err");
    errEl.textContent = "Переіндексація… (граф на паузі)";
    animPaused = true;
    physicsLeft = 0;
    try {
      const data = await api("/api/reindex", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      errEl.textContent = `Проіндексовано карток: ${data.indexed}`;
      await reload({ keepPositions: true });
    } catch (e) {
      errEl.textContent = e.message;
    } finally {
      animPaused = false;
    }
  };
  document.getElementById("btn-doctor").onclick = async () => {
    const out = document.getElementById("doctor-out");
    out.classList.remove("hidden");
    out.textContent = "Перевіряю…";
    try {
      const r = await api("/api/doctor");
      const lines = [
        r.ok ? "OK — проблем не знайдено" : "Є проблеми:",
        ...r.issues.map((s) => "✖ " + s),
        ...r.warnings.map((s) => "⚠ " + s),
        ...r.info.map((s) => "· " + s),
      ];
      out.textContent = lines.join("\n");
    } catch (e) { out.textContent = e.message; }
  };
  document.getElementById("btn-reveal").onclick = async () => {
    try {
      await api("/api/reveal-root", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    } catch (e) {
      document.getElementById("settings-err").textContent = e.message;
    }
  };

  document.getElementById("btn-about").onclick = () => {
    document.getElementById("modal-about").classList.remove("hidden");
  };
  document.getElementById("about-close").onclick = () => {
    document.getElementById("modal-about").classList.add("hidden");
  };

  document.getElementById("import-run").onclick = async () => {
    const path = document.getElementById("import-path").value.trim();
    const errEl = document.getElementById("settings-err");
    if (!path) { errEl.textContent = "Absolute folder path required."; return; }
    errEl.textContent = "Importing…";
    try {
      const data = await api("/api/import-folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      errEl.textContent = `Imported cards: ${data.count}` +
        (data.skipped.length ? ` (skipped: ${data.skipped.length})` : "");
      await reload();
    } catch (e) {
      errEl.textContent = e.message;
    }
  };

  document.getElementById("import-topics-run").onclick = async () => {
    const path = document.getElementById("import-topics-path").value.trim();
    const errEl = document.getElementById("settings-err");
    if (!path) { errEl.textContent = "Absolute topics folder path required."; return; }
    errEl.textContent = "Importing topics…";
    try {
      const data = await api("/api/import-topics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      errEl.textContent = `Imported topics: ${data.count}` +
        (data.skipped.length ? ` (skipped: ${data.skipped.length})` : "");
      await reload();
    } catch (e) {
      errEl.textContent = e.message;
    }
  };

  // --- AI agents install ---
  async function installAgents(targets) {
    const errEl = document.getElementById("settings-err");
    errEl.textContent = "Connecting…";
    try {
      const data = await api("/api/agents-install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ targets }),
      });
      const names = Object.keys(data.installed).join(", ");
      errEl.textContent = `Connected: ${names}. Agents now know the Brain protocol.`;
    } catch (e) {
      errEl.textContent = e.message;
    }
  }
  document.querySelectorAll(".agent-btn").forEach((b) => {
    b.onclick = () => installAgents([b.dataset.target]);
  });
  document.getElementById("agents-all").onclick = () => installAgents(["cursor", "codex", "claude"]);

  // --- Feedback questionnaire ---
  const fbModal = document.getElementById("modal-feedback");
  const fbAnswers = {};

  // build yes/no toggle buttons for each question
  document.querySelectorAll("#fb-questions .fb-q").forEach((q) => {
    const key = q.dataset.key;
    const wrap = document.createElement("div");
    wrap.className = "fb-toggle";
    [["yes", "Так"], ["no", "Ні"]].forEach(([val, label]) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.onclick = () => {
        fbAnswers[key] = val === "yes";
        wrap.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
        b.classList.add("on");
      };
      wrap.appendChild(b);
    });
    q.appendChild(wrap);
  });

  document.getElementById("fb-score").oninput = (ev) => {
    document.getElementById("fb-score-val").textContent = ev.target.value;
  };

  document.getElementById("btn-feedback").onclick = () => {
    document.getElementById("fb-err").textContent = "";
    document.getElementById("fb-status").textContent = "";
    fbModal.classList.remove("hidden");
  };
  document.getElementById("fb-cancel").onclick = () => fbModal.classList.add("hidden");

  document.getElementById("fb-send").onclick = async () => {
    const errEl = document.getElementById("fb-err");
    const statusEl = document.getElementById("fb-status");
    errEl.textContent = "";
    statusEl.textContent = "Зберігаю…";
    try {
      const data = await api("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          answers: {
            ...fbAnswers,
            tester: document.getElementById("fb-tester").value.trim(),
            platform: document.getElementById("fb-platform").value.trim(),
            score: Number(document.getElementById("fb-score").value),
            top_fix: document.getElementById("fb-topfix").value.trim(),
          },
          comments: document.getElementById("fb-comments").value,
        }),
      });
      statusEl.textContent = `Збережено: ${data.path} — файл вже підсвічено у Finder, надішли його розробнику.`;
    } catch (e) {
      statusEl.textContent = "";
      errEl.textContent = e.message;
    }
  };

  // --- Dashboard ---
  const dash = document.getElementById("dashboard");
  let dashTimer = null;
  async function refreshDashboard() {
    try {
      const s = await api("/api/stats");
      renderDashboard(s);
    } catch (e) {
      document.getElementById("dash-kpis").innerHTML =
        `<div class="kpi"><b>—</b><span>${escapeHtml(e.message)}</span></div>`;
    }
  }
  document.getElementById("btn-dashboard").onclick = async () => {
    dash.classList.remove("hidden");
    await refreshDashboard();
    clearInterval(dashTimer);
    dashTimer = setInterval(refreshDashboard, 4000);
  };
  document.getElementById("dash-close").onclick = () => {
    dash.classList.add("hidden");
    clearInterval(dashTimer);
    dashTimer = null;
  };
  document.getElementById("dash-reset").onclick = async () => {
    try {
      await api("/api/usage-reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      await refreshDashboard();
    } catch (e) {
      document.getElementById("dash-kpis").innerHTML =
        `<div class="kpi"><b>—</b><span>${escapeHtml(e.message)}</span></div>`;
    }
  };

  const wbMsg = () => document.getElementById("wb-msg");
  document.getElementById("wb-remember-btn").onclick = async () => {
    const note = document.getElementById("wb-remember").value.trim();
    if (!note) { wbMsg().textContent = "Enter a short note."; return; }
    try {
      await api("/api/remember", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note, source: "ui" }),
      });
      document.getElementById("wb-remember").value = "";
      wbMsg().textContent = "Remembered.";
      await refreshDashboard();
    } catch (e) {
      wbMsg().textContent = e.message;
    }
  };
  document.getElementById("wb-add-btn").onclick = async () => {
    const id = document.getElementById("wb-slug").value.trim();
    const title = document.getElementById("wb-title").value.trim();
    const tldr = document.getElementById("wb-tldr").value.trim();
    if (!title && !tldr && !id) { wbMsg().textContent = "Title or TL;DR required."; return; }
    try {
      const data = await api("/api/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, title, tldr, tags: ["inbox"] }),
      });
      document.getElementById("wb-slug").value = "";
      document.getElementById("wb-title").value = "";
      document.getElementById("wb-tldr").value = "";
      wbMsg().textContent = `Card saved: ${data.id}`;
      await refreshDashboard();
      await reload();
    } catch (e) {
      wbMsg().textContent = e.message;
    }
  };

  function fmtTokens(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
    return String(n);
  }

  function renderDashboard(s) {
    document.getElementById("dash-kpis").innerHTML = [
      [String(s.cards ?? 0), "карток у vault"],
      [String(s.fresh_24h ?? 0), "оновлено за 24 години"],
      [String(s.writes_today ?? 0), "записів сьогодні (UTC)"],
      [String(s.writes_14d ?? 0), "записів за 14 днів"],
      [String(s.orphans ?? 0), "без звʼязків"],
      [`${s.savings_pct ?? 0}%`, "економія vs full vault"],
    ].map(([v, l]) => `<div class="kpi"><b>${escapeHtml(String(v))}</b><span>${escapeHtml(l)}</span></div>`).join("");

    const health = [
      ["Secure-карток", s.secure],
      ["Inbox", s.inbox],
      ["Битих лінків", s.broken_links],
      ["Застарілих (>90д)", s.stale_cards],
    ];
    document.getElementById("dash-health").innerHTML = health
      .map(([l, v]) => `<li><span>${escapeHtml(l)}</span><b class="${v && String(l).includes("Битих") ? "warn" : ""}">${v}</b></li>`)
      .join("");

    const maxTag = Math.max(1, ...(s.top_tags || []).map(([, n]) => n));
    document.getElementById("dash-tags").innerHTML = (s.top_tags || [])
      .map(([t, n]) => `<li><span>${escapeHtml(t)}</span><i style="width:${Math.round((n / maxTag) * 100)}%"></i><b>${n}</b></li>`)
      .join("") || "<li><span>Тегів ще немає</span></li>";

    const recent = (s.recent_activity || []).slice().reverse();
    document.getElementById("dash-recent").innerHTML = recent.length
      ? recent.map((ev) => {
          const ts = String(ev.ts || "").replace("T", " ").slice(0, 16);
          const kind = ev.kind || "?";
          const slug = ev.slug || ev.detail || "";
          return `<li><span>${escapeHtml(ts)} · <b>${escapeHtml(kind)}</b> ${escapeHtml(slug)}</span></li>`;
        }).join("")
      : "<li><span>Ще немає записів activity — зроби brain add / link / remember</span></li>";

    document.getElementById("dash-memory").innerHTML = (s.memory_tail || [])
      .map((m) => `<li><span>${escapeHtml(m.replace(/^- /, ""))}</span></li>`)
      .join("") || "<li><span>Памʼять порожня</span></li>";

    document.getElementById("dash-tokens").innerHTML = [
      ["Типовий запит", fmtTokens(s.query_tokens)],
      ["Весь vault", fmtTokens(s.full_tokens)],
      ["Каталог", fmtTokens(s.catalog_tokens)],
      ["UI queries 14д", s.usage_queries_14d ?? 0],
    ].map(([l, v]) => `<li><span>${escapeHtml(l)}</span><b>${escapeHtml(String(v))}</b></li>`).join("");

    drawUsageChart(s.activity || []);
  }

  function drawUsageChart(activity) {
    const c = document.getElementById("dash-chart");
    const dpr = window.devicePixelRatio || 1;
    const w = c.parentElement.clientWidth - 8;
    const h = 160;
    c.width = w * dpr; c.height = h * dpr;
    c.style.width = w + "px"; c.style.height = h + "px";
    const g = c.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);

    const total = activity.reduce((s, u) => s + (u.total || 0), 0);
    if (!activity.length || total === 0) {
      g.fillStyle = "rgba(231, 242, 246, 0.55)";
      g.font = '12px "IBM Plex Sans", sans-serif';
      g.fillText("Немає записів за 14 днів — activity з’явиться після add/link/remember", 12, h / 2);
      return;
    }

    const pad = { l: 8, r: 8, t: 12, b: 20 };
    const iw = w - pad.l - pad.r;
    const maxT = Math.max(1, ...activity.map((u) => u.total || 0));
    const bw = Math.max(6, Math.floor(iw / activity.length) - 6);

    activity.forEach((u, i) => {
      const x = pad.l + (i / activity.length) * iw + 3;
      const bh = u.total ? Math.round(((h - pad.t - pad.b) * u.total) / maxT) : 0;
      g.fillStyle = u.total ? "rgba(122, 215, 240, 0.8)" : "rgba(122, 215, 240, 0.08)";
      g.fillRect(x, h - pad.b - Math.max(bh, u.total ? 3 : 1), bw, Math.max(bh, u.total ? 3 : 1));
      if (i % 3 === 0 || i === activity.length - 1) {
        g.fillStyle = "rgba(231, 242, 246, 0.5)";
        g.font = '10px "IBM Plex Sans", sans-serif';
        g.fillText(u.day.slice(5), x, h - 6);
      }
    });
  }

  document.getElementById("setup-save").onclick = async () => {
    const path = document.getElementById("setup-path").value.trim();
    try {
      await saveRoot(path, document.getElementById("setup-err"), async () => {
        document.getElementById("setup").classList.add("hidden");
        await reload();
      });
    } catch (e) {
      document.getElementById("setup-err").textContent = e.message;
    }
  };

  window.addEventListener("keydown", (ev) => {
    if (ev.key === "/" && document.activeElement !== searchInput) {
      ev.preventDefault();
      searchInput.focus();
    }
  });

  async function reload(opts) {
    // Always refresh password/unlock state first so the header button is correct
    await refreshStatus();
    const graph = await api("/api/graph");
    initPhysics(graph, opts || {});
  }

  async function boot() {
    resize();
    window.addEventListener("resize", resize);
    try {
      const st = await api("/api/status");
      hasPassword = !!st.has_password;
      if (!st.ready && !st.root) {
        document.getElementById("setup").classList.remove("hidden");
      } else {
        document.getElementById("setup").classList.add("hidden");
        await reload();
      }
      requestAnimationFrame(draw);
    } catch (e) {
      document.getElementById("setup").classList.remove("hidden");
      document.getElementById("setup-err").textContent = e.message;
      requestAnimationFrame(draw);
    }
  }

  boot();
})();

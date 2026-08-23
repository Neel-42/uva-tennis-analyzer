let currentSlug = null;
let currentMatches = [];
let rosterPlayers = [];
let activeRosterName = null;

const $ = (sel) => document.querySelector(sel);

/** Empty on localhost (Flask serves API). Static bundle on GitHub Pages. */
const STATIC_MODE = document.querySelector('meta[name="static-mode"]')?.content === "1";
const API_BASE = (() => {
  if (STATIC_MODE) return "";
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta?.content) return meta.content.replace(/\/$/, "");
  return "";
})();

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

function staticUrl(path) {
  return `data/${path.replace(/^\//, "")}`;
}

function setStatus(msg, isError = false) {
  const el = $("#status");
  el.textContent = msg || "";
  el.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function pieRingSvg(pct, isLoss = false) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, pct));
  const dLen = (clamped / 100) * c;
  const oLen = c - dLen;
  const dc = isLoss ? "#e8956a" : "#3ecf8e";
  const oc = isLoss ? "#f07178" : "#4a5568";
  return (
    `<svg class="pie-svg" viewBox="0 0 120 120" aria-hidden="true">` +
    `<circle cx="60" cy="60" r="${r}" fill="none" stroke="${oc}" stroke-width="12"/>` +
    `<circle cx="60" cy="60" r="${r}" fill="none" stroke="${dc}" stroke-width="12" ` +
    `stroke-dasharray="${dLen.toFixed(1)} ${oLen.toFixed(1)}" transform="rotate(-90 60 60)"/>` +
    `</svg>`
  );
}

function matchPieSvg(playerPct, playerLabel, isLoss) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, playerPct));
  const dLen = (pct / 100) * c;
  const oLen = c - dLen;
  const dc = isLoss ? "#e8956a" : "#3ecf8e";
  const oc = isLoss ? "#f07178" : "#4a5568";
  return (
    `<svg class="pie-svg" viewBox="0 0 120 120" aria-hidden="true">` +
    `<circle cx="60" cy="60" r="${r}" fill="none" stroke="${oc}" stroke-width="12"/>` +
    `<circle cx="60" cy="60" r="${r}" fill="none" stroke="${dc}" stroke-width="12" ` +
    `stroke-dasharray="${dLen.toFixed(1)} ${oLen.toFixed(1)}" transform="rotate(-90 60 60)"/>` +
    `<text x="60" y="56" text-anchor="middle" fill="#e8eaed" font-size="20" font-weight="700">${pct}%</text>` +
    `<text x="60" y="72" text-anchor="middle" fill="#9aa3b2" font-size="9">${playerLabel}</text>` +
    `</svg>`
  );
}

function renderSummaryPieCell(cell) {
  const winnerClass = cell.highlight ? " winner" : "";
  return `
    <div class="summary-pie-cell${winnerClass}">
      <div class="summary-pie-title">${cell.title}</div>
      <div class="summary-pie-ring-wrap">
        ${pieRingSvg(cell.pct, false)}
        <div class="summary-pie-pct">${cell.pct}%</div>
      </div>
      <div class="summary-pie-footer">
        <span class="summary-pie-total">${cell.total}</span>
        <span class="summary-pie-caption">${cell.caption.toLowerCase()}</span>
      </div>
    </div>`;
}

function renderPieCharts(pc) {
  if (!pc?.modeled) return "";

  const pw = pc.pointsWon;
  const oppPct = pw.opponentPct ?? 100 - pw.playerPct;

  const mainPie = `
    <div class="answer-card">
      <h2>Points won</h2>
      <p class="verdict ${pw.isLoss ? "loss" : ""}">${pw.playerPct}% ${pw.playerLabel}</p>
      <div class="pie-wrap">
        ${matchPieSvg(pw.playerPct, pw.playerLabel, pw.isLoss)}
        <div class="pie-legend">
          <div><span class="dot" style="background:var(--success)"></span>${pw.playerLabel} ${pw.playerPct}%</div>
          <div><span class="dot" style="background:var(--muted)"></span>Opponent ${oppPct}%</div>
        </div>
      </div>
      <p class="pie-caption">${pw.source} · ~${pw.totalPoints} total points estimated</p>
    </div>`;

  const serveSection = `
    <div class="answer-card">
      <h2>Serving (deuce vs ad)</h2>
      <p class="verdict">${pc.serve.verdict}</p>
      <p>Top row = points won on each side; bottom row = T-serve share. Win % inside each ring; total points below.</p>
      <div class="summary-pie-grid">
        ${(pc.serve.cells || []).map(renderSummaryPieCell).join("")}
      </div>
    </div>`;

  const returnSection = `
    <div class="answer-card">
      <h2>Returning (deuce vs ad)</h2>
      <p class="verdict tie">${pc.return.verdict}</p>
      <p>Top row = return points won; bottom row = total return points on that side.</p>
      <div class="summary-pie-grid">
        ${(pc.return.cells || []).map(renderSummaryPieCell).join("")}
      </div>
    </div>`;

  return `
    <div class="callout">${pc.note}</div>
    ${mainPie}
    ${serveSection}
    ${returnSection}`;
}

function renderAnalysis(data) {
  const isWin = data.result === "W";
  const stats = data.stats || {};

  const statBoxes = [
    ["Dominance ratio", stats.dominanceRatio?.toFixed(2) ?? "—"],
    ["Ace %", stats.acePct != null ? `${stats.acePct}%` : "—"],
    ["DF %", stats.dfPct != null ? `${stats.dfPct}%` : "—"],
    ["1st serve in", stats.firstServeInPct != null ? `${stats.firstServeInPct}%` : "—"],
    ["1st serve won", stats.firstServeWonPct != null ? `${stats.firstServeWonPct}%` : "—"],
    ["2nd serve won", stats.secondServeWonPct != null ? `${stats.secondServeWonPct}%` : "—"],
    ["BP saved", stats.bpSaved ?? "—"],
    ["Duration", stats.duration ?? "—"],
  ];

  const pc = data.pieCharts || {};
  const pieHtml = renderPieCharts(pc);

  $("#analysis").innerHTML = `
    <div class="analysis-header">
      <h2>${data.player} vs ${data.opponent}</h2>
      <div class="pill-row">
        <span class="pill ${isWin ? "win" : "loss"}">${isWin ? "Win" : "Loss"}</span>
        <span class="pill">${data.round}</span>
        <span class="pill">${data.tournament}</span>
        <span class="pill">${data.surface}</span>
        <span class="pill">${data.date}</span>
      </div>
      <p><strong>Score:</strong> ${data.score}</p>
      <p class="status">Source: ${data.source}</p>
    </div>

    <div class="grid-4">
      ${statBoxes
        .map(
          ([label, value]) => `
        <div class="stat-box">
          <div class="value">${value}</div>
          <div class="label">${label}</div>
        </div>`
        )
        .join("")}
    </div>

    <div class="section">
      <h3>Tactical profile</h3>
      <p>${data.tacticalProfile}</p>
    </div>

    <div class="grid-2">
      <div class="section">
        <h3>Coaching notes</h3>
        <ul>${(data.coachingNotes || []).map((n) => `<li>${n}</li>`).join("")}</ul>
      </div>
      <div class="section">
        <h3>Key moments</h3>
        <ul>${(data.keyMoments || []).map((n) => `<li>${n}</li>`).join("")}</ul>
      </div>
    </div>

    ${
      (data.strengths || []).length || (data.development || []).length
        ? `<div class="grid-2">
        <div class="section"><h3>Strengths</h3><ul>${(data.strengths || []).map((n) => `<li>${n}</li>`).join("") || "<li>—</li>"}</ul></div>
        <div class="section"><h3>Development</h3><ul>${(data.development || []).map((n) => `<li>${n}</li>`).join("") || "<li>—</li>"}</ul></div>
      </div>`
        : ""
    }

    <div class="section">
      <h3>Match breakdown</h3>
      ${pieHtml}
    </div>
  `;
  $("#analysis").classList.remove("hidden");
  $("#empty-state")?.classList.add("hidden");
  $("#analysis").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderRosterGrid(filter = "") {
  const grid = $("#roster-grid");
  const q = filter.trim().toLowerCase();
  const visible = rosterPlayers.filter((p) => {
    if (!q) return true;
    return (
      p.name.toLowerCase().includes(q) ||
      (p.class_year || "").toLowerCase().includes(q) ||
      (p.hometown || "").toLowerCase().includes(q)
    );
  });

  if (!visible.length) {
    grid.innerHTML = `<p class="status">No roster players match "${filter}"</p>`;
    return;
  }

  grid.innerHTML = visible
    .map((p) => {
      const active = activeRosterName === p.name ? " active" : "";
      const badge = p.has_data
        ? `<span class="badge ready">Analysis available</span>`
        : `<span class="badge pending">Limited public data</span>`;
      return `
        <button type="button" class="roster-card${active}" data-name="${p.name}">
          <div class="name">${p.name}</div>
          <div class="meta">${p.class_year || "UVA"}${p.hometown ? ` · ${p.hometown}` : ""}</div>
          ${badge}
        </button>`;
    })
    .join("");

  grid.querySelectorAll(".roster-card").forEach((el) => {
    el.addEventListener("click", () => selectRosterPlayer(el.dataset.name));
  });
}

async function loadRoster(refresh = false) {
  setStatus("Loading UVA roster…");
  try {
    if (STATIC_MODE && !refresh) {
      const res = await fetch(staticUrl("roster.json"));
      if (!res.ok) throw new Error("Static roster missing");
      const data = await res.json();
      rosterPlayers = data.players || [];
      renderRosterGrid($("#roster-query").value);
      setStatus(`${rosterPlayers.length} players on ${data.season || "current"} roster`);
      return;
    }
    const url = refresh ? apiUrl("/api/uva-roster?refresh=1") : apiUrl("/api/uva-roster");
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to load roster");
    rosterPlayers = data.players || [];
    renderRosterGrid($("#roster-query").value);
    setStatus(`${rosterPlayers.length} players on ${data.season || "current"} roster`);
  } catch (err) {
    setStatus(err.message || "Failed to load roster", true);
  }
}

async function selectRosterPlayer(name) {
  activeRosterName = name;
  renderRosterGrid($("#roster-query").value);
  setStatus(`Loading ${name}…`);
  $("#player-query").value = name;

  try {
    let data;
    const rosterEntry = rosterPlayers.find((p) => p.name === name);
    if (STATIC_MODE) {
      if (!rosterEntry?.has_data || !rosterEntry?.slug) {
        data = rosterEntry || { name, has_data: false };
      } else {
        const res = await fetch(staticUrl(`players/${rosterEntry.slug}.json`));
        if (!res.ok) throw new Error("Player data not found");
        data = await res.json();
      }
    } else {
      const res = await fetch(apiUrl(`/api/uva-roster/${encodeURIComponent(name)}`));
      data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to load player");
    }

  if (!data.slug || !data.has_data) {
    $("#player-card").innerHTML = `<strong>${data.name}</strong> · No Tennis Abstract match data found yet.`;
    $("#player-card").classList.remove("hidden");
    $("#match-select").innerHTML = `<option value="">No match data available</option>`;
    $("#match-select").disabled = true;
    $("#analyze-btn").disabled = true;
    setStatus(`${name} is on the roster, but public match data is not available yet.`, true);
    return;
  }

  currentSlug = data.slug;
  currentMatches = data.matches || [];
  const p = data.profile;
  $("#player-card").innerHTML = `
    <strong>${p.full_name}</strong> [${p.country}] · Rank #${p.rank ?? "—"} · ${p.hand}-handed ${p.backhand} BH
    ${p.age ? ` · Age ${p.age}` : ""}
    · ${currentMatches.length} match(es)
  `;
  $("#player-card").classList.remove("hidden");
  applyTournamentFilter();
  setStatus(`${name} loaded — select a match to analyze`);
  $("#analysis").classList.add("hidden");
  } catch (err) {
    setStatus(err.message || "Failed to load player", true);
  }
}

function applyTournamentFilter() {
  const tournament = $("#tournament-filter").value.trim().toLowerCase();
  const filtered = tournament
    ? currentMatches.filter((m) => m.tournament.toLowerCase().includes(tournament))
    : currentMatches;

  const sel = $("#match-select");
  if (!filtered.length) {
    sel.innerHTML = `<option value="">No matches found</option>`;
    sel.disabled = true;
    $("#analyze-btn").disabled = true;
    setStatus("No matches — try clearing tournament filter", true);
    return;
  }
  sel.innerHTML = filtered
    .map(
      (m) =>
        `<option value="${m.id}">${m.date} · ${m.tournament} · ${m.round} vs ${m.opponent} (${m.result} ${m.score})</option>`
    )
    .join("");
  sel.disabled = false;
  $("#analyze-btn").disabled = false;
}

async function searchPlayers() {
  const q = $("#player-query").value.trim();
  if (q.length < 2) {
    setStatus("Enter at least 2 characters", true);
    return;
  }
  setStatus("Searching…");
  const box = $("#search-results");

  if (STATIC_MODE) {
    const ql = q.toLowerCase();
    const hits = rosterPlayers.filter(
      (p) =>
        p.name.toLowerCase().includes(ql) ||
        (p.hometown || "").toLowerCase().includes(ql) ||
        (p.class_year || "").toLowerCase().includes(ql)
    );
    if (!hits.length) {
      box.innerHTML = `<div class="search-item">No roster players match "${q}". On this site, search is limited to the UVA roster — pick a player card above.</div>`;
      box.classList.remove("hidden");
      setStatus("No roster matches", true);
      return;
    }
    box.innerHTML = hits
      .map(
        (p) => `
    <div class="search-item roster-search-item" data-name="${p.name}">
      <span><strong>${p.name}</strong> · UVA roster</span>
      <span>${p.class_year || "UVA"}</span>
    </div>`
      )
      .join("");
    box.classList.remove("hidden");
    box.querySelectorAll(".roster-search-item").forEach((el) => {
      el.addEventListener("click", () => selectRosterPlayer(el.dataset.name));
    });
    setStatus(`${hits.length} roster player(s) found`);
    return;
  }

  const res = await fetch(apiUrl(`/api/search?q=${encodeURIComponent(q)}`));
  const data = await res.json();
  if (!data.results?.length) {
    box.innerHTML = `<div class="search-item">No players found for "${q}"</div>`;
    box.classList.remove("hidden");
    setStatus("No results — try full name", true);
    return;
  }
  box.innerHTML = data.results
    .map(
      (p) => `
    <div class="search-item" data-slug="${p.slug}">
      <span><strong>${p.name}</strong> [${p.country}]</span>
      <span>#${p.rank ?? "—"}</span>
    </div>`
    )
    .join("");
  box.classList.remove("hidden");
  box.querySelectorAll(".search-item").forEach((el) => {
    el.addEventListener("click", () => loadPlayer(el.dataset.slug));
  });
  setStatus(`${data.results.length} player(s) found`);
}

async function loadPlayer(slug) {
  currentSlug = slug;
  activeRosterName = null;
  renderRosterGrid($("#roster-query").value);
  setStatus("Loading matches…");
  $("#search-results").classList.add("hidden");
  const tournament = $("#tournament-filter").value.trim();
  const url = tournament
    ? apiUrl(`/api/player/${slug}?tournament=${encodeURIComponent(tournament)}`)
    : apiUrl(`/api/player/${slug}`);
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) {
    setStatus(data.error || "Failed to load player", true);
    return false;
  }

  const p = data.profile;
  currentMatches = data.matches;
  $("#player-card").innerHTML = `
    <strong>${p.full_name}</strong> [${p.country}] · Rank #${p.rank ?? "—"} · ${p.hand}-handed ${p.backhand} BH
    ${p.age ? ` · Age ${p.age}` : ""}
  `;
  $("#player-card").classList.remove("hidden");
  applyTournamentFilter();
  $("#analysis").classList.add("hidden");
  return true;
}

async function analyzeMatch() {
  const matchId = $("#match-select").value;
  if (!currentSlug || !matchId) return;
  setStatus("Building analysis…");
  $("#analyze-btn").disabled = true;
  try {
    let data;
    if (STATIC_MODE) {
      const res = await fetch(staticUrl(`analyses/${currentSlug}/${matchId}.json`));
      if (!res.ok) throw new Error("Analysis not found");
      data = await res.json();
    } else {
      const res = await fetch(apiUrl(`/api/analyze/${currentSlug}/${matchId}`));
      data = await res.json();
      if (!res.ok) throw new Error(data.error || "Analysis failed");
    }
    renderAnalysis(data);
    setStatus("Analysis ready — share this view with coaching staff");
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    $("#analyze-btn").disabled = false;
  }
}

$("#roster-refresh-btn").addEventListener("click", () => loadRoster(true));
$("#roster-query").addEventListener("input", (e) => renderRosterGrid(e.target.value));
$("#search-btn").addEventListener("click", searchPlayers);
$("#player-query").addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchPlayers();
});
$("#tournament-filter").addEventListener("input", () => {
  if (currentSlug) applyTournamentFilter();
});
$("#tournament-filter").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && currentSlug) applyTournamentFilter();
});
$("#analyze-btn").addEventListener("click", analyzeMatch);

const params = new URLSearchParams(window.location.search);

async function bootFromUrl() {
  await loadRoster();

  const rosterName = params.get("roster");
  if (rosterName) {
    $("#roster-query").value = rosterName;
    renderRosterGrid(rosterName);
    await selectRosterPlayer(rosterName);
  } else {
    const slug = params.get("player");
    if (slug) {
      $("#player-query").value = slug.replace(/([A-Z])/g, " $1").trim();
      if (params.get("tournament")) {
        $("#tournament-filter").value = params.get("tournament");
      }
      const ok = await loadPlayer(slug);
      if (!ok) return;
    }
  }

  const matchId = params.get("match");
  if (matchId) {
    $("#match-select").value = matchId;
  }

  if (params.get("analyze") === "1" || params.get("analyze") === "true" || matchId) {
    await analyzeMatch();
  }
}

bootFromUrl();

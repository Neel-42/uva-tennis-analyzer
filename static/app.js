let currentSlug = null;
let currentReports = null;
let currentSurface = "all";
let rosterPlayers = [];
let activeRosterName = null;

const $ = (sel) => document.querySelector(sel);

/** Static bundle on GitHub Pages; Flask API when running locally. */
const STATIC_MODE = document.querySelector('meta[name="static-mode"]')?.content === "1";
const API_BASE = (() => {
  if (STATIC_MODE) return "";
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta?.content) return meta.content.replace(/\/$/, "");
  return "";
})();

const SURFACE_LABELS = {
  all: "All surfaces",
  hard: "Hard court",
  clay: "Clay",
  grass: "Grass",
  indoor: "Indoor",
};

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

function siteRoot() {
  if (location.hostname.endsWith("github.io")) {
    const segment = location.pathname.split("/").filter(Boolean)[0];
    return segment ? `/${segment}/` : "/";
  }
  if (location.protocol === "file:") return "./";
  return "/";
}

function staticUrl(path) {
  return `${siteRoot()}data/${path.replace(/^\//, "")}`;
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

const KIND_MARK = { strength: "+", weakness: "−", note: "·" };

function renderScoutingList(items, compact = false) {
  if (!items?.length) return "";
  return `<ul class="scouting-list${compact ? " compact" : ""}">
    ${items
      .map(
        (s) => `<li class="scout ${s.kind}">
          <span class="scout-mark" aria-hidden="true">${KIND_MARK[s.kind] || "·"}</span>
          <span class="scout-text">${compact ? s.short : s.text}</span>
        </li>`
      )
      .join("")}
  </ul>`;
}

function renderSurfaceChips(report) {
  const wrap = $("#surface-filter");
  const counts = report.surfaceCounts || {};
  const keys = ["all", "hard", "clay", "indoor", "grass"].filter(
    (k) => k === "all" || counts[k]
  );

  wrap.innerHTML = keys
    .map((k) => {
      const active = k === currentSurface ? " active" : "";
      const count = k === "all" ? Object.values(counts).reduce((a, b) => a + b, 0) : counts[k];
      return `<button type="button" class="surface-chip${active}" data-surface="${k}">
        ${SURFACE_LABELS[k] || k} <span class="chip-count">${count}</span>
      </button>`;
    })
    .join("");

  wrap.classList.remove("hidden");
  wrap.querySelectorAll(".surface-chip").forEach((el) => {
    el.addEventListener("click", () => selectSurface(el.dataset.surface));
  });
}

function renderFeaturedMatches(matches, playerLabel) {
  if (!matches?.length) return "";
  const cards = matches
    .map((m) => {
      const isLoss = m.result === "L";
      const collegeTag = m.isCollege ? `<span class="pill college">College</span>` : "";
      return `
      <div class="match-card${isLoss ? " loss" : ""}">
        <div class="match-head">
          <div>
            <h3>${m.round} · ${m.tournament}</h3>
            <div class="match-meta">vs ${m.opponent} · ${m.score} · ${m.date}</div>
          </div>
          <span class="pill ${isLoss ? "loss" : "win"}">${m.result}</span>
        </div>
        <div class="pie-wrap">
          ${matchPieSvg(m.pointsWonPct, playerLabel, isLoss)}
          <div class="pie-legend">
            <div><span class="dot" style="background:var(--success)"></span>${playerLabel} ${m.pointsWonPct}%</div>
            <div><span class="dot" style="background:var(--muted)"></span>Opponent ${100 - m.pointsWonPct}%</div>
          </div>
        </div>
        <p class="pie-caption">Estimated from ${m.source.toLowerCase()} · ~${m.totalPoints} points · ${m.surface} ${collegeTag}</p>
      </div>`;
    })
    .join("");

  return `
    <h2 class="section-title">Featured matches — points won</h2>
    <p class="lead">Highest-signal matches in this sample. Pie = share of total points won.</p>
    <div class="match-grid">${cards}</div>`;
}

function renderMatchList(matches) {
  if (!matches?.length) return "";
  const rows = matches
    .map(
      (m) => `
      <li class="match-row ${m.result === "W" ? "win" : "loss"}">
        <span class="match-row-result">${m.result}</span>
        <span class="match-row-main">
          <strong>${m.opponent}</strong>
          <span class="match-row-meta">${m.tournament} · ${m.round} · ${m.surface}${
        m.isCollege ? " · college" : ""
      }</span>
        </span>
        <span class="match-row-score">${m.score}</span>
        <span class="match-row-date">${m.date}</span>
      </li>`
    )
    .join("");

  return `
    <details class="all-matches">
      <summary>All ${matches.length} matches in this sample</summary>
      <ul class="match-list">${rows}</ul>
    </details>`;
}

function renderReport(report) {
  if (report.empty) {
    $("#analysis").innerHTML = `<div class="callout">${report.note}</div>`;
    $("#analysis").classList.remove("hidden");
    $("#empty-state")?.classList.add("hidden");
    return;
  }

  const avg = report.statAverages || {};
  const pw = report.pointsWon;
  const label = report.playerLabel;
  const rec = report.record;

  const cov = report.statCoverage;
  let coverageNote = "";
  if (cov && cov.detailed === 0) {
    coverageNote = `<p class="coverage-note">No published box scores for these ${cov.total} matches, so the serve averages show a dash. Everything derived from scorelines still covers all of them.</p>`;
  } else if (cov && cov.detailed < cov.total) {
    coverageNote = `<p class="coverage-note">Serve averages come from the ${cov.detailed} of ${cov.total} matches with published box scores.</p>`;
  }

  const statBoxes = [
    ["Matches", report.matchCount],
    ["Record", `${rec.wins}-${rec.losses}`],
    ["Games won", `${report.games.won}-${report.games.lost}`],
    ["Dominance ratio", avg.dominanceRatio?.toFixed(2) ?? "—"],
    ["Ace %", avg.acePct != null ? `${avg.acePct}%` : "—"],
    ["DF %", avg.dfPct != null ? `${avg.dfPct}%` : "—"],
    ["1st serve won", avg.firstServeWonPct != null ? `${avg.firstServeWonPct}%` : "—"],
    ["2nd serve won", avg.secondServeWonPct != null ? `${avg.secondServeWonPct}%` : "—"],
  ];

  $("#analysis").innerHTML = `
    <div class="analysis-header">
      <h2>${report.player} — comprehensive analysis</h2>
      <div class="pill-row">
        <span class="pill">${SURFACE_LABELS[report.surface] || report.surface}</span>
        <span class="pill">${report.matchCount} matches</span>
        <span class="pill ${rec.wins >= rec.losses ? "win" : "loss"}">${rec.wins}-${rec.losses}</span>
        ${report.dateRange ? `<span class="pill">${report.dateRange}</span>` : ""}
        ${report.profile?.rank ? `<span class="pill">Rank #${report.profile.rank}</span>` : ""}
      </div>
    </div>

    ${
      report.scoutingReport?.length
        ? `<div class="scouting-card">
      <h3>Strengths &amp; weaknesses</h3>
      ${renderScoutingList(report.scoutingReport)}
    </div>`
        : ""
    }

    <div class="callout">${report.note}</div>

    <div class="grid-4">
      ${statBoxes
        .map(
          ([l, v]) => `
        <div class="stat-box">
          <div class="value">${v}</div>
          <div class="label">${l}</div>
        </div>`
        )
        .join("")}
    </div>
    ${coverageNote}

    <div class="answer-card">
      <h2>Points won — full sample</h2>
      <p class="verdict">${pw.playerPct}% ${label}</p>
      <div class="pie-wrap">
        ${matchPieSvg(pw.playerPct, label, false)}
        <div class="pie-legend">
          <div><span class="dot" style="background:var(--success)"></span>${label} ${pw.playerPct}%</div>
          <div><span class="dot" style="background:var(--muted)"></span>Opponents ${pw.opponentPct}%</div>
        </div>
      </div>
      <p class="pie-caption">${pw.source} · ~${pw.totalPoints} total points estimated</p>
    </div>

    <div class="answer-card">
      <h2>Serving (deuce vs ad)</h2>
      <p class="verdict">${report.serve.verdict}</p>
      <p>Aggregated across all ${report.matchCount} matches. Top row = points won on each side; bottom row = T-serve share. Win % inside each ring; total points below.</p>
      <div class="summary-pie-grid">
        ${(report.serve.cells || []).map(renderSummaryPieCell).join("")}
      </div>
    </div>

    <div class="answer-card">
      <h2>Returning (deuce vs ad)</h2>
      <p class="verdict tie">${report.return.verdict}</p>
      <p>Same ${report.matchCount}-match aggregate. Top row = return points won; bottom row = total return points on that side.</p>
      <div class="summary-pie-grid">
        ${(report.return.cells || []).map(renderSummaryPieCell).join("")}
      </div>
    </div>

    <div class="section">
      <h3>Coaching notes</h3>
      <ul>${(report.coachingNotes || []).map((n) => `<li>${n}</li>`).join("") || "<li>—</li>"}</ul>
    </div>

    ${renderFeaturedMatches(report.featuredMatches, label)}

    ${renderMatchList(report.matches)}
  `;

  $("#analysis").classList.remove("hidden");
  $("#empty-state")?.classList.add("hidden");
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
          ${renderScoutingList(p.scouting, true)}
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
    if (STATIC_MODE) {
      if (refresh) {
        location.reload();
        return;
      }
      const res = await fetch(staticUrl("roster.json"));
      if (!res.ok) throw new Error("Static roster data missing");
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
    loadScoutingBullets();
  } catch (err) {
    setStatus(err.message || "Failed to load roster", true);
  }
}

/** Local dev only: bullets are baked into roster.json for the static build. */
async function loadScoutingBullets() {
  if (STATIC_MODE) return;
  try {
    const res = await fetch(apiUrl("/api/uva-roster-scouting"));
    const data = await res.json();
    if (!data.scouting) return;
    rosterPlayers = rosterPlayers.map((p) =>
      data.scouting[p.name] ? { ...p, scouting: data.scouting[p.name] } : p
    );
    renderRosterGrid($("#roster-query").value);
  } catch {
    // Tiles stay useful without bullets; the full report still loads on click.
  }
}

function showNoData(name) {
  $("#player-card").innerHTML = `<strong>${name}</strong> · No public match data found yet.`;
  $("#player-card").classList.remove("hidden");
  $("#surface-filter").classList.add("hidden");
  $("#analysis").classList.add("hidden");
  setStatus(`${name} is on the roster, but public match data is not available yet.`, true);
}

async function loadReports(slug, surface = "all") {
  if (STATIC_MODE) {
    const res = await fetch(staticUrl(`reports/${slug}.json`));
    if (!res.ok) throw new Error("Report data not found");
    return await res.json();
  }
  const res = await fetch(apiUrl(`/api/report/${slug}?surface=${encodeURIComponent(surface)}`));
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Failed to build report");
  return { [surface]: data };
}

async function selectRosterPlayer(name) {
  const q = name.trim().toLowerCase();
  const entry =
    rosterPlayers.find((p) => p.name.toLowerCase() === q) ||
    rosterPlayers.find((p) => p.name.toLowerCase().includes(q));

  if (!entry) {
    setStatus(`No UVA roster player matches "${name}"`, true);
    return;
  }

  activeRosterName = entry.name;
  currentSurface = "all";
  renderRosterGrid($("#roster-query").value);
  setStatus(`Building comprehensive analysis for ${entry.name}…`);
  $("#player-query").value = entry.name;

  try {
    if (!entry.has_data || !entry.slug) {
      showNoData(entry.name);
      return;
    }
    await loadPlayerReport(entry.slug, entry.name);
  } catch (err) {
    setStatus(err.message || "Failed to load player", true);
  }
}

async function loadPlayerReport(slug, displayName) {
  currentSlug = slug;
  currentReports = await loadReports(slug, currentSurface);
  const report = currentReports[currentSurface] || currentReports.all;
  if (!report) throw new Error("No report available");

  const p = report.profile || {};
  $("#player-card").innerHTML = `
    <strong>${report.player}</strong>${p.country ? ` [${p.country}]` : ""}
    · Rank #${p.rank ?? "—"} · ${p.hand ?? "—"}-handed ${p.backhand ?? ""} BH
    ${p.age ? ` · Age ${p.age}` : ""}
    · ${report.matchCount} matches analyzed
  `;
  $("#player-card").classList.remove("hidden");

  renderSurfaceChips(report);
  renderReport(report);
  setStatus(
    `${displayName || report.player}: ${report.matchCount} matches aggregated into one analysis`
  );
  $("#analysis").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function selectSurface(surface) {
  if (!currentSlug) return;
  currentSurface = surface;
  setStatus(`Rebuilding analysis (${SURFACE_LABELS[surface] || surface})…`);
  try {
    if (!currentReports?.[surface]) {
      const fetched = await loadReports(currentSlug, surface);
      currentReports = { ...currentReports, ...fetched };
    }
    const report = currentReports[surface];
    if (!report) throw new Error("No matches on this surface");
    renderSurfaceChips(report);
    renderReport(report);
    setStatus(
      `${report.player}: ${report.matchCount} ${SURFACE_LABELS[surface] || surface} matches aggregated`
    );
  } catch (err) {
    setStatus(err.message || "Failed to switch surface", true);
  }
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
    el.addEventListener("click", async () => {
      activeRosterName = null;
      currentSurface = "all";
      renderRosterGrid($("#roster-query").value);
      $("#search-results").classList.add("hidden");
      setStatus("Building comprehensive analysis…");
      try {
        await loadPlayerReport(el.dataset.slug);
      } catch (err) {
        setStatus(err.message, true);
      }
    });
  });
  setStatus(`${data.results.length} player(s) found`);
}

$("#roster-refresh-btn").addEventListener("click", () => loadRoster(true));
$("#roster-query").addEventListener("input", (e) => renderRosterGrid(e.target.value));
$("#search-btn").addEventListener("click", searchPlayers);
$("#player-query").addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchPlayers();
});

const params = new URLSearchParams(window.location.search);

async function bootFromUrl() {
  await loadRoster();

  const rosterName = params.get("roster");
  if (rosterName) {
    $("#roster-query").value = rosterName;
    renderRosterGrid(rosterName);
    await selectRosterPlayer(rosterName);
    return;
  }

  const slug = params.get("player");
  if (slug) {
    currentSurface = params.get("surface") || "all";
    try {
      await loadPlayerReport(slug);
    } catch (err) {
      setStatus(err.message, true);
    }
  }
}

bootFromUrl();

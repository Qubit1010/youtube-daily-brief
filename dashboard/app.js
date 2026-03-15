/**
 * YouTube Intelligence Dashboard — Client-Side Renderer
 * Features: Tabs, Engagement Rate, Hidden Gems, Topic Filters,
 * Topic Matrix, Content Briefs, Kanban Pipeline, Sortable Tables, Bookmarks
 */

// ── Global State ─────────────────────────────────────────────────────────────
let _allVideos = [];
let _trendingTopics = [];
let _channelBreakdown = [];
let _activeFilter = null;
let _briefCache = {};
let _sortState = {};

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initBookmarks();
    initPipeline();
    fetchData();
});

async function fetchData() {
    try {
        const resp = await fetch("/api/data");
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderDashboard(data);
    } catch (err) {
        showError(err.message);
    }
}

function renderDashboard(data) {
    const analysis = data.analysis || {};
    const raw = data.raw || {};

    _allVideos = raw.videos || [];
    _trendingTopics = analysis.trending_topics || [];
    _channelBreakdown = analysis.channel_breakdown || [];

    renderLastUpdated(analysis.analyzed_at || raw.scraped_at);
    renderTrending(_trendingTopics);
    renderSentiment(analysis.sentiment || {});
    renderTopPerforming(analysis.top_performing || []);
    renderChannelBreakdown(_channelBreakdown);
    renderAllVideosByCreator(_allVideos);
    renderSuggestedTopics(analysis.suggested_topics || []);
    renderOpportunities(analysis.content_opportunities || []);
    renderPatterns(analysis.title_patterns || []);
    renderHiddenGems(_allVideos);
    renderTopicMatrix(_trendingTopics, _allVideos);
    renderPipeline();
    renderBookmarksSidebar();
}

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 1: DASHBOARD TABS
// ══════════════════════════════════════════════════════════════════════════════

function initTabs() {
    const tabs = document.querySelectorAll(".tab");
    const hash = window.location.hash.replace("#", "") || localStorage.getItem("activeTab") || "overview";
    switchTab(hash);

    tabs.forEach(btn => {
        btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    window.addEventListener("hashchange", () => {
        const h = window.location.hash.replace("#", "");
        if (h) switchTab(h);
    });
}

function switchTab(tabName) {
    const validTabs = ["overview", "studio", "research"];
    if (!validTabs.includes(tabName)) tabName = "overview";

    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tabName));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.toggle("active", c.dataset.tab === tabName));
    localStorage.setItem("activeTab", tabName);
    window.location.hash = tabName;
}

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 2: ENGAGEMENT RATE + HIDDEN GEMS
// ══════════════════════════════════════════════════════════════════════════════

function calcEngagement(v) {
    const views = v.view_count || 0;
    if (views === 0) return 0;
    return ((v.like_count || 0) + (v.comment_count || 0)) / views * 100;
}

function engagementBadge(rate) {
    const r = rate.toFixed(1);
    if (rate >= 5) return `<span class="engagement-badge high">${r}%</span>`;
    if (rate >= 2) return `<span class="engagement-badge medium">${r}%</span>`;
    return `<span class="engagement-badge low">${r}%</span>`;
}

function renderHiddenGems(videos) {
    const container = document.getElementById("hidden-gems-content");
    if (!videos.length) { container.innerHTML = '<div class="loading">No video data</div>'; return; }

    const withEngagement = videos.map(v => ({ ...v, engagement: calcEngagement(v) }));
    const medianViews = getMedian(videos.map(v => v.view_count || 0));
    const gems = withEngagement
        .filter(v => (v.view_count || 0) < medianViews && v.engagement > 0)
        .sort((a, b) => b.engagement - a.engagement)
        .slice(0, 5);

    if (!gems.length) { container.innerHTML = '<div class="loading">No hidden gems found</div>'; return; }

    container.innerHTML = gems.map(v => `
        <a href="${esc(v.url)}" target="_blank" rel="noopener" class="video-card gem-card">
            <img class="video-thumb" src="${esc(v.thumbnail_url)}" alt="${esc(v.title)}"
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%231a1a2e%22 width=%2216%22 height=%229%22/><text x=%228%22 y=%225%22 text-anchor=%22middle%22 fill=%22%2355556a%22 font-size=%222%22>No Thumb</text></svg>'">
            <div class="video-info">
                <div class="video-title">${esc(v.title)}</div>
                <div class="video-channel">${esc(v.channel_name)}</div>
                <div class="video-stats">
                    <span>${formatNumber(v.view_count)} views</span>
                    ${engagementBadge(v.engagement)}
                </div>
                <div class="video-note">High engagement, low views — opportunity!</div>
            </div>
        </a>
    `).join("");
}

function getMedian(arr) {
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 3: CLICKABLE TRENDING TOPIC FILTERS
// ══════════════════════════════════════════════════════════════════════════════

function filterVideosByTopic(topic) {
    _activeFilter = topic;
    switchTab("research");

    const filtered = _allVideos.filter(v => {
        const text = ((v.title || "") + " " + (v.description || "")).toLowerCase();
        return topic.toLowerCase().split(/\s+/).some(word => text.includes(word));
    });

    const banner = document.getElementById("filter-banner");
    const filterText = document.getElementById("filter-text");
    banner.style.display = "flex";
    filterText.textContent = `Showing ${filtered.length} video${filtered.length !== 1 ? "s" : ""} about "${topic}"`;

    renderAllVideosByCreator(filtered);
}

function clearFilter() {
    _activeFilter = null;
    document.getElementById("filter-banner").style.display = "none";
    document.querySelectorAll(".topic-pill").forEach(p => p.classList.remove("active"));
    renderAllVideosByCreator(_allVideos);
}

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 4: CROSS-CHANNEL TOPIC MATRIX
// ══════════════════════════════════════════════════════════════════════════════

function renderTopicMatrix(topics, videos) {
    const container = document.getElementById("topic-matrix-content");
    if (!topics.length || !videos.length) {
        container.innerHTML = '<div class="loading">Need trending topics and videos to build matrix</div>';
        return;
    }

    const channels = [...new Set(videos.map(v => v.channel_name || "Unknown"))].sort();

    const matrix = topics.slice(0, 8).map(t => {
        const topicWords = t.topic.toLowerCase().split(/\s+/);
        const row = { topic: t.topic, channels: {} };
        channels.forEach(ch => {
            const chVideos = videos.filter(v =>
                (v.channel_name || "") === ch &&
                topicWords.some(w => ((v.title || "") + " " + (v.description || "")).toLowerCase().includes(w))
            );
            row.channels[ch] = {
                count: chVideos.length,
                views: chVideos.reduce((s, v) => s + (v.view_count || 0), 0)
            };
        });
        return row;
    });

    const headerCells = channels.map(ch => `<th class="matrix-channel" title="${esc(ch)}">${esc(ch.length > 12 ? ch.slice(0, 11) + "..." : ch)}</th>`).join("");

    const rows = matrix.map(row => {
        const cells = channels.map(ch => {
            const cell = row.channels[ch];
            if (cell.count > 0) {
                return `<td class="matrix-cell covered" title="${cell.count} video(s), ${formatNumber(cell.views)} views">
                    <span class="matrix-dot"></span>
                </td>`;
            }
            return `<td class="matrix-cell gap" title="Gap — no coverage"><span class="matrix-gap">GAP</span></td>`;
        }).join("");
        return `<tr><td class="matrix-topic">${esc(row.topic)}</td>${cells}</tr>`;
    }).join("");

    container.innerHTML = `
        <div class="matrix-scroll">
            <table class="matrix-table">
                <thead><tr><th></th>${headerCells}</tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
        <div class="matrix-legend">
            <span><span class="matrix-dot"></span> Covered</span>
            <span><span class="matrix-gap">GAP</span> Opportunity</span>
        </div>
    `;
}

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 5: CONTENT BRIEF GENERATOR
// ══════════════════════════════════════════════════════════════════════════════

async function generateBrief(btn, topic) {
    const card = btn.closest(".topic-card");
    let panel = card.querySelector(".brief-panel");

    if (panel) {
        panel.style.display = panel.style.display === "none" ? "block" : "none";
        return;
    }

    const cacheKey = topic.topic || topic;
    if (_briefCache[cacheKey]) {
        renderBriefPanel(card, _briefCache[cacheKey]);
        return;
    }

    btn.disabled = true;
    btn.textContent = "Generating...";

    try {
        const resp = await fetch("/api/generate-brief", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(topic)
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const brief = await resp.json();
        _briefCache[cacheKey] = brief;
        renderBriefPanel(card, brief);
    } catch (err) {
        btn.textContent = "Error — Retry";
        btn.disabled = false;
        console.error("Brief generation failed:", err);
    }
}

function renderBriefPanel(card, brief) {
    const btn = card.querySelector(".brief-btn");
    btn.textContent = "Hide Brief";
    btn.disabled = false;

    const panel = document.createElement("div");
    panel.className = "brief-panel";
    panel.innerHTML = `
        <div class="brief-section"><strong>Hook (first 30s):</strong><p>${esc(brief.hook || "")}</p></div>
        <div class="brief-section"><strong>Talking Points:</strong>
            <ul>${(brief.talking_points || []).map(p => `<li>${esc(p)}</li>`).join("")}</ul>
        </div>
        <div class="brief-section"><strong>Title Variations:</strong>
            <ul>${(brief.title_variations || []).map(t => `<li>${esc(t)}</li>`).join("")}</ul>
        </div>
        <div class="brief-section"><strong>Thumbnail Concept:</strong><p>${esc(brief.thumbnail_concept || "")}</p></div>
        <div class="brief-section"><strong>CTA:</strong><p>${esc(brief.cta || "")}</p></div>
        ${brief.estimated_length ? `<div class="brief-section"><strong>Est. Length:</strong> ${esc(brief.estimated_length)}</div>` : ""}
    `;
    card.appendChild(panel);
}

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 6: CONTENT PIPELINE BOARD (KANBAN)
// ══════════════════════════════════════════════════════════════════════════════

function getPipeline() {
    try { return JSON.parse(localStorage.getItem("pipeline") || "null") || { ideas: [], in_progress: [], published: [] }; }
    catch { return { ideas: [], in_progress: [], published: [] }; }
}

function savePipeline(p) { localStorage.setItem("pipeline", JSON.stringify(p)); }

function initPipeline() {
    document.getElementById("pipeline-content")?.addEventListener("click", e => {
        if (e.target.closest(".pipeline-delete")) {
            const card = e.target.closest(".pipeline-card");
            const col = card.closest(".pipeline-column").dataset.col;
            const idx = parseInt(card.dataset.idx);
            const p = getPipeline();
            p[col].splice(idx, 1);
            savePipeline(p);
            renderPipeline();
        }
        if (e.target.id === "pipeline-clear-all") {
            savePipeline({ ideas: [], in_progress: [], published: [] });
            renderPipeline();
        }
        if (e.target.id === "pipeline-export") {
            const p = getPipeline();
            const text = ["IDEAS", ...p.ideas.map(i => `- ${i.name}`), "", "IN PROGRESS", ...p.in_progress.map(i => `- ${i.name}`), "", "PUBLISHED", ...p.published.map(i => `- ${i.name}${i.url ? " (" + i.url + ")" : ""}`)].join("\n");
            navigator.clipboard.writeText(text);
            e.target.textContent = "Copied!";
            setTimeout(() => { e.target.textContent = "Export"; }, 1500);
        }
    });
}

function addToPipeline(name, format, competition) {
    const p = getPipeline();
    if (p.ideas.some(i => i.name === name) || p.in_progress.some(i => i.name === name) || p.published.some(i => i.name === name)) return;
    p.ideas.push({ name, format: format || "", competition: competition || "" });
    savePipeline(p);
    renderPipeline();
    switchTab("studio");
}

function renderPipeline() {
    const container = document.getElementById("pipeline-content");
    if (!container) return;
    const p = getPipeline();
    const total = p.ideas.length + p.in_progress.length + p.published.length;

    if (total === 0) {
        container.innerHTML = '<div class="loading">No items in pipeline. Add topics from Suggested Topics or Content Opportunities.</div>';
        return;
    }

    function renderCol(title, items, colKey) {
        const cards = items.map((item, i) => `
            <div class="pipeline-card" draggable="true" data-idx="${i}" data-col="${colKey}">
                <span class="pipeline-card-name">${esc(item.name)}</span>
                <div class="pipeline-card-meta">
                    ${item.format ? `<span class="topic-tag format">${esc(item.format)}</span>` : ""}
                    ${item.competition ? `<span class="topic-tag competition-${item.competition}">${esc(item.competition)}</span>` : ""}
                </div>
                ${colKey === "published" ? `<input type="text" class="pipeline-url" placeholder="Video URL..." value="${esc(item.url || "")}" onchange="updatePipelineUrl('${colKey}',${i},this.value)">` : ""}
                <button class="pipeline-delete" title="Remove">&times;</button>
            </div>
        `).join("");
        return `
            <div class="pipeline-column" data-col="${colKey}">
                <div class="pipeline-col-header">${title} <span class="pipeline-col-count">${items.length}</span></div>
                <div class="pipeline-drop-zone" data-col="${colKey}">${cards}</div>
            </div>
        `;
    }

    container.innerHTML = `
        <div class="pipeline-board">
            ${renderCol("Ideas", p.ideas, "ideas")}
            ${renderCol("In Progress", p.in_progress, "in_progress")}
            ${renderCol("Published", p.published, "published")}
        </div>
        <div class="pipeline-actions">
            <button id="pipeline-export" class="btn-secondary">Export</button>
            <button id="pipeline-clear-all" class="btn-secondary btn-danger">Clear All</button>
        </div>
    `;

    // Drag and drop
    container.querySelectorAll(".pipeline-card").forEach(card => {
        card.addEventListener("dragstart", e => {
            e.dataTransfer.setData("text/plain", JSON.stringify({ col: card.dataset.col, idx: parseInt(card.dataset.idx) }));
            card.classList.add("dragging");
        });
        card.addEventListener("dragend", () => card.classList.remove("dragging"));
    });

    container.querySelectorAll(".pipeline-drop-zone").forEach(zone => {
        zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-over"); });
        zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
        zone.addEventListener("drop", e => {
            e.preventDefault();
            zone.classList.remove("drag-over");
            const { col: fromCol, idx } = JSON.parse(e.dataTransfer.getData("text/plain"));
            const toCol = zone.dataset.col;
            if (fromCol === toCol) return;
            const p = getPipeline();
            const [item] = p[fromCol].splice(idx, 1);
            p[toCol].push(item);
            savePipeline(p);
            renderPipeline();
        });
    });
}

// Called from inline onchange on published URL inputs
window.updatePipelineUrl = function(col, idx, url) {
    const p = getPipeline();
    if (p[col][idx]) { p[col][idx].url = url; savePipeline(p); }
};

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 7: SORTABLE TABLES
// ══════════════════════════════════════════════════════════════════════════════

function makeSortable(tableEl, data, renderRowFn, columnsConfig) {
    const tableId = tableEl.closest("section")?.id || "table";
    if (!_sortState[tableId]) _sortState[tableId] = { col: null, asc: true };

    tableEl.querySelectorAll("th").forEach((th, i) => {
        if (!columnsConfig[i]) return;
        th.classList.add("sortable");
        th.addEventListener("click", () => {
            const state = _sortState[tableId];
            if (state.col === i) { state.asc = !state.asc; }
            else { state.col = i; state.asc = true; }

            const sorted = [...data].sort((a, b) => {
                const va = columnsConfig[i].value(a);
                const vb = columnsConfig[i].value(b);
                if (typeof va === "string") return state.asc ? va.localeCompare(vb) : vb.localeCompare(va);
                return state.asc ? va - vb : vb - va;
            });

            const tbody = tableEl.querySelector("tbody");
            tbody.innerHTML = sorted.map(renderRowFn).join("");

            tableEl.querySelectorAll("th").forEach(h => h.classList.remove("sort-asc", "sort-desc"));
            th.classList.add(state.asc ? "sort-asc" : "sort-desc");
        });
    });
}

// ══════════════════════════════════════════════════════════════════════════════
// FEATURE 8: BOOKMARK / SAVE FOR LATER
// ══════════════════════════════════════════════════════════════════════════════

function getBookmarks() {
    try { return JSON.parse(localStorage.getItem("bookmarks") || "null") || { videos: [], topics: [] }; }
    catch { return { videos: [], topics: [] }; }
}

function saveBookmarks(b) {
    localStorage.setItem("bookmarks", JSON.stringify(b));
    updateBookmarkBadge();
}

function toggleBookmarkVideo(id, title, url, channel) {
    const b = getBookmarks();
    const idx = b.videos.findIndex(v => v.id === id);
    if (idx >= 0) b.videos.splice(idx, 1);
    else b.videos.push({ id, title, url, channel });
    saveBookmarks(b);
    renderBookmarksSidebar();
    // Update icon state
    document.querySelectorAll(`.bookmark-video[data-id="${id}"]`).forEach(el =>
        el.classList.toggle("bookmarked", idx < 0)
    );
}

function toggleBookmarkTopic(name) {
    const b = getBookmarks();
    const idx = b.topics.findIndex(t => t.name === name);
    if (idx >= 0) b.topics.splice(idx, 1);
    else b.topics.push({ name });
    saveBookmarks(b);
    renderBookmarksSidebar();
    document.querySelectorAll(`.bookmark-topic[data-name="${CSS.escape(name)}"]`).forEach(el =>
        el.classList.toggle("bookmarked", idx < 0)
    );
}

function isVideoBookmarked(id) { return getBookmarks().videos.some(v => v.id === id); }
function isTopicBookmarked(name) { return getBookmarks().topics.some(t => t.name === name); }

function updateBookmarkBadge() {
    const b = getBookmarks();
    const count = b.videos.length + b.topics.length;
    const badge = document.getElementById("bookmark-count");
    badge.textContent = count;
    badge.style.display = count > 0 ? "inline-flex" : "none";
}

function initBookmarks() {
    updateBookmarkBadge();
    document.getElementById("bookmarks-toggle")?.addEventListener("click", () => {
        document.getElementById("bookmarks-sidebar").classList.toggle("open");
        document.getElementById("bookmarks-overlay").style.display =
            document.getElementById("bookmarks-sidebar").classList.contains("open") ? "block" : "none";
    });
    document.getElementById("bookmarks-close")?.addEventListener("click", () => {
        document.getElementById("bookmarks-sidebar").classList.remove("open");
        document.getElementById("bookmarks-overlay").style.display = "none";
    });
    document.getElementById("bookmarks-overlay")?.addEventListener("click", () => {
        document.getElementById("bookmarks-sidebar").classList.remove("open");
        document.getElementById("bookmarks-overlay").style.display = "none";
    });
    document.getElementById("bookmarks-copy")?.addEventListener("click", () => {
        const b = getBookmarks();
        const lines = [
            "SAVED VIDEOS", ...b.videos.map(v => `- ${v.title} (${v.channel}) ${v.url}`),
            "", "SAVED TOPICS", ...b.topics.map(t => `- ${t.name}`)
        ].join("\n");
        navigator.clipboard.writeText(lines);
        const btn = document.getElementById("bookmarks-copy");
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = "Copy All"; }, 1500);
    });
    document.getElementById("bookmarks-clear")?.addEventListener("click", () => {
        saveBookmarks({ videos: [], topics: [] });
        renderBookmarksSidebar();
        document.querySelectorAll(".bookmarked").forEach(el => el.classList.remove("bookmarked"));
    });

    // Filter clear
    document.getElementById("filter-clear")?.addEventListener("click", clearFilter);
}

function renderBookmarksSidebar() {
    const b = getBookmarks();
    const container = document.getElementById("bookmarks-list");

    if (!b.videos.length && !b.topics.length) {
        container.innerHTML = '<div class="loading">No saved items</div>';
        return;
    }

    let html = "";
    if (b.videos.length) {
        html += `<h3 class="sidebar-section-title">Videos (${b.videos.length})</h3>`;
        html += b.videos.map(v => `
            <div class="sidebar-item">
                <a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a>
                <span class="sidebar-item-sub">${esc(v.channel)}</span>
            </div>
        `).join("");
    }
    if (b.topics.length) {
        html += `<h3 class="sidebar-section-title">Topics (${b.topics.length})</h3>`;
        html += b.topics.map(t => `
            <div class="sidebar-item">${esc(t.name)}</div>
        `).join("");
    }
    container.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════════════
// EXISTING RENDERERS (updated with new features integrated)
// ══════════════════════════════════════════════════════════════════════════════

function renderLastUpdated(isoDate) {
    const el = document.getElementById("last-updated");
    if (!isoDate) { el.textContent = "No data yet"; return; }
    const d = new Date(isoDate);
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    let ago;
    if (diffMins < 1) ago = "just now";
    else if (diffMins < 60) ago = `${diffMins}m ago`;
    else if (diffHours < 24) ago = `${diffHours}h ago`;
    else ago = d.toLocaleDateString();

    el.textContent = `Updated ${ago} — ${d.toLocaleString()}`;
}

// ── Trending Topics (with clickable filter) ──────────────────────────────────
function renderTrending(topics) {
    const container = document.getElementById("trending-content");
    if (!topics.length) { container.innerHTML = '<div class="loading">No trending data</div>'; return; }

    const pills = topics.map(t =>
        `<span class="topic-pill" data-topic="${esc(t.topic)}" title="${esc(t.summary || '')}">
            ${esc(t.topic)}
            <span class="count">${t.mention_count || ""}</span>
        </span>`
    ).join("");

    const topSummary = topics[0]?.summary
        ? `<div class="topic-summary"><strong>${esc(topics[0].topic)}:</strong> ${esc(topics[0].summary)}</div>`
        : "";

    container.innerHTML = `<div class="topic-pills">${pills}</div>${topSummary}`;

    // Feature 3: clickable pills
    container.querySelectorAll(".topic-pill").forEach(pill => {
        pill.style.cursor = "pointer";
        pill.addEventListener("click", () => {
            container.querySelectorAll(".topic-pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            filterVideosByTopic(pill.dataset.topic);
        });
    });
}

// ── Sentiment ────────────────────────────────────────────────────────────────
function renderSentiment(sentiment) {
    const container = document.getElementById("sentiment-content");
    if (!sentiment.overall) { container.innerHTML = '<div class="loading">No sentiment data</div>'; return; }

    const emojis = {
        bullish: "📈", cautious: "⚠️", "hype-driven": "🚀", neutral: "😐", mixed: "🔄"
    };

    const confidence = Math.round((sentiment.confidence || 0) * 100);

    const signalsHtml = (sentiment.signals || []).map(s =>
        `<li><span class="signal-weight ${s.weight}">${s.weight}</span> ${esc(s.signal)}</li>`
    ).join("");

    container.innerHTML = `
        <div class="sentiment-display">
            <div class="sentiment-indicator ${sentiment.overall}">
                <span class="sentiment-emoji">${emojis[sentiment.overall] || "📊"}</span>
                ${esc(sentiment.overall)}
            </div>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: ${confidence}%"></div>
            </div>
            <div class="confidence-label">Confidence: ${confidence}%</div>
            <div class="sentiment-reasoning">${esc(sentiment.reasoning || "")}</div>
            ${signalsHtml ? `<ul class="signals-list">${signalsHtml}</ul>` : ""}
        </div>
    `;
}

// ── Top Performing Videos (with bookmark) ────────────────────────────────────
function renderTopPerforming(videos) {
    const container = document.getElementById("top-videos-content");
    if (!videos.length) { container.innerHTML = '<div class="loading">No video data</div>'; return; }

    container.innerHTML = videos.map(v => {
        const vid = v.video_id || v.url || "";
        const bm = isVideoBookmarked(vid) ? "bookmarked" : "";
        return `
        <a href="${esc(v.url)}" target="_blank" rel="noopener" class="video-card">
            <img class="video-thumb" src="${esc(v.thumbnail_url)}" alt="${esc(v.title)}"
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%231a1a2e%22 width=%2216%22 height=%229%22/><text x=%228%22 y=%225%22 text-anchor=%22middle%22 fill=%22%2355556a%22 font-size=%222%22>No Thumb</text></svg>'">
            <div class="video-info">
                <div class="video-title">${esc(v.title)}</div>
                <div class="video-channel">${esc(v.channel_name)}</div>
                <div class="video-stats">
                    <span>${formatNumber(v.view_count)} views</span>
                    <span>${esc(v.published_date || "")}</span>
                </div>
                ${v.performance_note ? `<div class="video-note">${esc(v.performance_note)}</div>` : ""}
            </div>
            <button class="bookmark-video ${bm}" data-id="${esc(vid)}" data-title="${esc(v.title)}" data-url="${esc(v.url)}" data-channel="${esc(v.channel_name)}" onclick="event.preventDefault();event.stopPropagation();toggleBookmarkVideo(this.dataset.id,this.dataset.title,this.dataset.url,this.dataset.channel)" title="Bookmark">&#9733;</button>
        </a>`;
    }).join("");
}

// ── Channel Breakdown (sortable) ─────────────────────────────────────────────
function renderChannelBreakdown(channels) {
    const container = document.getElementById("channels-content");
    if (!channels.length) { container.innerHTML = '<div class="loading">No channel data</div>'; return; }

    const renderRow = ch => `
        <tr>
            <td>${esc(ch.channel_name)}</td>
            <td>${esc(ch.channel_handle)}</td>
            <td>${ch.videos_scraped || 0}</td>
            <td>${formatNumber(ch.total_views)}</td>
            <td>${formatNumber(ch.avg_views)}</td>
            <td><span class="format-badge">${esc(ch.most_common_format || "—")}</span></td>
            <td>${esc(ch.posting_frequency || "—")}</td>
        </tr>
    `;

    container.innerHTML = `
        <table class="channel-table">
            <thead>
                <tr>
                    <th>Channel</th>
                    <th>Handle</th>
                    <th>Videos</th>
                    <th>Total Views</th>
                    <th>Avg Views</th>
                    <th>Format</th>
                    <th>Frequency</th>
                </tr>
            </thead>
            <tbody>${channels.map(renderRow).join("")}</tbody>
        </table>
    `;

    makeSortable(container.querySelector(".channel-table"), channels, renderRow, {
        0: { value: ch => (ch.channel_name || "").toLowerCase() },
        2: { value: ch => ch.videos_scraped || 0 },
        3: { value: ch => ch.total_views || 0 },
        4: { value: ch => ch.avg_views || 0 },
        5: { value: ch => (ch.most_common_format || "").toLowerCase() },
        6: { value: ch => (ch.posting_frequency || "").toLowerCase() }
    });
}

// ── All Videos by Creator (with engagement rate, sortable, bookmarks) ────────
function renderAllVideosByCreator(videos) {
    const container = document.getElementById("all-videos-content");
    if (!videos.length) { container.innerHTML = '<div class="loading">No video data</div>'; return; }

    const grouped = {};
    videos.forEach(v => {
        const ch = v.channel_name || "Unknown";
        if (!grouped[ch]) grouped[ch] = [];
        grouped[ch].push(v);
    });

    const channelNames = Object.keys(grouped).sort();

    container.innerHTML = channelNames.map(ch => {
        const vids = grouped[ch];

        const renderRow = v => {
            const eng = calcEngagement(v);
            const vid = v.video_id || v.url || "";
            const bm = isVideoBookmarked(vid) ? "bookmarked" : "";
            return `
            <tr>
                <td>
                    <a href="${esc(v.url)}" target="_blank" rel="noopener" class="creator-video-link">
                        <img class="creator-thumb" src="${esc(v.thumbnail_url)}" alt=""
                             onerror="this.style.display='none'">
                        <span>${esc(v.title)}</span>
                    </a>
                </td>
                <td>${formatNumber(v.view_count)} views</td>
                <td>${formatNumber(v.like_count)} likes</td>
                <td>${engagementBadge(eng)}</td>
                <td>${v.duration_formatted || "—"}</td>
                <td>${v.published_date ? new Date(v.published_date).toLocaleDateString() : "—"}</td>
                <td><button class="bookmark-video ${bm}" data-id="${esc(vid)}" data-title="${esc(v.title)}" data-url="${esc(v.url)}" data-channel="${esc(v.channel_name)}" onclick="toggleBookmarkVideo(this.dataset.id,this.dataset.title,this.dataset.url,this.dataset.channel)" title="Bookmark">&#9733;</button></td>
            </tr>`;
        };

        const totalViews = vids.reduce((s, v) => s + (v.view_count || 0), 0);

        return `
            <div class="creator-group">
                <div class="creator-header">
                    <span class="creator-name">${esc(ch)}</span>
                    <span class="creator-handle">${esc(vids[0]?.channel_handle || "")}</span>
                    <span class="creator-stats">${vids.length} videos &middot; ${formatNumber(totalViews)} total views</span>
                </div>
                <table class="creator-table" data-channel="${esc(ch)}">
                    <thead>
                        <tr><th>Video</th><th>Views</th><th>Likes</th><th>Eng. Rate</th><th>Duration</th><th>Published</th><th></th></tr>
                    </thead>
                    <tbody>${vids.map(renderRow).join("")}</tbody>
                </table>
            </div>
        `;
    }).join("");

    // Make each creator table sortable
    container.querySelectorAll(".creator-table").forEach(table => {
        const ch = table.dataset.channel;
        const vids = grouped[ch];
        const renderRow = v => {
            const eng = calcEngagement(v);
            const vid = v.video_id || v.url || "";
            const bm = isVideoBookmarked(vid) ? "bookmarked" : "";
            return `
            <tr>
                <td>
                    <a href="${esc(v.url)}" target="_blank" rel="noopener" class="creator-video-link">
                        <img class="creator-thumb" src="${esc(v.thumbnail_url)}" alt=""
                             onerror="this.style.display='none'">
                        <span>${esc(v.title)}</span>
                    </a>
                </td>
                <td>${formatNumber(v.view_count)} views</td>
                <td>${formatNumber(v.like_count)} likes</td>
                <td>${engagementBadge(eng)}</td>
                <td>${v.duration_formatted || "—"}</td>
                <td>${v.published_date ? new Date(v.published_date).toLocaleDateString() : "—"}</td>
                <td><button class="bookmark-video ${bm}" data-id="${esc(vid)}" data-title="${esc(v.title)}" data-url="${esc(v.url)}" data-channel="${esc(v.channel_name)}" onclick="toggleBookmarkVideo(this.dataset.id,this.dataset.title,this.dataset.url,this.dataset.channel)" title="Bookmark">&#9733;</button></td>
            </tr>`;
        };
        makeSortable(table, vids, renderRow, {
            1: { value: v => v.view_count || 0 },
            2: { value: v => v.like_count || 0 },
            3: { value: v => calcEngagement(v) },
            4: { value: v => (v.duration_formatted || "").length },
            5: { value: v => v.published_date ? new Date(v.published_date).getTime() : 0 }
        });
    });
}

// ── Suggested Content Topics (with brief button + pipeline + bookmark) ───────
let _suggestedTopicsData = [];

function renderSuggestedTopics(topics) {
    const container = document.getElementById("suggested-topics-content");
    if (!topics.length) { container.innerHTML = '<div class="loading">No topic suggestions</div>'; return; }

    _suggestedTopicsData = topics;

    container.innerHTML = `<div class="topics-grid">${
        topics.map((t, i) => {
            const bm = isTopicBookmarked(t.topic) ? "bookmarked" : "";
            return `
            <div class="topic-card" data-topic-idx="${i}">
                <div class="topic-card-header">
                    <h3>${esc(t.topic)}</h3>
                    <button class="bookmark-topic ${bm}" data-topic-idx="${i}" title="Bookmark">&#9733;</button>
                </div>
                <div class="topic-angle">${esc(t.angle)}</div>
                <div class="topic-why">${esc(t.why_now)}</div>
                <div class="topic-meta">
                    ${t.target_format ? `<span class="topic-tag format">${esc(t.target_format)}</span>` : ""}
                    ${t.competition_level ? `<span class="topic-tag competition-${t.competition_level}">${esc(t.competition_level)} competition</span>` : ""}
                </div>
                ${t.reference_videos?.length ? `<div class="topic-refs">Inspired by: ${t.reference_videos.map(esc).join(", ")}</div>` : ""}
                <div class="topic-actions">
                    <button class="brief-btn btn-secondary" data-topic-idx="${i}">Expand Brief</button>
                    <button class="pipeline-btn btn-secondary" data-topic-idx="${i}">Add to Pipeline</button>
                </div>
            </div>`;
        }).join("")
    }</div>`;

    // Attach all button handlers via event delegation (no inline onclick)
    container.querySelectorAll(".brief-btn").forEach(btn => {
        btn.addEventListener("click", function(e) {
            e.preventDefault();
            e.stopPropagation();
            const idx = parseInt(this.dataset.topicIdx);
            const topicData = _suggestedTopicsData[idx];
            if (topicData) generateBrief(this, topicData);
        });
    });

    container.querySelectorAll(".pipeline-btn").forEach(btn => {
        btn.addEventListener("click", function() {
            const idx = parseInt(this.dataset.topicIdx);
            const t = _suggestedTopicsData[idx];
            if (t) addToPipeline(t.topic, t.target_format || "", t.competition_level || "");
        });
    });

    container.querySelectorAll(".bookmark-topic").forEach(btn => {
        btn.addEventListener("click", function() {
            const idx = parseInt(this.dataset.topicIdx);
            const t = _suggestedTopicsData[idx];
            if (t) toggleBookmarkTopic(t.topic);
        });
    });
}

// ── Content Opportunities (with pipeline button) ─────────────────────────────
function renderOpportunities(opportunities) {
    const container = document.getElementById("opportunities-content");
    if (!opportunities.length) { container.innerHTML = '<div class="loading">No opportunities identified</div>'; return; }

    container.innerHTML = `<div class="opportunity-list">${
        opportunities.map(o => `
            <div class="opportunity-card">
                <h3>${esc(o.idea)}</h3>
                <p>${esc(o.reasoning)}</p>
                <div class="opportunity-meta">
                    ${o.format_suggestion ? `<span class="opportunity-tag format">${esc(o.format_suggestion)}</span>` : ""}
                    ${o.estimated_interest ? `<span class="opportunity-tag interest-${o.estimated_interest}">${esc(o.estimated_interest)} interest</span>` : ""}
                </div>
                <div class="topic-actions">
                    <button class="pipeline-btn btn-secondary" onclick="addToPipeline('${esc(o.idea)}','${esc(o.format_suggestion || "")}','')">Add to Pipeline</button>
                </div>
            </div>
        `).join("")
    }</div>`;
}

// ── Title Patterns ───────────────────────────────────────────────────────────
function renderPatterns(patterns) {
    const container = document.getElementById("patterns-content");
    if (!patterns.length) { container.innerHTML = '<div class="loading">No pattern data</div>'; return; }

    container.innerHTML = `<div class="pattern-list">${
        patterns.map(p => `
            <div class="pattern-item">
                <div class="pattern-header">
                    <span class="pattern-name">${esc(p.pattern)}</span>
                    <span class="pattern-count">${p.count || 0}x</span>
                </div>
                ${p.examples?.length ? `<div class="pattern-examples">"${p.examples.slice(0, 2).map(esc).join('", "')}"</div>` : ""}
            </div>
        `).join("")
    }</div>`;
}

// ── Error State ──────────────────────────────────────────────────────────────
function showError(msg) {
    document.querySelectorAll(".card-body").forEach(el => {
        el.innerHTML = `
            <div class="error-state">
                <p>No data available</p>
                <code>bash run.sh</code>
                <p style="margin-top: 0.5rem; font-size: 0.8rem">${esc(msg)}</p>
            </div>
        `;
    });
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function esc(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
}

function formatNumber(n) {
    if (n == null) return "0";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return String(n);
}

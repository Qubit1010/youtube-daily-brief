/**
 * YouTube Intelligence Dashboard — Client-Side Renderer
 * Fetches data from /api/data and renders all dashboard sections.
 */

document.addEventListener("DOMContentLoaded", () => {
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

    renderLastUpdated(analysis.analyzed_at || raw.scraped_at);
    renderTrending(analysis.trending_topics || []);
    renderSentiment(analysis.sentiment || {});
    renderTopPerforming(analysis.top_performing || []);
    renderChannelBreakdown(analysis.channel_breakdown || []);
    renderAllVideosByCreator(raw.videos || []);
    renderSuggestedTopics(analysis.suggested_topics || []);
    renderOpportunities(analysis.content_opportunities || []);
    renderPatterns(analysis.title_patterns || []);
}

// ── Last Updated ──────────────────────────────────────────────────────────────
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

// ── Trending Topics ───────────────────────────────────────────────────────────
function renderTrending(topics) {
    const container = document.getElementById("trending-content");
    if (!topics.length) { container.innerHTML = '<div class="loading">No trending data</div>'; return; }

    const pills = topics.map(t =>
        `<span class="topic-pill" title="${esc(t.summary || '')}">
            ${esc(t.topic)}
            <span class="count">${t.mention_count || ""}</span>
        </span>`
    ).join("");

    // Show summary of top topic
    const topSummary = topics[0]?.summary
        ? `<div class="topic-summary"><strong>${esc(topics[0].topic)}:</strong> ${esc(topics[0].summary)}</div>`
        : "";

    container.innerHTML = `<div class="topic-pills">${pills}</div>${topSummary}`;
}

// ── Sentiment ─────────────────────────────────────────────────────────────────
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

// ── Top Performing Videos ─────────────────────────────────────────────────────
function renderTopPerforming(videos) {
    const container = document.getElementById("top-videos-content");
    if (!videos.length) { container.innerHTML = '<div class="loading">No video data</div>'; return; }

    container.innerHTML = videos.map(v => `
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
        </a>
    `).join("");
}

// ── Channel Breakdown ─────────────────────────────────────────────────────────
function renderChannelBreakdown(channels) {
    const container = document.getElementById("channels-content");
    if (!channels.length) { container.innerHTML = '<div class="loading">No channel data</div>'; return; }

    const rows = channels.map(ch => `
        <tr>
            <td>${esc(ch.channel_name)}</td>
            <td>${esc(ch.channel_handle)}</td>
            <td>${ch.videos_scraped || 0}</td>
            <td>${formatNumber(ch.total_views)}</td>
            <td>${formatNumber(ch.avg_views)}</td>
            <td><span class="format-badge">${esc(ch.most_common_format || "—")}</span></td>
            <td>${esc(ch.posting_frequency || "—")}</td>
        </tr>
    `).join("");

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
            <tbody>${rows}</tbody>
        </table>
    `;
}

// ── All Videos by Creator ─────────────────────────────────────────────────────
function renderAllVideosByCreator(videos) {
    const container = document.getElementById("all-videos-content");
    if (!videos.length) { container.innerHTML = '<div class="loading">No video data</div>'; return; }

    // Group by channel
    const grouped = {};
    videos.forEach(v => {
        const ch = v.channel_name || "Unknown";
        if (!grouped[ch]) grouped[ch] = [];
        grouped[ch].push(v);
    });

    // Sort channels alphabetically
    const channels = Object.keys(grouped).sort();

    container.innerHTML = channels.map(ch => {
        const vids = grouped[ch];
        const rows = vids.map(v => `
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
                <td>${v.duration_formatted || "—"}</td>
                <td>${v.published_date ? new Date(v.published_date).toLocaleDateString() : "—"}</td>
            </tr>
        `).join("");

        const totalViews = vids.reduce((s, v) => s + (v.view_count || 0), 0);

        return `
            <div class="creator-group">
                <div class="creator-header">
                    <span class="creator-name">${esc(ch)}</span>
                    <span class="creator-handle">${esc(vids[0]?.channel_handle || "")}</span>
                    <span class="creator-stats">${vids.length} videos &middot; ${formatNumber(totalViews)} total views</span>
                </div>
                <table class="creator-table">
                    <thead>
                        <tr><th>Video</th><th>Views</th><th>Likes</th><th>Duration</th><th>Published</th></tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }).join("");
}

// ── Suggested Content Topics ─────────────────────────────────────────────────
function renderSuggestedTopics(topics) {
    const container = document.getElementById("suggested-topics-content");
    if (!topics.length) { container.innerHTML = '<div class="loading">No topic suggestions</div>'; return; }

    container.innerHTML = `<div class="topics-grid">${
        topics.map(t => `
            <div class="topic-card">
                <h3>${esc(t.topic)}</h3>
                <div class="topic-angle">${esc(t.angle)}</div>
                <div class="topic-why">${esc(t.why_now)}</div>
                <div class="topic-meta">
                    ${t.target_format ? `<span class="topic-tag format">${esc(t.target_format)}</span>` : ""}
                    ${t.competition_level ? `<span class="topic-tag competition-${t.competition_level}">${esc(t.competition_level)} competition</span>` : ""}
                </div>
                ${t.reference_videos?.length ? `<div class="topic-refs">Inspired by: ${t.reference_videos.map(esc).join(", ")}</div>` : ""}
            </div>
        `).join("")
    }</div>`;
}

// ── Content Opportunities ─────────────────────────────────────────────────────
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
            </div>
        `).join("")
    }</div>`;
}

// ── Title Patterns ────────────────────────────────────────────────────────────
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

// ── Error State ───────────────────────────────────────────────────────────────
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

// ── Helpers ───────────────────────────────────────────────────────────────────
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

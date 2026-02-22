// ─── Shared Pipeline Trace Renderer ───
// Used by both chat.js and eval.js

const ZINC_500 = "#71717a";
const ZINC_600 = "#52525b";
const ZINC_700 = "#3f3f46";

const CALL_TYPE_CONFIG = {
    mem0_search: { icon: "M", color: ZINC_600, label: "Mem0" },
    llm_call: { icon: "AI", color: ZINC_700, label: "LLM" },
    http_fetch: { icon: "H", color: ZINC_500, label: "HTTP" },
    computation: { icon: "C", color: ZINC_600, label: "Compute" },
    agent_call: { icon: "A", color: ZINC_700, label: "Agent" },
};

function getCallTypeConfig(callType) {
    return CALL_TYPE_CONFIG[callType] || { icon: "?", color: ZINC_500, label: callType };
}

function getConfidenceColor(confidence) {
    if (confidence >= 0.8) return "#52525b";
    if (confidence >= 0.5) return "#71717a";
    return "#3f3f46";
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return "confidence-high";
    if (confidence >= 0.5) return "confidence-mid";
    return "confidence-low";
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function formatDetailLabel(key) {
    return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

function buildEventHtml(event, index) {
    const config = getCallTypeConfig(event.call_type);
    const statusClass = event.status || 'completed';
    const durationLabel = event.duration_ms > 0 ? `${event.duration_ms}ms` : '';

    const details = event.details || {};
    let detailsHtml = '';
    if (Object.keys(details).length > 0) {
        detailsHtml = buildEventDetails(details);
    }

    return `
        <div class="trace-event" data-status="${statusClass}" data-call-type="${event.call_type}">
            <div class="event-connector">
                <div class="event-dot ${statusClass}" style="border-color:${config.color}${statusClass === 'completed' ? ';background:' + config.color : ''}">
                    <span class="event-dot-label">${config.icon}</span>
                </div>
                ${index < 999 ? '<div class="event-line"></div>' : ''}
            </div>
            <div class="event-content">
                <div class="event-header">
                    <div class="event-title-area">
                        <div class="event-title">
                            <span class="call-type-badge" style="background:${config.color}15;color:${config.color}">${config.label}</span>
                            ${escapeHtml(event.label)}
                        </div>
                        <div class="event-summary">
                            ${event.input_summary ? '<span class="event-input">' + escapeHtml(event.input_summary) + '</span>' : ''}
                            ${event.output_summary ? '<span class="event-output">' + escapeHtml(event.output_summary) + '</span>' : ''}
                        </div>
                    </div>
                    <div class="event-meta">
                        ${statusClass === 'error' ? '<span class="event-status-badge error">ERROR</span>' : ''}
                        ${statusClass === 'skipped' ? '<span class="event-status-badge skipped">SKIPPED</span>' : ''}
                        ${durationLabel ? `<span class="event-duration">${durationLabel}</span>` : ''}
                        <span class="event-chevron">&#9654;</span>
                    </div>
                </div>
                ${detailsHtml ? `<div class="event-details">${detailsHtml}</div>` : ''}
                ${event.error_message ? `<div class="event-error">${escapeHtml(event.error_message)}</div>` : ''}
            </div>
        </div>
    `;
}

function buildEventDetails(details) {
    let html = '';

    for (const [key, value] of Object.entries(details)) {
        if (value === null || value === undefined) continue;

        const label = formatDetailLabel(key);

        if (typeof value === 'object' && !Array.isArray(value)) {
            html += `
                <div class="detail-subsection">
                    <span class="label">${escapeHtml(label)}</span>
                    <div class="detail-scrollable">${escapeHtml(JSON.stringify(value, null, 2))}</div>
                </div>
            `;
        } else if (Array.isArray(value)) {
            if (value.length === 0) {
                html += `
                    <div class="detail-row">
                        <span class="label">${escapeHtml(label)}</span>
                        <span class="value">[] (empty)</span>
                    </div>
                `;
            } else if (typeof value[0] === 'object') {
                html += `
                    <div class="detail-subsection">
                        <span class="label">${escapeHtml(label)} (${value.length})</span>
                        <div class="detail-scrollable">${escapeHtml(JSON.stringify(value, null, 2))}</div>
                    </div>
                `;
            } else {
                html += `
                    <div class="detail-row">
                        <span class="label">${escapeHtml(label)}</span>
                        <span class="value">${escapeHtml(value.join(', '))}</span>
                    </div>
                `;
            }
        } else if (typeof value === 'number' && key.toLowerCase().includes('confidence')) {
            const pct = (value * 100).toFixed(0);
            const color = getConfidenceColor(value);
            html += `
                <div class="detail-row">
                    <span class="label">${escapeHtml(label)}</span>
                    <span class="value">
                        ${pct}%
                        <span class="confidence-mini-bar">
                            <span class="confidence-mini-bar-fill" style="width:${pct}%;background:${color}"></span>
                        </span>
                    </span>
                </div>
            `;
        } else if (typeof value === 'boolean') {
            html += `
                <div class="detail-row">
                    <span class="label">${escapeHtml(label)}</span>
                    <span class="value">${value ? 'Yes' : 'No'}</span>
                </div>
            `;
        } else if (typeof value === 'string' && value.length > 120) {
            html += `
                <div class="detail-subsection">
                    <span class="label">${escapeHtml(label)}</span>
                    <div class="detail-scrollable">${escapeHtml(value)}</div>
                </div>
            `;
        } else {
            html += `
                <div class="detail-row">
                    <span class="label">${escapeHtml(label)}</span>
                    <span class="value">${escapeHtml(String(value))}</span>
                </div>
            `;
        }
    }

    return html;
}

function buildResponseSummary(content, confidence) {
    const confPct = ((confidence || 0) * 100).toFixed(0);
    const confColor = getConfidenceColor(confidence || 0);

    return `
        <div class="response-summary">
            <div class="detail-row">
                <span class="label">Final Response</span>
                <span class="value">
                    ${confPct}% confidence
                    <span class="confidence-mini-bar">
                        <span class="confidence-mini-bar-fill" style="width:${confPct}%;background:${confColor}"></span>
                    </span>
                </span>
            </div>
            <div class="detail-scrollable" style="max-height:200px">${escapeHtml(content)}</div>
        </div>
    `;
}

function renderPipelineTrace(trace, totalMs, container) {
    if (!trace || trace.length === 0) {
        container.innerHTML = '<p class="hint">No trace data available.</p>';
        return;
    }

    let html = '<div class="pipeline-timeline">';
    for (let i = 0; i < trace.length; i++) {
        html += buildEventHtml(trace[i], i);
    }
    html += '</div>';

    container.innerHTML = html;

    container.querySelectorAll('.event-header').forEach(header => {
        header.addEventListener('click', () => {
            const eventEl = header.closest('.trace-event');
            eventEl.classList.toggle('expanded');
        });
    });
}

// State
let ws = null;
let sessionId = null;
let editingMessageIndex = null;
const pipelineTraces = new Map();
const pipelineDurations = new Map();
let messageCounter = 0;

// DOM elements
const chatMessages = document.getElementById("chat-messages");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const newSessionBtn = document.getElementById("new-session-btn");
const sessionInfo = document.getElementById("session-info");
const detailContent = document.getElementById("detail-content");
const editModal = document.getElementById("edit-modal");
const editTextarea = document.getElementById("edit-textarea");
const editSaveBtn = document.getElementById("edit-save");
const editCancelBtn = document.getElementById("edit-cancel");
const panelTotalTime = document.getElementById("panel-total-time");

// ─── Session management ───

newSessionBtn.addEventListener("click", createSession);

async function createSession() {
    if (ws) {
        ws.close();
        ws = null;
    }

    const res = await fetch("/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
    });
    const data = await res.json();
    sessionId = data.session_id;

    chatMessages.innerHTML = "";
    pipelineTraces.clear();
    pipelineDurations.clear();
    messageCounter = 0;

    if (panelTotalTime) panelTotalTime.textContent = "";
    detailContent.innerHTML = '<p class="hint">Send a message to see the pipeline trace.</p>';

    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${location.host}/chat/ws/${sessionId}`);

    ws.onopen = () => {
        sessionInfo.textContent = `Session: ${sessionId.slice(0, 8)}...`;
        messageInput.disabled = false;
        sendBtn.disabled = false;
        messageInput.focus();
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
    };

    ws.onclose = () => {
        sessionInfo.textContent = "Disconnected";
    };

    ws.onerror = () => {
        sessionInfo.textContent = "Connection error";
    };
}

// ─── Send message ───

sendBtn.addEventListener("click", sendMessage);

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    appendMessage("user", text);
    ws.send(JSON.stringify({ type: "user_message", content: text }));
    messageInput.value = "";

    showTypingIndicator();
}

// ─── Server message handling ───

function handleServerMessage(msg) {
    removeTypingIndicator();

    switch (msg.type) {
        case "ai_response":
            appendAssistantMessage(msg.content, {
                confidence: msg.confidence,
                reasoning: msg.reasoning,
                status: "sent",
                autoSent: msg.auto_sent || false,
                pipelineTrace: msg.pipeline_trace || [],
                totalDurationMs: msg.total_duration_ms || 0,
            });
            break;

        case "review_request":
            appendAssistantMessage(msg.content, {
                confidence: msg.confidence,
                reasoning: msg.reasoning,
                status: "pending",
                messageIndex: msg.message_index,
                pipelineTrace: msg.pipeline_trace || [],
                totalDurationMs: msg.total_duration_ms || 0,
            });
            break;

        case "response_approved":
            updateDraftStatus(msg.message_index, "approved", msg.content);
            break;

        case "response_edited":
            updateDraftStatus(msg.message_index, "edited", msg.content);
            break;

        case "response_rejected":
            updateDraftStatus(msg.message_index, "rejected");
            break;

        case "error":
            appendSystemMessage(msg.message);
            break;
    }
}

// ─── Message rendering ───

function appendMessage(role, content) {
    const wrapper = document.createElement("div");
    wrapper.className = `message-wrapper ${role}`;

    const bubble = document.createElement("div");
    bubble.className = `message ${role}`;
    bubble.textContent = content;

    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);
    scrollToBottom();
}

function appendAssistantMessage(content, opts = {}) {
    const msgId = opts.messageIndex !== undefined
        ? opts.messageIndex
        : `auto_${messageCounter++}`;

    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper assistant";
    wrapper.dataset.msgId = msgId;
    if (opts.messageIndex !== undefined) {
        wrapper.dataset.messageIndex = opts.messageIndex;
    }

    const bubble = document.createElement("div");
    bubble.className = `message assistant ${opts.status === "pending" ? "pending" : ""}`;
    bubble.textContent = content;

    // Store pipeline trace and duration
    if (opts.pipelineTrace && opts.pipelineTrace.length > 0) {
        pipelineTraces.set(String(msgId), opts.pipelineTrace);
        pipelineDurations.set(String(msgId), opts.totalDurationMs || 0);
    }

    // Click to show pipeline trace
    bubble.addEventListener("click", () => {
        showPipelineTrace(String(msgId), content, opts.confidence, opts.reasoning);
    });

    wrapper.appendChild(bubble);

    // Confidence badge
    if (opts.confidence !== undefined) {
        const badge = document.createElement("span");
        badge.className = `confidence-badge ${getConfidenceClass(opts.confidence)}`;
        badge.textContent = `Confidence: ${(opts.confidence * 100).toFixed(0)}%`;
        wrapper.appendChild(badge);
    }

    // Review action buttons
    if (opts.status === "pending" && opts.messageIndex !== undefined) {
        const actions = document.createElement("div");
        actions.className = "review-actions";

        const approveBtn = document.createElement("button");
        approveBtn.className = "btn btn-approve";
        approveBtn.textContent = "Approve";
        approveBtn.addEventListener("click", () =>
            approveResponse(opts.messageIndex)
        );

        const editBtn = document.createElement("button");
        editBtn.className = "btn btn-edit";
        editBtn.textContent = "Edit";
        editBtn.addEventListener("click", () =>
            openEditModal(opts.messageIndex, content)
        );

        const rejectBtn = document.createElement("button");
        rejectBtn.className = "btn btn-reject";
        rejectBtn.textContent = "Reject";
        rejectBtn.addEventListener("click", () =>
            rejectResponse(opts.messageIndex)
        );

        actions.appendChild(approveBtn);
        actions.appendChild(editBtn);
        actions.appendChild(rejectBtn);
        wrapper.appendChild(actions);
    }

    // Status label for auto-sent messages
    if (opts.status === "sent" && opts.autoSent) {
        const label = document.createElement("span");
        label.className = "status-label";
        label.textContent = "Auto-sent (high confidence)";
        wrapper.appendChild(label);
    }

    chatMessages.appendChild(wrapper);
    scrollToBottom();

    // Auto-show pipeline trace for latest message
    showPipelineTrace(String(msgId), content, opts.confidence, opts.reasoning);
}

function appendSystemMessage(content) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper assistant";

    const bubble = document.createElement("div");
    bubble.className = "message assistant";
    bubble.style.color = "#ef4444";
    bubble.style.fontStyle = "italic";
    bubble.textContent = content;

    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);
    scrollToBottom();
}

function updateDraftStatus(messageIndex, status, newContent) {
    const wrapper = chatMessages.querySelector(
        `[data-message-index="${messageIndex}"]`
    );
    if (!wrapper) return;

    const bubble = wrapper.querySelector(".message");

    bubble.classList.remove("pending");

    const actions = wrapper.querySelector(".review-actions");
    if (actions) actions.remove();

    if (status === "rejected") {
        bubble.classList.add("rejected");
    }

    if (newContent) {
        bubble.textContent = newContent;
    }

    const label = document.createElement("span");
    label.className = "status-label";
    const statusText = {
        approved: "Approved & sent",
        edited: "Edited & sent",
        rejected: "Rejected",
    };
    label.textContent = statusText[status] || status;
    wrapper.appendChild(label);
}

// ─── Typing indicator ───

function showTypingIndicator() {
    const existing = chatMessages.querySelector(".typing-wrapper");
    if (existing) return;

    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper assistant typing-wrapper";

    const indicator = document.createElement("div");
    indicator.className = "message assistant typing-indicator";
    indicator.innerHTML = "<span></span><span></span><span></span>";

    wrapper.appendChild(indicator);
    chatMessages.appendChild(wrapper);
    scrollToBottom();
}

function removeTypingIndicator() {
    const indicator = chatMessages.querySelector(".typing-wrapper");
    if (indicator) indicator.remove();
}

// ─── Pipeline Trace Panel ───

// Map call_type to display icon/color
const CALL_TYPE_CONFIG = {
    mem0_search: { icon: "M", color: "#8b5cf6", label: "Mem0" },
    llm_call: { icon: "AI", color: "#4f6ef7", label: "LLM" },
    http_fetch: { icon: "H", color: "#06b6d4", label: "HTTP" },
    computation: { icon: "C", color: "#10b981", label: "Compute" },
    agent_call: { icon: "A", color: "#f59e0b", label: "Agent" },
};

function getCallTypeConfig(callType) {
    return CALL_TYPE_CONFIG[callType] || { icon: "?", color: "#8b90a0", label: callType };
}

function showPipelineTrace(msgId, content, confidence, reasoning) {
    const trace = pipelineTraces.get(msgId);

    if (!trace || trace.length === 0) {
        showLegacyDetails(content, confidence, reasoning);
        return;
    }

    // Get total pipeline time from stored duration or sum events
    const totalMs = pipelineDurations.get(msgId) ||
        trace.reduce((sum, ev) => sum + (ev.duration_ms || 0), 0);

    if (panelTotalTime) {
        panelTotalTime.textContent = `${totalMs}ms total`;
    }

    // Build timeline HTML from flat event list
    let html = '<div class="pipeline-timeline">';
    for (let i = 0; i < trace.length; i++) {
        html += buildEventHtml(trace[i], i);
    }
    html += '</div>';

    // Final response summary
    html += buildResponseSummary(content, confidence);

    detailContent.innerHTML = html;

    // Attach expand/collapse click handlers
    detailContent.querySelectorAll('.event-header').forEach(header => {
        header.addEventListener('click', () => {
            const eventEl = header.closest('.trace-event');
            eventEl.classList.toggle('expanded');
        });
    });
}

function buildEventHtml(event, index) {
    const config = getCallTypeConfig(event.call_type);
    const statusClass = event.status || 'completed';
    const durationLabel = event.duration_ms > 0 ? `${event.duration_ms}ms` : '';

    // Build details HTML
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
            // Nested object — render as scrollable JSON
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
            // Confidence with mini-bar
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
            // Long strings in scrollable container
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

function formatDetailLabel(key) {
    return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
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

// ─── Legacy Detail Panel (fallback) ───

function showLegacyDetails(content, confidence, reasoning) {
    if (panelTotalTime) panelTotalTime.textContent = "";

    let html = "";

    if (confidence !== undefined) {
        const pct = (confidence * 100).toFixed(1);
        const color = getConfidenceColor(confidence);

        html += `
            <div class="detail-section">
                <label>Confidence</label>
                <div class="value">${pct}%</div>
                <div class="confidence-bar">
                    <div class="confidence-bar-fill" style="width: ${pct}%; background: ${color};"></div>
                </div>
            </div>
        `;
    }

    if (reasoning) {
        html += `
            <div class="detail-section">
                <label>Reasoning</label>
                <div class="value">${escapeHtml(reasoning)}</div>
            </div>
        `;
    }

    html += `
        <div class="detail-section">
            <label>Response</label>
            <div class="value">${escapeHtml(content)}</div>
        </div>
    `;

    detailContent.innerHTML = html;
}

// ─── Approve / Edit / Reject ───

function approveResponse(messageIndex) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
        JSON.stringify({ type: "approve", message_index: messageIndex })
    );
}

function openEditModal(messageIndex, currentText) {
    editingMessageIndex = messageIndex;
    editTextarea.value = currentText;
    editModal.classList.remove("hidden");
    editTextarea.focus();
}

function rejectResponse(messageIndex) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
        JSON.stringify({ type: "reject", message_index: messageIndex })
    );
}

editSaveBtn.addEventListener("click", () => {
    const newText = editTextarea.value.trim();
    if (!newText || editingMessageIndex === null) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(
        JSON.stringify({
            type: "edit",
            message_index: editingMessageIndex,
            content: newText,
        })
    );

    editModal.classList.add("hidden");
    editingMessageIndex = null;
});

editCancelBtn.addEventListener("click", () => {
    editModal.classList.add("hidden");
    editingMessageIndex = null;
});

document.querySelector(".modal-backdrop")?.addEventListener("click", () => {
    editModal.classList.add("hidden");
    editingMessageIndex = null;
});

// ─── Utilities ───

function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return "confidence-high";
    if (confidence >= 0.5) return "confidence-mid";
    return "confidence-low";
}

function getConfidenceColor(confidence) {
    if (confidence >= 0.8) return '#10b981';
    if (confidence >= 0.5) return '#f59e0b';
    return '#ef4444';
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

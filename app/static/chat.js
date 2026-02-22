// State
let ws = null;
let sessionId = null;
let editingMessageIndex = null;
const pipelineTraces = new Map();
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
    // Close existing WebSocket
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

    // Clear chat and traces
    chatMessages.innerHTML = "";
    pipelineTraces.clear();
    messageCounter = 0;

    // Reset detail panel
    if (panelTotalTime) panelTotalTime.textContent = "";
    detailContent.innerHTML = '<p class="hint">Send a message to see the pipeline trace.</p>';

    // Connect WebSocket
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

    // Show typing indicator
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
            });
            break;

        case "review_request":
            appendAssistantMessage(msg.content, {
                confidence: msg.confidence,
                reasoning: msg.reasoning,
                status: "pending",
                messageIndex: msg.message_index,
                pipelineTrace: msg.pipeline_trace || [],
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

    // Store pipeline trace
    if (opts.pipelineTrace && opts.pipelineTrace.length > 0) {
        pipelineTraces.set(String(msgId), opts.pipelineTrace);
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

    // Review action buttons (manual mode, pending status)
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

    // Status label for auto-sent messages (high confidence)
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

    // Remove pending styling
    bubble.classList.remove("pending");

    // Remove action buttons
    const actions = wrapper.querySelector(".review-actions");
    if (actions) actions.remove();

    if (status === "rejected") {
        bubble.classList.add("rejected");
    }

    if (newContent) {
        bubble.textContent = newContent;
    }

    // Add status label
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

function showPipelineTrace(msgId, content, confidence, reasoning) {
    const trace = pipelineTraces.get(msgId);

    if (!trace || trace.length === 0) {
        // Fallback for messages without trace data
        showLegacyDetails(content, confidence, reasoning);
        return;
    }

    // Calculate total pipeline time
    const totalMs = trace.reduce((sum, step) => sum + (step.duration_ms || 0), 0);

    // Update panel header
    if (panelTotalTime) {
        panelTotalTime.textContent = `${totalMs}ms total`;
    }

    // Build timeline HTML
    let html = '<div class="pipeline-timeline">';
    for (const step of trace) {
        html += buildStepHtml(step);
    }
    html += '</div>';

    // Add final response summary
    html += buildResponseSummary(content, confidence);

    detailContent.innerHTML = html;

    // Attach expand/collapse click handlers
    detailContent.querySelectorAll('.step-header').forEach(header => {
        header.addEventListener('click', () => {
            const stepEl = header.closest('.pipeline-step');
            stepEl.classList.toggle('expanded');
        });
    });
}

function buildStepHtml(step) {
    const statusClass = step.status || 'completed';
    const details = step.details || {};

    let detailsHtml = '';
    switch (step.step_number) {
        case 1:
            detailsHtml = buildMemoryStepDetails(details);
            break;
        case 2:
            detailsHtml = buildResponseStepDetails(details);
            break;
        case 3:
            detailsHtml = buildPostProcessingStepDetails(details);
            break;
        case 4:
            detailsHtml = buildRoutingStepDetails(details);
            break;
        default:
            detailsHtml = `<div class="detail-scrollable">${escapeHtml(JSON.stringify(details, null, 2))}</div>`;
    }

    const durationLabel = step.duration_ms > 0 ? `${step.duration_ms}ms` : '';

    return `
        <div class="pipeline-step">
            <div class="step-dot ${statusClass}"></div>
            <div class="step-header">
                <div class="step-title-area">
                    <div class="step-title">${escapeHtml(step.step_name)}</div>
                    <div class="step-summary">${escapeHtml(step.summary)}</div>
                </div>
                <div class="step-meta">
                    ${durationLabel ? `<span class="step-duration">${durationLabel}</span>` : ''}
                    <span class="step-chevron">&#9654;</span>
                </div>
            </div>
            <div class="step-details">
                ${detailsHtml}
            </div>
        </div>
    `;
}

// ─── Step-Specific Detail Builders ───

function buildMemoryStepDetails(details) {
    const boostText = details.confidence_boost > 0
        ? `+${(details.confidence_boost * 100).toFixed(0)}%`
        : 'None';

    let html = `
        <div class="detail-row">
            <span class="label">Conv. History</span>
            <span class="value">${details.conversation_history_count || 0} turns</span>
        </div>
        <div class="detail-row">
            <span class="label">Global Matches</span>
            <span class="value">${details.global_matches_count || 0} found</span>
        </div>
        <div class="detail-row">
            <span class="label">Confidence Boost</span>
            <span class="value">${boostText}</span>
        </div>
    `;

    if (details.conversation_history && details.conversation_history.length > 0) {
        html += `
            <div class="detail-subsection">
                <span class="label">Conversation History</span>
                <div class="detail-scrollable">${escapeHtml(JSON.stringify(details.conversation_history, null, 2))}</div>
            </div>
        `;
    }

    if (details.global_matches && details.global_matches.length > 0) {
        html += `
            <div class="detail-subsection">
                <span class="label">Global Matches</span>
                <div class="detail-scrollable">${escapeHtml(JSON.stringify(details.global_matches, null, 2))}</div>
            </div>
        `;
    }

    return html;
}

function buildResponseStepDetails(details) {
    const confPct = ((details.initial_confidence || 0) * 100).toFixed(0);
    const confColor = getConfidenceColor(details.initial_confidence || 0);

    let html = `
        <div class="detail-row">
            <span class="label">Model</span>
            <span class="value">${escapeHtml(details.model || 'unknown')}</span>
        </div>
        <div class="detail-row">
            <span class="label">Initial Confidence</span>
            <span class="value">
                ${confPct}%
                <span class="confidence-mini-bar">
                    <span class="confidence-mini-bar-fill" style="width:${confPct}%;background:${confColor}"></span>
                </span>
            </span>
        </div>
        <div class="detail-row">
            <span class="label">Skill Agent</span>
            <span class="value">${details.skill_agent_used ? 'Yes' : 'No'}</span>
        </div>
    `;

    if (details.reasoning) {
        html += `
            <div class="detail-subsection">
                <span class="label">Reasoning</span>
                <div class="detail-scrollable">${escapeHtml(details.reasoning)}</div>
            </div>
        `;
    }

    if (details.full_text) {
        html += `
            <div class="detail-subsection">
                <span class="label">Generated Text</span>
                <div class="detail-scrollable">${escapeHtml(details.full_text)}</div>
            </div>
        `;
    }

    return html;
}

function buildPostProcessingStepDetails(details) {
    if (!details.enabled) {
        return '<div class="detail-row"><span class="label">Status</span><span class="value">Disabled</span></div>';
    }

    const beforePct = ((details.confidence_before || 0) * 100).toFixed(0);
    const afterPct = ((details.confidence_after || 0) * 100).toFixed(0);
    const delta = details.confidence_delta || 0;
    const deltaStr = delta > 0 ? `+${(delta * 100).toFixed(1)}%` : `${(delta * 100).toFixed(1)}%`;
    const deltaColor = delta > 0 ? '#10b981' : delta < 0 ? '#ef4444' : '#8b90a0';
    const afterColor = getConfidenceColor(details.confidence_after || 0);

    let html = `
        <div class="detail-row">
            <span class="label">Model</span>
            <span class="value">${escapeHtml(details.model || 'unknown')}</span>
        </div>
        <div class="detail-row">
            <span class="label">Confidence</span>
            <span class="value">
                ${beforePct}% &rarr; ${afterPct}%
                <span style="color:${deltaColor};font-weight:600;margin-left:4px">(${deltaStr})</span>
                <span class="confidence-mini-bar">
                    <span class="confidence-mini-bar-fill" style="width:${afterPct}%;background:${afterColor}"></span>
                </span>
            </span>
        </div>
        <div class="detail-row">
            <span class="label">Text Changed</span>
            <span class="value">${details.text_changed ? 'Yes' : 'No'}</span>
        </div>
    `;

    if (details.reasoning) {
        html += `
            <div class="detail-subsection">
                <span class="label">Reasoning</span>
                <div class="detail-scrollable">${escapeHtml(details.reasoning)}</div>
            </div>
        `;
    }

    return html;
}

function buildRoutingStepDetails(details) {
    const isAutoSent = details.decision === 'auto_sent';
    const decisionColor = isAutoSent ? '#10b981' : '#f59e0b';
    const decisionLabel = isAutoSent ? 'AUTO-SENT' : 'PENDING REVIEW';
    const confPct = ((details.final_confidence || 0) * 100).toFixed(0);
    const threshPct = ((details.threshold || 0) * 100).toFixed(0);

    return `
        <div class="detail-row">
            <span class="label">Decision</span>
            <span class="value" style="color:${decisionColor};font-weight:700">${decisionLabel}</span>
        </div>
        <div class="detail-row">
            <span class="label">Final Confidence</span>
            <span class="value">${confPct}%</span>
        </div>
        <div class="detail-row">
            <span class="label">Threshold</span>
            <span class="value">${threshPct}%</span>
        </div>
        <div class="detail-row">
            <span class="label">Reason</span>
            <span class="value">${escapeHtml(details.reason || '')}</span>
        </div>
    `;
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

// Close modal on backdrop click
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

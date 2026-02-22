// State
let ws = null;
let sessionId = null;
let editingMessageIndex = null;

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

    // Clear chat
    chatMessages.innerHTML = "";

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
            });
            break;

        case "review_request":
            appendAssistantMessage(msg.content, {
                confidence: msg.confidence,
                reasoning: msg.reasoning,
                status: "pending",
                messageIndex: msg.message_index,
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
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper assistant";
    if (opts.messageIndex !== undefined) {
        wrapper.dataset.messageIndex = opts.messageIndex;
    }

    const bubble = document.createElement("div");
    bubble.className = `message assistant ${opts.status === "pending" ? "pending" : ""}`;
    bubble.textContent = content;

    // Click to show details
    bubble.addEventListener("click", () => {
        showDetails(content, opts.confidence, opts.reasoning);
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

    // Auto-show details for latest message
    showDetails(content, opts.confidence, opts.reasoning);
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

// ─── Detail panel ───

function showDetails(content, confidence, reasoning) {
    let html = "";

    if (confidence !== undefined) {
        const pct = (confidence * 100).toFixed(1);
        const cls = getConfidenceClass(confidence);
        const color =
            cls === "confidence-high"
                ? "#22c55e"
                : cls === "confidence-mid"
                  ? "#f59e0b"
                  : "#ef4444";

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

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

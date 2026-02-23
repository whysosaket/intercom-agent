// ─── Eval Mode State ───
let conversations = [];
let selectedConvId = null;
let selectedConv = null;
let candidatesMap = new Map();   // conv_id -> candidates array
let sentConversations = new Set();
let generatingSet = new Set();   // conv_ids currently generating

// Editing state
let editingConvId = null;
let editingText = "";

// DOM elements
const fetchBtn = document.getElementById("fetch-btn");
const generateAllBtn = document.getElementById("generate-all-btn");
const statusInfo = document.getElementById("status-info");
const convList = document.getElementById("conv-list");
const convCount = document.getElementById("conv-count");
const messagePanelTitle = document.getElementById("message-panel-title");
const messageHistory = document.getElementById("message-history");
const generateBtn = document.getElementById("generate-btn");
const candidatesContent = document.getElementById("candidates-content");
const editModal = document.getElementById("edit-modal");
const editTextarea = document.getElementById("edit-textarea");
const editSaveBtn = document.getElementById("edit-save");
const editCancelBtn = document.getElementById("edit-cancel");

// ─── Fetch Conversations ───

fetchBtn.addEventListener("click", fetchConversations);

async function fetchConversations() {
    fetchBtn.disabled = true;
    generateAllBtn.disabled = true;
    statusInfo.textContent = "Fetching...";
    convList.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Fetching unanswered conversations from Intercom...</p></div>';

    try {
        const res = await fetch("/eval/conversations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();
        conversations = data.conversations || [];

        if (data.message && conversations.length === 0) {
            statusInfo.textContent = data.message;
        } else {
            statusInfo.textContent = `${conversations.length} conversations`;
        }

        convCount.textContent = conversations.length > 0 ? `${conversations.length}` : "";
        generateAllBtn.disabled = conversations.length === 0;
        renderConversationList();

    } catch (err) {
        statusInfo.textContent = "Fetch failed";
        convList.innerHTML = `<div class="empty-state"><p>Failed to fetch conversations.</p><p class="hint">${escapeHtml(err.message)}</p></div>`;
    } finally {
        fetchBtn.disabled = false;
    }
}

// ─── Conversation List ───

function renderConversationList() {
    if (conversations.length === 0) {
        convList.innerHTML = '<div class="empty-state"><p>No unanswered conversations found.</p><p class="hint">All recent conversations have admin replies, or Intercom API is unavailable.</p></div>';
        return;
    }

    convList.innerHTML = "";
    for (const conv of conversations) {
        const item = document.createElement("div");
        item.className = "conv-item";
        item.id = `conv-item-${conv.conversation_id}`;
        if (conv.conversation_id === selectedConvId) {
            item.classList.add("selected");
        }
        if (sentConversations.has(conv.conversation_id)) {
            item.classList.add("sent");
        }
        if (generatingSet.has(conv.conversation_id)) {
            item.classList.add("generating");
        }
        if (candidatesMap.has(conv.conversation_id)) {
            item.classList.add("generated");
        }
        item.dataset.convId = conv.conversation_id;

        const name = conv.contact?.name || conv.contact?.email || "Unknown";
        const firstMsg = conv.messages?.[0]?.content || "";
        const preview = firstMsg.length > 80 ? firstMsg.slice(0, 80) + "..." : firstMsg;
        const msgCount = conv.messages?.length || 0;

        let badgeHtml = "";
        if (sentConversations.has(conv.conversation_id)) {
            badgeHtml = '<span class="conv-item-sent-badge">Sent</span>';
        } else if (generatingSet.has(conv.conversation_id)) {
            badgeHtml = '<span class="conv-item-gen-badge">Generating...</span>';
        } else if (candidatesMap.has(conv.conversation_id)) {
            const cands = candidatesMap.get(conv.conversation_id);
            const topConf = cands.length > 0 ? Math.max(...cands.map(c => c.confidence || 0)) : 0;
            badgeHtml = `<span class="conv-item-ready-badge">${(topConf * 100).toFixed(0)}%</span>`;
        }

        item.innerHTML = `
            <div class="conv-item-header">
                <span class="conv-item-name">${escapeHtml(name)}</span>
                <span class="conv-item-count">${msgCount} msg${msgCount !== 1 ? "s" : ""}</span>
            </div>
            <div class="conv-item-preview">${escapeHtml(preview)}</div>
            ${badgeHtml}
        `;

        item.addEventListener("click", () => selectConversation(conv.conversation_id));
        convList.appendChild(item);
    }
}

// ─── Select Conversation ───

function selectConversation(convId) {
    selectedConvId = convId;
    selectedConv = conversations.find(c => c.conversation_id === convId);

    // Update list selection
    convList.querySelectorAll(".conv-item").forEach(el => {
        el.classList.toggle("selected", el.dataset.convId === convId);
    });

    // Enable generate button
    generateBtn.disabled = false;

    // Render message history
    renderMessageHistory();

    // Show existing candidates if already generated
    if (candidatesMap.has(convId)) {
        renderCandidates(convId);
    } else {
        candidatesContent.innerHTML = '<div class="empty-state"><p>Click "Generate Responses" to create candidates.</p></div>';
    }
}

// ─── Message History ───

function renderMessageHistory() {
    if (!selectedConv) {
        messageHistory.innerHTML = '<div class="empty-state"><p>Select a conversation.</p></div>';
        return;
    }

    const name = selectedConv.contact?.name || selectedConv.contact?.email || "Unknown";
    messagePanelTitle.textContent = `${name} — ${selectedConv.conversation_id.slice(0, 12)}...`;

    messageHistory.innerHTML = "";
    for (const msg of selectedConv.messages) {
        const wrapper = document.createElement("div");
        wrapper.className = `message-wrapper ${msg.role === "user" ? "user" : "assistant"}`;

        const bubble = document.createElement("div");
        bubble.className = `message ${msg.role === "user" ? "user" : "assistant"}`;
        bubble.textContent = msg.content;

        const roleLabel = document.createElement("span");
        roleLabel.className = "eval-role-label";
        roleLabel.textContent = msg.role === "user" ? "Customer" : "Admin";

        wrapper.appendChild(roleLabel);
        wrapper.appendChild(bubble);
        messageHistory.appendChild(wrapper);
    }

    messageHistory.scrollTop = messageHistory.scrollHeight;
}

// ─── Generate Candidates (single) ───

generateBtn.addEventListener("click", generateResponses);

async function generateResponses() {
    if (!selectedConv || !selectedConvId) return;

    generateBtn.disabled = true;
    generateBtn.textContent = "Generating...";

    const userMessages = selectedConv.messages.filter(m => m.role === "user");
    const customerMessage = userMessages.length > 0 ? userMessages[userMessages.length - 1].content : "";

    if (!customerMessage) {
        candidatesContent.innerHTML = '<div class="empty-state"><p>No customer message found in this conversation.</p></div>';
        generateBtn.disabled = false;
        generateBtn.textContent = "Generate Responses";
        return;
    }

    candidatesContent.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Running pipeline to generate candidate responses...</p></div>';

    try {
        const res = await fetch("/eval/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                conversation_id: selectedConvId,
                customer_message: customerMessage,
                num_candidates: 2,
            }),
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();
        candidatesMap.set(selectedConvId, data.candidates || []);
        renderCandidates(selectedConvId);
        renderConversationList();
        renderReport();

    } catch (err) {
        candidatesContent.innerHTML = `<div class="empty-state"><p>Failed to generate responses.</p><p class="hint">${escapeHtml(err.message)}</p></div>`;
    } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = "Generate Responses";
    }
}

// ─── Generate All ───

generateAllBtn.addEventListener("click", generateAll);

async function generateAll() {
    // Only generate for conversations that don't already have candidates and aren't sent
    const toGenerate = conversations.filter(c =>
        !candidatesMap.has(c.conversation_id) &&
        !sentConversations.has(c.conversation_id)
    );

    if (toGenerate.length === 0) {
        statusInfo.textContent = "All conversations already have generated responses.";
        return;
    }

    generateAllBtn.disabled = true;
    fetchBtn.disabled = true;
    generateBtn.disabled = true;

    let completed = 0;
    const total = toGenerate.length;
    statusInfo.textContent = `Generating 0/${total}...`;

    // Mark all as generating
    for (const conv of toGenerate) {
        generatingSet.add(conv.conversation_id);
    }
    renderConversationList();

    // Build the request items
    const items = toGenerate.map(conv => {
        const userMessages = conv.messages.filter(m => m.role === "user");
        const customerMessage = userMessages.length > 0 ? userMessages[userMessages.length - 1].content : "";
        return {
            conversation_id: conv.conversation_id,
            customer_message: customerMessage,
        };
    }).filter(item => item.customer_message);

    try {
        const res = await fetch("/eval/generate-all-stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                conversations: items,
                num_candidates: 1,
            }),
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        // Read SSE stream — each result arrives as soon as it's ready
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE lines from the buffer
            const lines = buffer.split("\n");
            // Keep the last (possibly incomplete) line in the buffer
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const payload = line.slice(6);
                if (payload === "[DONE]") continue;

                try {
                    const result = JSON.parse(payload);
                    generatingSet.delete(result.conversation_id);
                    candidatesMap.set(result.conversation_id, result.candidates || []);
                    completed++;

                    statusInfo.textContent = `Generated ${completed}/${total}...`;
                    renderConversationList();
                    renderReport();

                    // If this conversation is currently selected, refresh its candidates panel
                    if (selectedConvId === result.conversation_id) {
                        renderCandidates(result.conversation_id);
                    }
                } catch (parseErr) {
                    // Skip unparseable lines
                }
            }
        }

        statusInfo.textContent = `Generated ${completed}/${total} responses`;
        renderReport();

    } catch (err) {
        statusInfo.textContent = `Generate all failed: ${err.message}`;
        // Clear generating state
        for (const conv of toGenerate) {
            generatingSet.delete(conv.conversation_id);
        }
    } finally {
        generateAllBtn.disabled = false;
        fetchBtn.disabled = false;
        if (selectedConvId) generateBtn.disabled = false;

        renderConversationList();

        // If a conversation is currently selected, refresh its candidates panel
        if (selectedConvId && candidatesMap.has(selectedConvId)) {
            renderCandidates(selectedConvId);
        }
    }
}

// ─── Report ───

const AUTOSEND_THRESHOLD = 0.8;
const evalReport = document.getElementById("eval-report");

function renderReport() {
    if (candidatesMap.size === 0) {
        evalReport.classList.add("hidden");
        return;
    }

    let autoSend = 0;
    let needsReview = 0;
    let escalated = 0;
    let greeting = 0;
    let clarify = 0;
    let errors = 0;
    let totalConf = 0;
    let confCount = 0;

    for (const [convId, candidates] of candidatesMap) {
        if (!candidates || candidates.length === 0) continue;
        const best = candidates[0];

        if (best.error) {
            errors++;
            continue;
        }

        const reasoning = best.reasoning || "";
        if (reasoning.startsWith("[Pre-Check Escalation]")) {
            escalated++;
        } else if (reasoning.startsWith("[Greeting]")) {
            greeting++;
            autoSend++;
        } else if (reasoning.startsWith("[Clarify Issue]")) {
            clarify++;
            autoSend++;
        } else if ((best.confidence || 0) >= AUTOSEND_THRESHOLD) {
            autoSend++;
        } else {
            needsReview++;
        }

        totalConf += best.confidence || 0;
        confCount++;
    }

    const total = candidatesMap.size;
    const pending = generatingSet.size;
    const avgConf = confCount > 0 ? (totalConf / confCount * 100).toFixed(0) : "—";

    evalReport.classList.remove("hidden");
    evalReport.innerHTML = `
        <div class="report-stats">
            <div class="report-stat report-stat-total">
                <span class="report-stat-value">${total}</span>
                <span class="report-stat-label">Generated</span>
            </div>
            <div class="report-stat report-stat-auto">
                <span class="report-stat-value">${autoSend}</span>
                <span class="report-stat-label">Auto-send</span>
            </div>
            <div class="report-stat report-stat-review">
                <span class="report-stat-value">${needsReview}</span>
                <span class="report-stat-label">Needs review</span>
            </div>
            <div class="report-stat report-stat-escalated">
                <span class="report-stat-value">${escalated}</span>
                <span class="report-stat-label">Escalated</span>
            </div>
            ${greeting > 0 ? `<div class="report-stat report-stat-greeting">
                <span class="report-stat-value">${greeting}</span>
                <span class="report-stat-label">Greeting</span>
            </div>` : ""}
            ${clarify > 0 ? `<div class="report-stat report-stat-clarify">
                <span class="report-stat-value">${clarify}</span>
                <span class="report-stat-label">Clarify</span>
            </div>` : ""}
            ${errors > 0 ? `<div class="report-stat report-stat-error">
                <span class="report-stat-value">${errors}</span>
                <span class="report-stat-label">Errors</span>
            </div>` : ""}
            <div class="report-stat report-stat-avg">
                <span class="report-stat-value">${avgConf}${avgConf !== "—" ? "%" : ""}</span>
                <span class="report-stat-label">Avg confidence</span>
            </div>
            ${pending > 0 ? `<div class="report-stat report-stat-pending">
                <span class="report-stat-value">${pending}</span>
                <span class="report-stat-label">Pending</span>
            </div>` : ""}
        </div>
    `;
}

// ─── Render Candidates ───

function renderCandidates(convId) {
    const candidates = candidatesMap.get(convId);
    if (!candidates || candidates.length === 0) {
        candidatesContent.innerHTML = '<div class="empty-state"><p>No candidates generated.</p></div>';
        return;
    }

    candidatesContent.innerHTML = "";

    for (const candidate of candidates) {
        const card = document.createElement("div");
        card.className = "candidate-card";
        if (candidate.error) card.classList.add("candidate-error");

        const isSent = sentConversations.has(convId);

        // Header with confidence
        const header = document.createElement("div");
        header.className = "candidate-header";
        const confPct = ((candidate.confidence || 0) * 100).toFixed(0);
        header.innerHTML = `
            <span class="candidate-label">Candidate ${candidate.index + 1}</span>
            <span class="confidence-badge ${getConfidenceClass(candidate.confidence || 0)}">
                ${confPct}%
            </span>
            <span class="candidate-duration">${candidate.total_duration_ms || 0}ms</span>
        `;
        card.appendChild(header);

        // Response text
        const textEl = document.createElement("div");
        textEl.className = "candidate-text";
        textEl.textContent = candidate.text || "(empty)";
        card.appendChild(textEl);

        // Reasoning
        if (candidate.reasoning) {
            const reasoning = document.createElement("div");
            reasoning.className = "candidate-reasoning";
            reasoning.innerHTML = `<span class="label">Reasoning:</span> ${escapeHtml(candidate.reasoning)}`;
            card.appendChild(reasoning);
        }

        // Action buttons
        if (!isSent && !candidate.error) {
            const actions = document.createElement("div");
            actions.className = "candidate-actions";

            const approveBtn = document.createElement("button");
            approveBtn.className = "btn btn-approve";
            approveBtn.innerHTML = "&#10003; Approve & Send";
            approveBtn.addEventListener("click", () => approveAndSend(convId, candidate.text));

            const editBtn = document.createElement("button");
            editBtn.className = "btn btn-edit";
            editBtn.textContent = "Edit & Send";
            editBtn.addEventListener("click", () => openEdit(convId, candidate.text));

            actions.appendChild(approveBtn);
            actions.appendChild(editBtn);
            card.appendChild(actions);
        }

        if (isSent) {
            const sentLabel = document.createElement("span");
            sentLabel.className = "status-label";
            sentLabel.textContent = "Response sent to this conversation";
            card.appendChild(sentLabel);
        }

        // Trace toggle
        if (candidate.pipeline_trace && candidate.pipeline_trace.length > 0) {
            const traceToggle = document.createElement("button");
            traceToggle.className = "btn btn-ghost trace-toggle";
            traceToggle.textContent = "Show Trace";
            traceToggle.addEventListener("click", () => {
                const traceContainer = card.querySelector(".candidate-trace");
                if (traceContainer.classList.contains("hidden")) {
                    traceContainer.classList.remove("hidden");
                    traceToggle.textContent = "Hide Trace";
                    renderPipelineTrace(candidate.pipeline_trace, candidate.total_duration_ms, traceContainer);
                } else {
                    traceContainer.classList.add("hidden");
                    traceToggle.textContent = "Show Trace";
                }
            });
            card.appendChild(traceToggle);

            const traceContainer = document.createElement("div");
            traceContainer.className = "candidate-trace hidden";
            card.appendChild(traceContainer);
        }

        candidatesContent.appendChild(card);
    }
}

// ─── Approve & Send ───

async function approveAndSend(convId, responseText) {
    if (sentConversations.has(convId)) return;

    const conv = conversations.find(c => c.conversation_id === convId);
    const userId = conv?.contact?.email || conv?.contact?.id || convId;

    // Get the last customer message for memory storage
    const userMessages = conv?.messages?.filter(m => m.role === "user") || [];
    const customerMessage = userMessages.length > 0 ? userMessages[userMessages.length - 1].content : "";

    try {
        const res = await fetch("/eval/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                conversation_id: convId,
                response_text: responseText,
                customer_message: customerMessage,
                user_id: userId,
            }),
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            const detail = errData.detail || `HTTP ${res.status}`;
            throw new Error(detail);
        }

        sentConversations.add(convId);
        statusInfo.textContent = `Sent to ${convId.slice(0, 8)}...`;

        // Re-render to reflect sent state
        renderConversationList();
        renderCandidates(convId);

    } catch (err) {
        statusInfo.textContent = `Send failed: ${err.message}`;
        alert(`Failed to send: ${err.message}`);
    }
}

// ─── Edit & Send ───

function openEdit(convId, currentText) {
    editingConvId = convId;
    editingText = currentText;
    editTextarea.value = currentText;
    editModal.classList.remove("hidden");
    editTextarea.focus();
}

editSaveBtn.addEventListener("click", async () => {
    const newText = editTextarea.value.trim();
    if (!newText || !editingConvId) return;

    editModal.classList.add("hidden");
    await approveAndSend(editingConvId, newText);
    editingConvId = null;
    editingText = "";
});

editCancelBtn.addEventListener("click", () => {
    editModal.classList.add("hidden");
    editingConvId = null;
    editingText = "";
});

document.querySelector(".modal-backdrop")?.addEventListener("click", () => {
    editModal.classList.add("hidden");
    editingConvId = null;
    editingText = "";
});

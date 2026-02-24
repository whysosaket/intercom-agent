const API_BASE = import.meta.env.VITE_API_BASE || ""

export const api = {
  async createSession(): Promise<{ session_id: string }> {
    const res = await fetch(`${API_BASE}/chat/sessions`, { method: "POST" })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async fetchConversations(limit: number): Promise<{ conversations: import("@/lib/types").EvalConversation[] }> {
    const res = await fetch(`${API_BASE}/eval/conversations?limit=${limit}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async generateCandidates(
    conversationId: string,
    customerMessage: string,
  ): Promise<{ conversation_id: string; candidates: import("@/lib/types").Candidate[] }> {
    const res = await fetch(`${API_BASE}/eval/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, customer_message: customerMessage }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async sendResponse(
    conversationId: string,
    responseText: string,
    customerMessage: string,
    userId: string,
  ): Promise<void> {
    const res = await fetch(`${API_BASE}/eval/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        response_text: responseText,
        customer_message: customerMessage,
        user_id: userId,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  },
}

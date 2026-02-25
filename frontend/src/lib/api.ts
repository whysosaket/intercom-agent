import type { EvalConversation, Candidate } from "./types"

const API_BASE = import.meta.env.VITE_API_BASE || ""

export const api = {
  async createSession(): Promise<{ session_id: string }> {
    const res = await fetch(`${API_BASE}/chat/sessions`, { method: "POST" })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async fetchConversations(limit: number): Promise<{ conversations: EvalConversation[] }> {
    const res = await fetch(`${API_BASE}/eval/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async generateCandidates(
    conversationId: string,
    customerMessage: string,
  ): Promise<{ conversation_id: string; candidates: Candidate[] }> {
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

  async translateText(
    text: string,
    targetLanguage: string = "English",
  ): Promise<{ translated_text: string; source_text: string; target_language: string }> {
    const res = await fetch(`${API_BASE}/eval/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, target_language: targetLanguage }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async refineResponse(
    conversationId: string,
    originalResponse: string,
    userInstructions: string,
    customerMessage: string,
    confidence: number,
  ): Promise<{ conversation_id: string; refined_text: string; confidence: number; reasoning: string }> {
    const res = await fetch(`${API_BASE}/eval/refine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        original_response: originalResponse,
        user_instructions: userInstructions,
        customer_message: customerMessage,
        confidence,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },
}

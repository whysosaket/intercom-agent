// ── Chat types ──

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  status: "sent" | "pending" | "approved" | "edited" | "rejected"
  confidence?: number
  reasoning?: string
  autoSent?: boolean
  pipelineTrace?: TraceEventData[]
  totalDurationMs?: number
  messageIndex?: number
}

export type ServerMessage =
  | {
      type: "ai_response"
      content: string
      confidence: number
      reasoning?: string
      auto_sent?: boolean
      pipeline_trace?: TraceEventData[]
      total_duration_ms?: number
    }
  | {
      type: "review_request"
      content: string
      confidence: number
      reasoning?: string
      message_index: number
      pipeline_trace?: TraceEventData[]
      total_duration_ms?: number
    }
  | { type: "response_approved"; message_index: number; content: string }
  | { type: "response_edited"; message_index: number; content: string }
  | { type: "response_rejected"; message_index: number }
  | { type: "error"; message: string }

export type ClientMessage =
  | { type: "user_message"; content: string }
  | { type: "approve"; message_index: number }
  | { type: "edit"; message_index: number; content: string }
  | { type: "reject"; message_index: number }

export type ConnectionState = "connecting" | "connected" | "disconnected" | "error"

// ── Eval types ──

export interface EvalConversation {
  conversation_id: string
  messages: Array<{ role: string; content: string }>
  has_admin_reply: boolean
  contact?: {
    id?: string
    name?: string
    email?: string
  }
}

export interface Candidate {
  text: string
  confidence: number
  reasoning?: string
  total_duration_ms?: number
  pipeline_trace?: TraceEventData[]
  error?: string
  refined?: boolean
}

export interface GenerateResult {
  conversation_id: string
  candidates: Candidate[]
}

// ── Trace types ──

export interface TraceEventData {
  call_type: string
  label: string
  status?: string
  duration_ms: number
  input_summary?: string
  output_summary?: string
  details?: Record<string, unknown>
  error_message?: string
}

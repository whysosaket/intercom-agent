export interface TraceEventData {
  call_type: string
  label: string
  duration_ms: number
  status?: string
  input_summary?: string
  output_summary?: string
  error_message?: string
  details?: Record<string, unknown>
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  confidence?: number
  reasoning?: string
  status: "sent" | "pending" | "approved" | "edited" | "rejected"
  autoSent?: boolean
  messageIndex?: number
  pipelineTrace?: TraceEventData[]
  totalDurationMs?: number
}

export type ConnectionState = "disconnected" | "connecting" | "connected" | "error"

export interface ClientMessage {
  type: "user_message" | "approve" | "edit" | "reject"
  content?: string
  message_index?: number
}

export type ServerMessage =
  | {
      type: "ai_response"
      content: string
      confidence: number
      reasoning?: string
      auto_sent: boolean
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
  | {
      type: "response_approved"
      message_index: number
      content: string
    }
  | {
      type: "response_edited"
      message_index: number
      content: string
    }
  | {
      type: "response_rejected"
      message_index: number
    }
  | {
      type: "error"
      message: string
    }

export interface EvalConversation {
  conversation_id: string
  has_admin_reply: boolean
  contact?: {
    id?: string
    name?: string
    email?: string
  }
  messages: Array<{
    role: "user" | "admin"
    content: string
  }>
}

export interface Candidate {
  text: string
  confidence: number
  reasoning?: string
  error?: string
  pipeline_trace?: TraceEventData[]
  total_duration_ms?: number
}

export interface GenerateResult {
  conversation_id: string
  candidates: Candidate[]
}

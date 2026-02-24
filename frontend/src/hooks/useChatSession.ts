import { useReducer, useCallback, useEffect } from "react"
import type { ChatMessage, ServerMessage } from "@/lib/types"
import { api } from "@/lib/api"
import { useWebSocket } from "./useWebSocket"

interface ChatState {
  sessionId: string | null
  messages: ChatMessage[]
  selectedTraceId: string | null
  isTyping: boolean
}

type ChatAction =
  | { type: "SESSION_CREATED"; sessionId: string }
  | { type: "ADD_USER_MESSAGE"; content: string }
  | { type: "SET_TYPING"; value: boolean }
  | { type: "AI_RESPONSE"; msg: Extract<ServerMessage, { type: "ai_response" }> }
  | { type: "REVIEW_REQUEST"; msg: Extract<ServerMessage, { type: "review_request" }> }
  | { type: "RESPONSE_APPROVED"; messageIndex: number; content: string }
  | { type: "RESPONSE_EDITED"; messageIndex: number; content: string }
  | { type: "RESPONSE_REJECTED"; messageIndex: number }
  | { type: "ERROR"; message: string }
  | { type: "SELECT_TRACE"; msgId: string }

let autoIdCounter = 0

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "SESSION_CREATED":
      autoIdCounter = 0
      return {
        ...state,
        sessionId: action.sessionId,
        messages: [],
        selectedTraceId: null,
        isTyping: false,
      }

    case "ADD_USER_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: `user_${Date.now()}`,
            role: "user",
            content: action.content,
            status: "sent",
          },
        ],
        isTyping: true,
      }

    case "SET_TYPING":
      return { ...state, isTyping: action.value }

    case "AI_RESPONSE": {
      const id = `auto_${autoIdCounter++}`
      return {
        ...state,
        isTyping: false,
        messages: [
          ...state.messages,
          {
            id,
            role: "assistant",
            content: action.msg.content,
            confidence: action.msg.confidence,
            reasoning: action.msg.reasoning,
            status: "sent",
            autoSent: action.msg.auto_sent,
            pipelineTrace: action.msg.pipeline_trace,
            totalDurationMs: action.msg.total_duration_ms,
          },
        ],
        selectedTraceId: id,
      }
    }

    case "REVIEW_REQUEST": {
      const id = String(action.msg.message_index)
      return {
        ...state,
        isTyping: false,
        messages: [
          ...state.messages,
          {
            id,
            role: "assistant",
            content: action.msg.content,
            confidence: action.msg.confidence,
            reasoning: action.msg.reasoning,
            status: "pending",
            messageIndex: action.msg.message_index,
            pipelineTrace: action.msg.pipeline_trace,
            totalDurationMs: action.msg.total_duration_ms,
          },
        ],
        selectedTraceId: id,
      }
    }

    case "RESPONSE_APPROVED":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.messageIndex === action.messageIndex
            ? { ...m, status: "approved" as const, content: action.content }
            : m,
        ),
      }

    case "RESPONSE_EDITED":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.messageIndex === action.messageIndex
            ? { ...m, status: "edited" as const, content: action.content }
            : m,
        ),
      }

    case "RESPONSE_REJECTED":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.messageIndex === action.messageIndex
            ? { ...m, status: "rejected" as const }
            : m,
        ),
      }

    case "ERROR":
      return {
        ...state,
        isTyping: false,
        messages: [
          ...state.messages,
          {
            id: `error_${Date.now()}`,
            role: "assistant",
            content: action.message,
            status: "sent",
          },
        ],
      }

    case "SELECT_TRACE":
      return { ...state, selectedTraceId: action.msgId }

    default:
      return state
  }
}

const initialState: ChatState = {
  sessionId: null,
  messages: [],
  selectedTraceId: null,
  isTyping: false,
}

export function useChatSession() {
  const [state, dispatch] = useReducer(chatReducer, initialState)
  const { sendMessage: wsSend, lastMessage, connectionState } = useWebSocket(state.sessionId)

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return

    switch (lastMessage.type) {
      case "ai_response":
        dispatch({ type: "AI_RESPONSE", msg: lastMessage })
        break
      case "review_request":
        dispatch({ type: "REVIEW_REQUEST", msg: lastMessage })
        break
      case "response_approved":
        dispatch({
          type: "RESPONSE_APPROVED",
          messageIndex: lastMessage.message_index,
          content: lastMessage.content,
        })
        break
      case "response_edited":
        dispatch({
          type: "RESPONSE_EDITED",
          messageIndex: lastMessage.message_index,
          content: lastMessage.content,
        })
        break
      case "response_rejected":
        dispatch({ type: "RESPONSE_REJECTED", messageIndex: lastMessage.message_index })
        break
      case "error":
        dispatch({ type: "ERROR", message: lastMessage.message })
        break
    }
  }, [lastMessage])

  const createSession = useCallback(async () => {
    const session = await api.createSession()
    dispatch({ type: "SESSION_CREATED", sessionId: session.session_id })
  }, [])

  const sendUserMessage = useCallback(
    (content: string) => {
      dispatch({ type: "ADD_USER_MESSAGE", content })
      wsSend({ type: "user_message", content })
    },
    [wsSend],
  )

  const approveResponse = useCallback(
    (messageIndex: number) => {
      wsSend({ type: "approve", message_index: messageIndex })
    },
    [wsSend],
  )

  const editResponse = useCallback(
    (messageIndex: number, content: string) => {
      wsSend({ type: "edit", message_index: messageIndex, content })
    },
    [wsSend],
  )

  const rejectResponse = useCallback(
    (messageIndex: number) => {
      wsSend({ type: "reject", message_index: messageIndex })
    },
    [wsSend],
  )

  const selectTrace = useCallback((msgId: string) => {
    dispatch({ type: "SELECT_TRACE", msgId })
  }, [])

  return {
    ...state,
    connectionState,
    createSession,
    sendUserMessage,
    approveResponse,
    editResponse,
    rejectResponse,
    selectTrace,
  }
}

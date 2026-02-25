import { useReducer, useCallback, useMemo } from "react"
import type { EvalConversation, Candidate, GenerateResult } from "@/lib/types"
import { api } from "@/lib/api"
import { useSSE } from "./useSSE"

interface EvalState {
  conversations: EvalConversation[]
  selectedConvId: string | null
  candidatesMap: Map<string, Candidate[]>
  sentConversations: Set<string>
  generatingSet: Set<string>
  generateMode: "unanswered" | "all"
  fetchStatus: "idle" | "loading" | "done" | "error"
  batchStatus: { completed: number; total: number } | null
}

type EvalAction =
  | { type: "FETCH_START" }
  | { type: "FETCH_SUCCESS"; conversations: EvalConversation[] }
  | { type: "FETCH_ERROR" }
  | { type: "SELECT_CONVERSATION"; id: string }
  | { type: "SET_GENERATE_MODE"; mode: "unanswered" | "all" }
  | { type: "GENERATE_START"; conversationIds: string[] }
  | { type: "GENERATE_RESULT"; result: GenerateResult }
  | { type: "GENERATE_DONE" }
  | { type: "MARK_SENT"; conversationId: string }
  | { type: "SET_CANDIDATES"; conversationId: string; candidates: Candidate[] }

function evalReducer(state: EvalState, action: EvalAction): EvalState {
  switch (action.type) {
    case "FETCH_START":
      return { ...state, fetchStatus: "loading" }

    case "FETCH_SUCCESS":
      return {
        ...state,
        fetchStatus: "done",
        conversations: action.conversations,
        candidatesMap: new Map(),
        sentConversations: new Set(),
        generatingSet: new Set(),
        selectedConvId: null,
        batchStatus: null,
      }

    case "FETCH_ERROR":
      return { ...state, fetchStatus: "error" }

    case "SELECT_CONVERSATION":
      return { ...state, selectedConvId: action.id }

    case "SET_GENERATE_MODE":
      return { ...state, generateMode: action.mode }

    case "GENERATE_START": {
      const generating = new Set(action.conversationIds)
      return {
        ...state,
        generatingSet: generating,
        batchStatus: { completed: 0, total: action.conversationIds.length },
      }
    }

    case "GENERATE_RESULT": {
      const newMap = new Map(state.candidatesMap)
      newMap.set(action.result.conversation_id, action.result.candidates)
      const newGenerating = new Set(state.generatingSet)
      newGenerating.delete(action.result.conversation_id)
      const completed = (state.batchStatus?.completed ?? 0) + 1
      return {
        ...state,
        candidatesMap: newMap,
        generatingSet: newGenerating,
        batchStatus: state.batchStatus
          ? { ...state.batchStatus, completed }
          : null,
      }
    }

    case "GENERATE_DONE":
      return { ...state, generatingSet: new Set(), batchStatus: null }

    case "MARK_SENT": {
      const newSent = new Set(state.sentConversations)
      newSent.add(action.conversationId)
      return { ...state, sentConversations: newSent }
    }

    case "SET_CANDIDATES": {
      const newMap = new Map(state.candidatesMap)
      newMap.set(action.conversationId, action.candidates)
      return { ...state, candidatesMap: newMap }
    }

    default:
      return state
  }
}

const initialState: EvalState = {
  conversations: [],
  selectedConvId: null,
  candidatesMap: new Map(),
  sentConversations: new Set(),
  generatingSet: new Set(),
  generateMode: "unanswered",
  fetchStatus: "idle",
  batchStatus: null,
}

export function useEvalState() {
  const [state, dispatch] = useReducer(evalReducer, initialState)
  const { startStream, cancel: cancelStream } = useSSE()

  const fetchConversations = useCallback(async (limit: number) => {
    dispatch({ type: "FETCH_START" })
    try {
      const data = await api.fetchConversations(limit)
      dispatch({ type: "FETCH_SUCCESS", conversations: data.conversations })
    } catch {
      dispatch({ type: "FETCH_ERROR" })
    }
  }, [])

  const selectConversation = useCallback((id: string) => {
    dispatch({ type: "SELECT_CONVERSATION", id })
  }, [])

  const setGenerateMode = useCallback((mode: "unanswered" | "all") => {
    dispatch({ type: "SET_GENERATE_MODE", mode })
  }, [])

  const generateSingle = useCallback(
    async (conversationId: string, customerMessage: string) => {
      dispatch({ type: "GENERATE_START", conversationIds: [conversationId] })
      try {
        const result = await api.generateCandidates(conversationId, customerMessage)
        dispatch({
          type: "GENERATE_RESULT",
          result: { conversation_id: result.conversation_id, candidates: result.candidates },
        })
        dispatch({ type: "GENERATE_DONE" })
      } catch {
        dispatch({ type: "GENERATE_DONE" })
      }
    },
    [],
  )

  const generateBatch = useCallback(
    (conversations: Array<{ conversation_id: string; customer_message: string }>) => {
      const ids = conversations.map((c) => c.conversation_id)
      dispatch({ type: "GENERATE_START", conversationIds: ids })

      startStream(conversations, 2, {
        onResult: (result) => dispatch({ type: "GENERATE_RESULT", result }),
        onDone: () => dispatch({ type: "GENERATE_DONE" }),
        onError: () => dispatch({ type: "GENERATE_DONE" }),
      })
    },
    [startStream],
  )

  const sendApproved = useCallback(
    async (conversationId: string, responseText: string, customerMessage: string, userId: string) => {
      await api.sendResponse(conversationId, responseText, customerMessage, userId)
      dispatch({ type: "MARK_SENT", conversationId })
    },
    [],
  )

  const setCandidates = useCallback(
    (conversationId: string, candidates: Candidate[]) => {
      dispatch({ type: "SET_CANDIDATES", conversationId, candidates })
    },
    [],
  )

  const sendAllHighConfidence = useCallback(
    async () => {
      const eligible: Array<{
        convId: string
        text: string
        customerMessage: string
        userId: string
      }> = []

      state.candidatesMap.forEach((candidates, convId) => {
        if (state.sentConversations.has(convId)) return
        const best = candidates[0]
        if (!best || best.error || best.confidence < 0.8) return
        const conv = state.conversations.find((c) => c.conversation_id === convId)
        if (!conv) return
        const userId = conv.contact?.email || conv.contact?.id || convId
        const userMsgs = conv.messages.filter((m) => m.role === "user")
        const customerMessage = userMsgs.map((m) => m.content).join("\n")
        eligible.push({ convId, text: best.text, customerMessage, userId })
      })

      let sentCount = 0
      for (const item of eligible) {
        try {
          await api.sendResponse(item.convId, item.text, item.customerMessage, item.userId)
          dispatch({ type: "MARK_SENT", conversationId: item.convId })
          sentCount++
        } catch (err) {
          console.error(`Failed to send for ${item.convId}`, err)
        }
      }
      return sentCount
    },
    [state.candidatesMap, state.sentConversations, state.conversations],
  )

  // Derived report stats
  const reportStats = useMemo(() => {
    const candidates = state.candidatesMap
    if (candidates.size === 0) return null

    let autoSend = 0
    let needsReview = 0
    let escalated = 0
    let errors = 0
    let totalConf = 0
    let confCount = 0

    candidates.forEach((candidateList) => {
      if (candidateList.length === 0) return
      const best = candidateList[0]
      if (best.error) {
        errors++
        return
      }
      totalConf += best.confidence
      confCount++
      if (best.confidence >= 0.8) {
        autoSend++
      } else if (best.confidence >= 0.5) {
        needsReview++
      } else {
        escalated++
      }
    })

    return {
      total: candidates.size,
      autoSend,
      needsReview,
      escalated,
      errors,
      avgConf: confCount > 0 ? totalConf / confCount : 0,
      pending: state.generatingSet.size,
    }
  }, [state.candidatesMap, state.generatingSet])

  const selectedConversation = useMemo(
    () => state.conversations.find((c) => c.conversation_id === state.selectedConvId) ?? null,
    [state.conversations, state.selectedConvId],
  )

  const selectedCandidates = useMemo(
    () => (state.selectedConvId ? state.candidatesMap.get(state.selectedConvId) ?? [] : []),
    [state.selectedConvId, state.candidatesMap],
  )

  const highConfidenceCount = useMemo(() => {
    let count = 0
    state.candidatesMap.forEach((candidates, convId) => {
      if (state.sentConversations.has(convId)) return
      const best = candidates[0]
      if (best && !best.error && best.confidence >= 0.8) count++
    })
    return count
  }, [state.candidatesMap, state.sentConversations])

  return {
    ...state,
    selectedConversation,
    selectedCandidates,
    reportStats,
    highConfidenceCount,
    fetchConversations,
    selectConversation,
    setGenerateMode,
    generateSingle,
    generateBatch,
    sendApproved,
    setCandidates,
    sendAllHighConfidence,
    cancelStream,
  }
}

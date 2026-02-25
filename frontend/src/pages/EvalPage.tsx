import { useState, useCallback, useMemo } from "react"
import { AppHeader } from "@/components/layout/AppHeader"
import { ConversationList } from "@/components/eval/ConversationList"
import { MessageHistory } from "@/components/eval/MessageHistory"
import { CandidatesPanel } from "@/components/eval/CandidatesPanel"
import { EvalReport } from "@/components/eval/EvalReport"
import { EvalActionsDropdown } from "@/components/eval/eval-actions-dropdown"
import { EditModal } from "@/components/shared/EditModal"
import { Button } from "@/components/ui/button"
import { useEvalState } from "@/hooks/useEvalState"
import { api } from "@/lib/api"

export function EvalPage() {
  const {
    conversations,
    selectedConvId,
    candidatesMap,
    sentConversations,
    generatingSet,
    generateMode,
    fetchStatus,
    batchStatus,
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
  } = useEvalState()

  const [fetchLimit, setFetchLimit] = useState(20)
  const [editState, setEditState] = useState<{ convId: string; text: string } | null>(null)

  const statusBadge = useMemo(() => {
    if (fetchStatus === "loading") return "Fetching..."
    if (batchStatus) return `Generated ${batchStatus.completed}/${batchStatus.total}...`
    if (fetchStatus === "done" && conversations.length > 0) {
      const answered = conversations.filter((c) => c.has_admin_reply).length
      const unanswered = conversations.length - answered
      return `${conversations.length} conversations (${unanswered} unanswered, ${answered} answered)`
    }
    return undefined
  }, [fetchStatus, batchStatus, conversations])

  const handleGenerate = useCallback(() => {
    if (!selectedConversation || !selectedConvId) return
    if (selectedConversation.has_admin_reply) return

    const userMessages = selectedConversation.messages.filter((m) => m.role === "user")
    const customerMessage = userMessages.map((m) => m.content).join("\n")
    if (!customerMessage) return

    generateSingle(selectedConvId, customerMessage)
  }, [selectedConversation, selectedConvId, generateSingle])

  const handleBatchGenerate = useCallback(() => {
    const skipAnswered = generateMode === "unanswered"
    const toGenerate = conversations.filter((c) => {
      if (candidatesMap.has(c.conversation_id)) return false
      if (sentConversations.has(c.conversation_id)) return false
      if (skipAnswered && c.has_admin_reply) return false
      return true
    })

    if (toGenerate.length === 0) return

    const items = toGenerate
      .map((conv) => {
        const userMessages = conv.messages.filter((m) => m.role === "user")
        const customerMessage = userMessages.map((m) => m.content).join("\n")
        return { conversation_id: conv.conversation_id, customer_message: customerMessage }
      })
      .filter((item) => item.customer_message)

    generateBatch(items)
  }, [conversations, candidatesMap, sentConversations, generateMode, generateBatch])

  const handleApprove = useCallback(
    async (text: string) => {
      if (!selectedConvId || !selectedConversation) return
      const userId = selectedConversation.contact?.email || selectedConversation.contact?.id || selectedConvId
      const userMessages = selectedConversation.messages.filter((m) => m.role === "user")
      const customerMessage = userMessages.map((m) => m.content).join("\n")
      await sendApproved(selectedConvId, text, customerMessage, userId)
    },
    [selectedConvId, selectedConversation, sendApproved],
  )

  const handleManualSend = useCallback(
    async (text: string) => {
      if (!selectedConvId || !selectedConversation) return
      const userId = selectedConversation.contact?.email || selectedConversation.contact?.id || selectedConvId
      const userMessages = selectedConversation.messages.filter((m) => m.role === "user")
      const customerMessage = userMessages.map((m) => m.content).join("\n")
      await sendApproved(selectedConvId, text, customerMessage, userId)
    },
    [selectedConvId, selectedConversation, sendApproved],
  )

  const handleEditSave = useCallback(
    async (text: string) => {
      if (!editState) return
      const conv = conversations.find((c) => c.conversation_id === editState.convId)
      if (!conv) return
      const userId = conv.contact?.email || conv.contact?.id || editState.convId
      const userMessages = conv.messages.filter((m) => m.role === "user")
      const customerMessage = userMessages.map((m) => m.content).join("\n")
      await sendApproved(editState.convId, text, customerMessage, userId)
      setEditState(null)
    },
    [editState, conversations, sendApproved],
  )

  const isBatchRunning = generatingSet.size > 0
  const isSent = selectedConvId ? sentConversations.has(selectedConvId) : false
  const [replyAllSending, setReplyAllSending] = useState(false)
  const [refiningIndex, setRefiningIndex] = useState<number | null>(null)

  const handleRefine = useCallback(
    async (candidateIndex: number, instructions: string) => {
      if (!selectedConvId || !selectedConversation || !selectedCandidates[candidateIndex]) return

      const candidate = selectedCandidates[candidateIndex]
      const userMessages = selectedConversation.messages.filter((m) => m.role === "user")
      const customerMessage = userMessages.map((m) => m.content).join("\n")

      setRefiningIndex(candidateIndex)
      try {
        const result = await api.refineResponse(
          selectedConvId,
          candidate.text,
          instructions,
          customerMessage,
          candidate.confidence,
        )

        const updatedCandidates = [...selectedCandidates]
        updatedCandidates[candidateIndex] = {
          ...candidate,
          text: result.refined_text,
          confidence: result.confidence,
          reasoning: result.reasoning,
          refined: true,
        }
        setCandidates(selectedConvId, updatedCandidates)
      } catch (err) {
        console.error("Refinement failed", err)
      } finally {
        setRefiningIndex(null)
      }
    },
    [selectedConvId, selectedConversation, selectedCandidates, setCandidates],
  )

  const handleReplyAll = useCallback(async () => {
    if (highConfidenceCount === 0) return
    const confirmed = window.confirm(
      `Send auto-replies for ${highConfidenceCount} conversation(s) with confidence ≥ 80%?`
    )
    if (!confirmed) return
    setReplyAllSending(true)
    try {
      await sendAllHighConfidence()
    } finally {
      setReplyAllSending(false)
    }
  }, [highConfidenceCount, sendAllHighConfidence])

  return (
    <>
      <AppHeader
        statusBadge={statusBadge}
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              className="h-8 rounded-lg bg-success text-white hover:bg-success/90 px-3 text-xs"
              disabled={highConfidenceCount === 0 || isBatchRunning || replyAllSending}
              onClick={handleReplyAll}
            >
              {replyAllSending ? "Sending..." : `Reply All (${highConfidenceCount})`}
            </Button>
            <EvalActionsDropdown
              fetchLimit={fetchLimit}
              onFetchLimitChange={setFetchLimit}
              onFetch={() => fetchConversations(fetchLimit)}
              generateMode={generateMode}
              onGenerateModeChange={setGenerateMode}
              onGenerate={handleBatchGenerate}
              fetchDisabled={fetchStatus === "loading" || isBatchRunning}
              generateDisabled={conversations.length === 0 || isBatchRunning}
            />
          </div>
        }
      />
      <EvalReport stats={reportStats} />
      <div className="grid grid-cols-[440px_1fr_520px] flex-1 min-h-0 2xl:grid-cols-[440px_1fr_520px] xl:grid-cols-[380px_1fr_480px] lg:grid-cols-[340px_1fr_400px]">
        <ConversationList
          conversations={conversations}
          selectedId={selectedConvId}
          candidatesMap={candidatesMap}
          sentSet={sentConversations}
          generatingSet={generatingSet}
          fetchStatus={fetchStatus}
          onSelect={selectConversation}
        />
        <MessageHistory
          conversation={selectedConversation}
          isGenerating={selectedConvId ? generatingSet.has(selectedConvId) : false}
          isSent={isSent}
          onGenerate={handleGenerate}
          onManualSend={handleManualSend}
        />
        <CandidatesPanel
          candidates={selectedCandidates}
          isSent={isSent}
          onApprove={handleApprove}
          onEdit={(text) => {
            if (selectedConvId) setEditState({ convId: selectedConvId, text })
          }}
          onRefine={handleRefine}
          refiningIndex={refiningIndex}
        />
      </div>
      <EditModal
        open={editState !== null}
        initialText={editState?.text ?? ""}
        onSave={handleEditSave}
        onCancel={() => setEditState(null)}
      />
    </>
  )
}

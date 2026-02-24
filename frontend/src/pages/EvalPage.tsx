import { useState, useCallback, useMemo } from "react"
import { AppHeader } from "@/components/layout/AppHeader"
import { ConversationList } from "@/components/eval/ConversationList"
import { MessageHistory } from "@/components/eval/MessageHistory"
import { CandidatesPanel } from "@/components/eval/CandidatesPanel"
import { EvalReport } from "@/components/eval/EvalReport"
import { EvalActionsDropdown } from "@/components/eval/eval-actions-dropdown"
import { EditModal } from "@/components/shared/EditModal"
import { useEvalState } from "@/hooks/useEvalState"

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
    fetchConversations,
    selectConversation,
    setGenerateMode,
    generateSingle,
    generateBatch,
    sendApproved,
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

  return (
    <>
      <AppHeader
        statusBadge={statusBadge}
        actions={
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
          onGenerate={handleGenerate}
        />
        <CandidatesPanel
          candidates={selectedCandidates}
          isSent={isSent}
          onApprove={handleApprove}
          onEdit={(text) => {
            if (selectedConvId) setEditState({ convId: selectedConvId, text })
          }}
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

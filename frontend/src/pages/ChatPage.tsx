import { useState, useMemo } from "react"
import { AppHeader } from "@/components/layout/AppHeader"
import { ChatMessages } from "@/components/chat/ChatMessages"
import { ChatInput } from "@/components/chat/ChatInput"
import { PipelineTracePanel } from "@/components/chat/PipelineTracePanel"
import { EditModal } from "@/components/shared/EditModal"
import { Button } from "@/components/ui/button"
import { useChatSession } from "@/hooks/useChatSession"

export function ChatPage() {
  const {
    sessionId,
    messages,
    selectedTraceId,
    isTyping,
    connectionState,
    createSession,
    sendUserMessage,
    approveResponse,
    editResponse,
    rejectResponse,
    selectTrace,
  } = useChatSession()

  const [editState, setEditState] = useState<{ messageIndex: number; content: string } | null>(null)

  const selectedMessage = useMemo(
    () => messages.find((m) => m.id === selectedTraceId),
    [messages, selectedTraceId],
  )

  const statusBadge = sessionId
    ? connectionState === "connected"
      ? `Session: ${sessionId.slice(0, 8)}...`
      : connectionState === "connecting"
        ? "Connecting..."
        : "Disconnected"
    : undefined

  const isConnected = connectionState === "connected"

  return (
    <>
      <AppHeader
        statusBadge={statusBadge}
        actions={
          <Button size="sm" onClick={createSession}>
            New Session
          </Button>
        }
      />
      <div className="flex flex-1 overflow-hidden">
        <main className="flex-1 flex flex-col min-w-0">
          <ChatMessages
            messages={messages}
            isTyping={isTyping}
            selectedTraceId={selectedTraceId}
            onSelectTrace={selectTrace}
            onApprove={approveResponse}
            onEdit={(idx, content) => setEditState({ messageIndex: idx, content })}
            onReject={rejectResponse}
          />
          <ChatInput onSend={sendUserMessage} disabled={!isConnected} />
        </main>
        <PipelineTracePanel
          trace={selectedMessage?.pipelineTrace}
          totalMs={selectedMessage?.totalDurationMs}
          content={selectedMessage?.content}
          confidence={selectedMessage?.confidence}
        />
      </div>
      <EditModal
        open={editState !== null}
        initialText={editState?.content ?? ""}
        onSave={(text) => {
          if (editState) {
            editResponse(editState.messageIndex, text)
            setEditState(null)
          }
        }}
        onCancel={() => setEditState(null)}
      />
    </>
  )
}

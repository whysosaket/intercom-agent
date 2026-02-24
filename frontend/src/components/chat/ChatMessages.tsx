import { useEffect, useRef } from "react"
import type { ChatMessage } from "@/lib/types"
import { MessageBubble } from "./MessageBubble"
import { TypingIndicator } from "./TypingIndicator"
import { EmptyState } from "@/components/shared/EmptyState"

interface ChatMessagesProps {
  messages: ChatMessage[]
  isTyping: boolean
  selectedTraceId: string | null
  onSelectTrace: (msgId: string) => void
  onApprove: (messageIndex: number) => void
  onEdit: (messageIndex: number, content: string) => void
  onReject: (messageIndex: number) => void
}

export function ChatMessages({
  messages,
  isTyping,
  selectedTraceId,
  onSelectTrace,
  onApprove,
  onEdit,
  onReject,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  if (messages.length === 0 && !isTyping) {
    return (
      <div className="flex-1 overflow-y-auto">
        <EmptyState
          title="Start a new session to begin testing."
          hint='Click "New Session" above, then type a customer message below.'
        />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-5">
      {messages.map((msg, i) => (
        <div key={msg.id} style={{ animationDelay: `${i * 40}ms` }}>
          <MessageBubble
            message={msg}
            onSelectTrace={onSelectTrace}
            onApprove={onApprove}
            onEdit={onEdit}
            onReject={onReject}
            isSelected={msg.id === selectedTraceId}
          />
        </div>
      ))}
      {isTyping && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}

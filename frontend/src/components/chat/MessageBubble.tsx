import { cn } from "@/lib/utils"
import type { ChatMessage } from "@/lib/types"
import { ConfidenceBadge } from "@/components/shared/ConfidenceBadge"
import { ReviewActions } from "./ReviewActions"

interface MessageBubbleProps {
  message: ChatMessage
  onSelectTrace: (msgId: string) => void
  onApprove: (messageIndex: number) => void
  onEdit: (messageIndex: number, content: string) => void
  onReject: (messageIndex: number) => void
  isSelected: boolean
}

export function MessageBubble({
  message,
  onSelectTrace,
  onApprove,
  onEdit,
  onReject,
  isSelected,
}: MessageBubbleProps) {
  const isUser = message.role === "user"
  const isPending = message.status === "pending"
  const isRejected = message.status === "rejected"

  const statusLabel: Record<string, string> = {
    approved: "Approved & sent",
    edited: "Edited & sent",
    rejected: "Rejected",
  }

  return (
    <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[75%] px-4 py-3 text-sm whitespace-pre-wrap transition-shadow",
          isUser
            ? "bg-accent-600 text-white rounded-xl rounded-br-[6px] shadow-md"
            : cn(
                "bg-elevated border border-cream-200 rounded-xl rounded-bl-[6px] cursor-pointer hover:shadow-md",
                isPending && "border-l-[3px] border-l-accent-400",
                isRejected && "opacity-50 line-through",
                isSelected && "ring-2 ring-accent-400/30",
              ),
        )}
        onClick={() => {
          if (!isUser) onSelectTrace(message.id)
        }}
      >
        {message.content}
      </div>

      {!isUser && message.confidence !== undefined && (
        <ConfidenceBadge confidence={message.confidence} className="mt-1" />
      )}

      {isPending && message.messageIndex !== undefined && (
        <ReviewActions
          onApprove={() => onApprove(message.messageIndex!)}
          onEdit={() => onEdit(message.messageIndex!, message.content)}
          onReject={() => onReject(message.messageIndex!)}
        />
      )}

      {message.status === "sent" && message.autoSent && (
        <span className="text-[11px] text-cream-400 mt-1">Auto-sent (high confidence)</span>
      )}

      {statusLabel[message.status] && message.status !== "sent" && (
        <span className="text-[11px] text-cream-400 mt-1">{statusLabel[message.status]}</span>
      )}
    </div>
  )
}

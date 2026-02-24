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
    <div className={cn("flex flex-col animate-stagger-in", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[75%] px-4 py-3 text-sm whitespace-pre-wrap transition-all duration-300",
          isUser
            ? "bg-ice-600 text-white rounded-2xl rounded-br-lg shadow-[0_0_20px_rgba(59,115,245,0.15),inset_0_1px_0_rgba(255,255,255,0.1)]"
            : cn(
                "glass-elevated rounded-2xl rounded-bl-lg cursor-pointer hover:bg-[rgba(255,255,255,0.05)] hover:shadow-[0_0_24px_rgba(0,0,0,0.2)]",
                isPending && "border-l-2 border-l-ice-400/60 shadow-[0_0_16px_rgba(59,115,245,0.08)]",
                isRejected && "opacity-40 line-through",
                isSelected && "ring-1 ring-ice-400/25 shadow-[0_0_20px_rgba(59,115,245,0.1)]",
              ),
        )}
        onClick={() => {
          if (!isUser) onSelectTrace(message.id)
        }}
      >
        <span className={cn(!isUser && "text-graphite-200")}>{message.content}</span>
      </div>

      {!isUser && message.confidence !== undefined && (
        <ConfidenceBadge confidence={message.confidence} className="mt-1.5" />
      )}

      {isPending && message.messageIndex !== undefined && (
        <ReviewActions
          onApprove={() => onApprove(message.messageIndex!)}
          onEdit={() => onEdit(message.messageIndex!, message.content)}
          onReject={() => onReject(message.messageIndex!)}
        />
      )}

      {message.status === "sent" && message.autoSent && (
        <span className="text-[11px] text-graphite-500 mt-1">Auto-sent (high confidence)</span>
      )}

      {statusLabel[message.status] && message.status !== "sent" && (
        <span className="text-[11px] text-graphite-500 mt-1">{statusLabel[message.status]}</span>
      )}
    </div>
  )
}

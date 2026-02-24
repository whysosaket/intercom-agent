import { cn } from "@/lib/utils"
import type { EvalConversation, Candidate } from "@/lib/types"

interface ConversationItemProps {
  conversation: EvalConversation
  isSelected: boolean
  isSent: boolean
  isGenerating: boolean
  candidates: Candidate[] | undefined
  onClick: () => void
}

export function ConversationItem({
  conversation,
  isSelected,
  isSent,
  isGenerating,
  candidates,
  onClick,
}: ConversationItemProps) {
  const name = conversation.contact?.name || conversation.contact?.email || "Unknown"
  const firstMsg = conversation.messages?.[0]?.content || ""
  const preview = firstMsg.length > 80 ? firstMsg.slice(0, 80) + "..." : firstMsg
  const msgCount = conversation.messages?.length || 0

  let badge: { text: string; className: string } | null = null
  if (isSent) {
    badge = { text: "Sent", className: "bg-success/10 text-success border-success/15" }
  } else if (isGenerating) {
    badge = { text: "Generating...", className: "bg-ice-500/10 text-ice-400 border-ice-500/15" }
  } else if (candidates && candidates.length > 0) {
    const topConf = Math.max(...candidates.map((c) => c.confidence || 0))
    badge = {
      text: `${(topConf * 100).toFixed(0)}%`,
      className:
        topConf >= 0.8
          ? "bg-success/10 text-success border-success/15"
          : topConf >= 0.5
            ? "bg-warning/10 text-warning border-warning/15"
            : "bg-error/10 text-error border-error/15",
    }
  } else if (conversation.has_admin_reply) {
    badge = { text: "Answered", className: "bg-[rgba(255,255,255,0.04)] text-graphite-500 border-[rgba(255,255,255,0.06)]" }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left p-3.5 border-b border-[rgba(255,255,255,0.04)] transition-all duration-300 cursor-pointer",
        isSelected
          ? "bg-[rgba(59,115,245,0.06)] border-l-2 border-l-ice-500 shadow-[inset_0_0_20px_rgba(59,115,245,0.04)]"
          : "hover:bg-[rgba(255,255,255,0.02)]",
        isSent && "opacity-50",
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-graphite-200 truncate">{name}</span>
        <span className="text-[11px] text-graphite-600 flex-shrink-0">
          {msgCount} msg{msgCount !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="text-xs text-graphite-500 truncate">{preview}</div>
      {badge && (
        <span className={cn("inline-block mt-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border", badge.className)}>
          {badge.text}
        </span>
      )}
    </button>
  )
}

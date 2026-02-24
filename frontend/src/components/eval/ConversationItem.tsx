import { ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"
import type { EvalConversation, Candidate } from "@/lib/types"
import { getIntercomConversationUrl } from "@/lib/intercom"

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
  const intercomUrl = getIntercomConversationUrl(conversation.conversation_id)

  let badge: { text: string; className: string } | null = null
  if (isSent) {
    badge = { text: "Sent", className: "bg-success-bg text-success" }
  } else if (isGenerating) {
    badge = { text: "Generating...", className: "bg-accent-50 text-accent-600" }
  } else if (candidates && candidates.length > 0) {
    const topConf = Math.max(...candidates.map((c) => c.confidence || 0))
    badge = {
      text: `${(topConf * 100).toFixed(0)}%`,
      className:
        topConf >= 0.8
          ? "bg-success-bg text-success"
          : topConf >= 0.5
            ? "bg-warning-bg text-warning"
            : "bg-error-bg text-error",
    }
  } else if (conversation.has_admin_reply) {
    badge = { text: "Answered", className: "bg-cream-100 text-cream-500" }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left p-3 border-b border-cream-200 transition-colors cursor-pointer",
        isSelected ? "bg-accent-50 border-l-2 border-l-accent-500" : "hover:bg-cream-50",
        isSent && "opacity-60",
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-cream-800 truncate">{name}</span>
        <span className="text-[11px] text-cream-400 shrink-0">
          {msgCount} msg{msgCount !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="text-xs text-cream-500 truncate">{preview}</div>
      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        {badge && (
          <span className={cn("inline-block text-[10px] font-medium px-1.5 py-0.5 rounded-full", badge.className)}>
            {badge.text}
          </span>
        )}
        {intercomUrl && (
          <a
            href={intercomUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-[10px] text-accent-600 hover:text-accent-700 hover:underline"
            title="Open in Intercom"
          >
            <ExternalLink className="size-3" aria-hidden />
            <span>Open in Intercom</span>
          </a>
        )}
      </div>
    </button>
  )
}

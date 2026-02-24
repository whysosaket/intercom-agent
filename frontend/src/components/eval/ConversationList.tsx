import type { EvalConversation, Candidate } from "@/lib/types"
import { ConversationItem } from "./ConversationItem"
import { EmptyState } from "@/components/shared/EmptyState"
import { LoadingSpinner } from "@/components/shared/LoadingSpinner"

interface ConversationListProps {
  conversations: EvalConversation[]
  selectedId: string | null
  candidatesMap: Map<string, Candidate[]>
  sentSet: Set<string>
  generatingSet: Set<string>
  fetchStatus: "idle" | "loading" | "done" | "error"
  onSelect: (id: string) => void
}

export function ConversationList({
  conversations,
  selectedId,
  candidatesMap,
  sentSet,
  generatingSet,
  fetchStatus,
  onSelect,
}: ConversationListProps) {
  return (
    <aside className="flex flex-col border-r border-cream-200 bg-elevated overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-cream-200 flex-shrink-0">
        <h2 className="text-sm font-semibold text-cream-800">Conversations</h2>
        {conversations.length > 0 && (
          <span className="text-xs text-cream-400">{conversations.length}</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        {fetchStatus === "loading" && <LoadingSpinner />}
        {fetchStatus === "idle" && (
          <EmptyState title="No conversations loaded." hint='Click "Fetch Conversations" to load unanswered messages.' />
        )}
        {fetchStatus === "error" && (
          <EmptyState title="Failed to fetch conversations." />
        )}
        {fetchStatus === "done" && conversations.length === 0 && (
          <EmptyState title="No conversations found." hint="No recent conversations available." />
        )}
        {fetchStatus === "done" &&
          conversations.map((conv) => (
            <ConversationItem
              key={conv.conversation_id}
              conversation={conv}
              isSelected={conv.conversation_id === selectedId}
              isSent={sentSet.has(conv.conversation_id)}
              isGenerating={generatingSet.has(conv.conversation_id)}
              candidates={candidatesMap.get(conv.conversation_id)}
              onClick={() => onSelect(conv.conversation_id)}
            />
          ))}
      </div>
    </aside>
  )
}

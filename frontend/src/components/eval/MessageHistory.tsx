import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import type { EvalConversation } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/shared/EmptyState"

interface MessageHistoryProps {
  conversation: EvalConversation | null
  isGenerating: boolean
  onGenerate: () => void
}

export function MessageHistory({ conversation, isGenerating, onGenerate }: MessageHistoryProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [conversation])

  if (!conversation) {
    return (
      <main className="flex flex-col bg-surface overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-cream-200 flex-shrink-0">
          <h2 className="text-sm font-semibold text-cream-800">Messages</h2>
        </div>
        <EmptyState title="Select a conversation from the left panel." />
      </main>
    )
  }

  const name = conversation.contact?.name || conversation.contact?.email || "Unknown"
  const title = `${name} — ${conversation.conversation_id.slice(0, 12)}...`

  return (
    <main className="flex flex-col bg-surface overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-cream-200 flex-shrink-0">
        <h2 className="text-sm font-semibold text-cream-800">{title}</h2>
        <Button size="sm" onClick={onGenerate} disabled={isGenerating}>
          {isGenerating ? "Generating..." : "Generate Responses"}
        </Button>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
        {conversation.messages.map((msg, i) => {
          const isUser = msg.role === "user"
          return (
            <div key={i} className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
              <span className="text-[10px] text-cream-400 mb-0.5 uppercase tracking-wider">
                {isUser ? "Customer" : "Admin"}
              </span>
              <div
                className={cn(
                  "max-w-[80%] px-4 py-3 text-sm whitespace-pre-wrap",
                  isUser
                    ? "bg-accent-600 text-white rounded-xl rounded-br-[6px] shadow-md"
                    : "bg-elevated border border-cream-200 rounded-xl rounded-bl-[6px]",
                )}
              >
                {msg.content}
              </div>
            </div>
          )
        })}
      </div>
    </main>
  )
}

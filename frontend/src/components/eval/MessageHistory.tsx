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
      <main className="flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-[rgba(255,255,255,0.04)] flex-shrink-0">
          <h2 className="text-sm font-semibold text-graphite-100 tracking-tight">Messages</h2>
        </div>
        <EmptyState title="Select a conversation from the left panel." />
      </main>
    )
  }

  const name = conversation.contact?.name || conversation.contact?.email || "Unknown"
  const title = `${name} — ${conversation.conversation_id.slice(0, 12)}...`

  return (
    <main className="flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-[rgba(255,255,255,0.04)] flex-shrink-0">
        <h2 className="text-sm font-semibold text-graphite-100 tracking-tight">{title}</h2>
        <Button size="sm" onClick={onGenerate} disabled={isGenerating}>
          {isGenerating ? "Generating..." : "Generate Responses"}
        </Button>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
        {conversation.messages.map((msg, i) => {
          const isUser = msg.role === "user"
          return (
            <div key={i} className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
              <span className="text-[10px] text-graphite-600 mb-0.5 uppercase tracking-wider font-medium">
                {isUser ? "Customer" : "Admin"}
              </span>
              <div
                className={cn(
                  "max-w-[80%] px-4 py-3 text-sm whitespace-pre-wrap",
                  isUser
                    ? "bg-ice-600 text-white rounded-2xl rounded-br-lg shadow-[0_0_20px_rgba(59,115,245,0.15),inset_0_1px_0_rgba(255,255,255,0.1)]"
                    : "glass-elevated rounded-2xl rounded-bl-lg text-graphite-200",
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

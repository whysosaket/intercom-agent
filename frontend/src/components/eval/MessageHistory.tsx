import { useEffect, useRef, useState, useCallback } from "react"
import { ExternalLink, Send, Languages } from "lucide-react"
import { cn } from "@/lib/utils"
import type { EvalConversation } from "@/lib/types"
import { getIntercomConversationUrl } from "@/lib/intercom"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/shared/EmptyState"

interface MessageHistoryProps {
  conversation: EvalConversation | null
  isGenerating: boolean
  isSent?: boolean
  onGenerate: () => void
  onManualSend?: (text: string) => void
}

export function MessageHistory({ conversation, isGenerating, isSent, onGenerate, onManualSend }: MessageHistoryProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [manualInput, setManualInput] = useState("")
  const [translations, setTranslations] = useState<Map<string, string>>(new Map())
  const [translatingSet, setTranslatingSet] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [conversation])

  useEffect(() => {
    setManualInput("")
    setTranslations(new Map())
    setTranslatingSet(new Set())
  }, [conversation?.conversation_id])

  const handleTranslate = useCallback(
    async (msgIndex: number, text: string) => {
      if (!conversation) return
      const key = `${conversation.conversation_id}-${msgIndex}`
      if (translations.has(key)) return

      setTranslatingSet((prev) => new Set(prev).add(key))
      try {
        const result = await api.translateText(text)
        setTranslations((prev) => new Map(prev).set(key, result.translated_text))
      } catch (err) {
        console.error("Translation failed", err)
      } finally {
        setTranslatingSet((prev) => {
          const next = new Set(prev)
          next.delete(key)
          return next
        })
      }
    },
    [conversation, translations],
  )

  if (!conversation) {
    return (
      <main className="flex flex-col bg-surface overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-cream-200 shrink-0">
          <h2 className="text-sm font-semibold text-cream-800">Messages</h2>
        </div>
        <EmptyState title="Select a conversation from the left panel." />
      </main>
    )
  }

  const name = conversation.contact?.name || conversation.contact?.email || "Unknown"
  const title = `${name} — ${conversation.conversation_id.slice(0, 12)}...`
  const intercomUrl = getIntercomConversationUrl(conversation.conversation_id)

  return (
    <main className="flex flex-col bg-surface overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-cream-200 shrink-0 gap-2">
        <h2 className="text-sm font-semibold text-cream-800 truncate min-w-0">{title}</h2>
        <div className="flex items-center gap-2 shrink-0">
          {intercomUrl && (
            <a
              href={intercomUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-accent-600 hover:text-accent-700 hover:underline"
              title="Open in Intercom"
            >
              <ExternalLink className="size-3.5" aria-hidden />
              <span>Open in Intercom</span>
            </a>
          )}
          <Button size="sm" onClick={onGenerate} disabled={isGenerating}>
            {isGenerating ? "Generating..." : "Generate Responses"}
          </Button>
        </div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
        {conversation.messages.map((msg, i) => {
          const isUser = msg.role === "user"
          const translationKey = `${conversation.conversation_id}-${i}`
          const translatedText = translations.get(translationKey)
          const isTranslating = translatingSet.has(translationKey)
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
              {isUser && (
                <button
                  type="button"
                  className="text-[10px] text-cream-400 hover:text-accent-600 mt-1 flex items-center gap-1 transition-colors"
                  onClick={() => handleTranslate(i, msg.content)}
                  disabled={isTranslating || !!translatedText}
                >
                  <Languages className="size-3" />
                  {isTranslating ? "Translating..." : translatedText ? "Translated" : "Translate"}
                </button>
              )}
              {translatedText && (
                <div className="max-w-[80%] px-4 py-2 text-xs text-cream-600 bg-cream-50 rounded-lg mt-1 border border-cream-200">
                  <span className="text-[10px] text-cream-400 block mb-0.5">Translation (English)</span>
                  {translatedText}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Manual reply input */}
      {onManualSend && !isSent && (
        <div className="border-t border-cream-200 bg-elevated px-4 py-3 shrink-0">
          <div className="flex items-end gap-2">
            <textarea
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  const trimmed = manualInput.trim()
                  if (trimmed) {
                    onManualSend(trimmed)
                    setManualInput("")
                  }
                }
              }}
              placeholder="Type a reply..."
              rows={2}
              className="flex-1 resize-none rounded-lg border border-cream-200 bg-cream-50 px-3 py-2 text-sm text-cream-900 placeholder:text-cream-400 outline-none focus:ring-2 focus:ring-accent-300"
            />
            <Button
              size="sm"
              className="h-9 px-3 shrink-0"
              disabled={!manualInput.trim()}
              onClick={() => {
                const trimmed = manualInput.trim()
                if (trimmed) {
                  onManualSend(trimmed)
                  setManualInput("")
                }
              }}
            >
              <Send className="size-4" />
            </Button>
          </div>
        </div>
      )}
      {isSent && (
        <div className="border-t border-cream-200 bg-elevated px-4 py-3 shrink-0">
          <p className="text-xs text-cream-400 text-center">Response sent to this conversation</p>
        </div>
      )}
    </main>
  )
}

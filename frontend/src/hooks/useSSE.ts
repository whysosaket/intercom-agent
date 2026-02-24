import { useCallback, useRef } from "react"
import type { GenerateResult } from "@/lib/types"

const API_BASE = import.meta.env.VITE_API_BASE || ""

interface SSECallbacks {
  onResult: (result: GenerateResult) => void
  onDone: () => void
  onError: (error: Error) => void
}

export function useSSE() {
  const abortRef = useRef<AbortController | null>(null)

  const startStream = useCallback(
    async (
      conversations: Array<{ conversation_id: string; customer_message: string }>,
      numCandidates: number,
      callbacks: SSECallbacks,
    ) => {
      abortRef.current = new AbortController()

      let res: Response
      try {
        res = await fetch(`${API_BASE}/eval/generate-all-stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ conversations, num_candidates: numCandidates }),
          signal: abortRef.current.signal,
        })
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          callbacks.onError(err as Error)
        }
        return
      }

      if (!res.ok || !res.body) {
        callbacks.onError(new Error(`HTTP ${res.status}`))
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() || ""

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            const payload = line.slice(6)
            if (payload === "[DONE]") {
              callbacks.onDone()
              return
            }
            try {
              callbacks.onResult(JSON.parse(payload) as GenerateResult)
            } catch {
              // skip unparseable
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          callbacks.onError(err as Error)
        }
        return
      }

      callbacks.onDone()
    },
    [],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { startStream, cancel }
}

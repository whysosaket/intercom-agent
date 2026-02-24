import { useEffect, useRef, useState, useCallback } from "react"
import type { ClientMessage, ServerMessage, ConnectionState } from "@/lib/types"

const WS_BASE = import.meta.env.VITE_API_WS_BASE || ""

export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected")
  const [lastMessage, setLastMessage] = useState<ServerMessage | null>(null)

  useEffect(() => {
    if (!sessionId) return

    const protocol = location.protocol === "https:" ? "wss:" : "ws:"
    const host = WS_BASE || location.host
    const wsUrl = `${protocol}//${host}/chat/ws/${sessionId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    setConnectionState("connecting")

    ws.onopen = () => setConnectionState("connected")
    ws.onmessage = (e) => {
      try {
        setLastMessage(JSON.parse(e.data as string) as ServerMessage)
      } catch {
        // ignore unparseable messages
      }
    }
    ws.onclose = () => setConnectionState("disconnected")
    ws.onerror = () => setConnectionState("error")

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [sessionId])

  const sendMessage = useCallback((msg: ClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  return { sendMessage, lastMessage, connectionState }
}

export const CONFIDENCE_THRESHOLD = 0.8

export const CALL_TYPE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  mem0_search: { label: "Memory Search", color: "text-blue-600", icon: "search" },
  llm_call: { label: "LLM Call", color: "text-purple-600", icon: "brain" },
  http_fetch: { label: "HTTP Fetch", color: "text-green-600", icon: "globe" },
  computation: { label: "Computation", color: "text-amber-600", icon: "cpu" },
  agent_call: { label: "Agent Call", color: "text-rose-600", icon: "bot" },
}

import { useState } from "react"
import { cn } from "@/lib/utils"
import type { TraceEventData } from "@/lib/types"
import { escapeHtml } from "@/lib/utils"

const CALL_TYPE_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  mem0_search: { icon: "M", color: "#4f46e5", label: "Mem0" },
  llm_call: { icon: "AI", color: "#6366f1", label: "LLM" },
  http_fetch: { icon: "H", color: "#4b5563", label: "HTTP" },
  computation: { icon: "C", color: "#6b7280", label: "Compute" },
  agent_call: { icon: "A", color: "#4f46e5", label: "Agent" },
}

function getConfig(callType: string) {
  return CALL_TYPE_CONFIG[callType] || { icon: "?", color: "#6b7280", label: callType }
}

function formatDetailLabel(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

function getConfidenceColor(confidence: number) {
  if (confidence >= 0.8) return "#059669"
  if (confidence >= 0.5) return "#d97706"
  return "#dc2626"
}

interface TraceEventProps {
  event: TraceEventData
  isLast: boolean
}

export function TraceEvent({ event, isLast }: TraceEventProps) {
  const [expanded, setExpanded] = useState(false)
  const config = getConfig(event.call_type)
  const statusClass = event.status || "completed"
  const durationLabel = event.duration_ms > 0 ? `${event.duration_ms}ms` : ""
  const details = event.details || {}
  const hasDetails = Object.keys(details).length > 0 || event.error_message

  return (
    <div className="flex gap-3" data-status={statusClass}>
      {/* Connector: dot + line */}
      <div className="flex flex-col items-center w-8 flex-shrink-0">
        <div
          className={cn(
            "w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold border-2 flex-shrink-0",
            statusClass === "completed" ? "text-white" : "bg-white",
          )}
          style={{
            borderColor: config.color,
            backgroundColor: statusClass === "completed" ? config.color : undefined,
            color: statusClass !== "completed" ? config.color : undefined,
          }}
        >
          {config.icon}
        </div>
        {!isLast && <div className="w-px flex-1 bg-cream-200 min-h-[16px]" />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pb-4">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full text-left flex items-start justify-between gap-2 group cursor-pointer"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold"
                style={{
                  backgroundColor: `${config.color}12`,
                  color: config.color,
                }}
              >
                {config.label}
              </span>
              <span className="text-sm font-medium text-cream-800">{event.label}</span>
            </div>
            {(event.input_summary || event.output_summary) && (
              <div className="flex flex-col gap-0.5 mt-1">
                {event.input_summary && (
                  <span className="text-xs text-cream-500 truncate block">{event.input_summary}</span>
                )}
                {event.output_summary && (
                  <span className="text-xs text-cream-400 truncate block">{event.output_summary}</span>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
            {statusClass === "error" && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-error-bg text-error">ERROR</span>
            )}
            {statusClass === "skipped" && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-cream-100 text-cream-500">SKIPPED</span>
            )}
            {durationLabel && <span className="text-xs text-cream-400 font-mono">{durationLabel}</span>}
            <span
              className={cn(
                "text-[10px] text-cream-400 transition-transform",
                expanded && "rotate-90",
              )}
            >
              &#9654;
            </span>
          </div>
        </button>

        {/* Expanded details */}
        {expanded && hasDetails && (
          <div className="mt-2 pl-0 space-y-1.5">
            {Object.entries(details).map(([key, value]) => {
              if (value === null || value === undefined) return null
              const label = formatDetailLabel(key)

              if (typeof value === "number" && key.toLowerCase().includes("confidence")) {
                const pct = (value * 100).toFixed(0)
                const color = getConfidenceColor(value)
                return (
                  <div key={key} className="flex items-center gap-2 text-xs">
                    <span className="text-cream-500 font-medium">{label}</span>
                    <span className="text-cream-700">
                      {pct}%
                      <span className="inline-block ml-1.5 w-16 h-1.5 bg-cream-100 rounded-full overflow-hidden align-middle">
                        <span className="block h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                      </span>
                    </span>
                  </div>
                )
              }

              if (typeof value === "object") {
                return (
                  <div key={key} className="text-xs">
                    <span className="text-cream-500 font-medium block mb-0.5">{label}</span>
                    <pre className="bg-cream-50 border border-cream-200 rounded-md p-2 text-[11px] font-mono text-cream-700 overflow-auto max-h-40">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  </div>
                )
              }

              if (typeof value === "string" && value.length > 120) {
                return (
                  <div key={key} className="text-xs">
                    <span className="text-cream-500 font-medium block mb-0.5">{label}</span>
                    <div className="bg-cream-50 border border-cream-200 rounded-md p-2 text-[11px] text-cream-700 overflow-auto max-h-40 whitespace-pre-wrap">
                      {escapeHtml(value)}
                    </div>
                  </div>
                )
              }

              return (
                <div key={key} className="flex items-baseline gap-2 text-xs">
                  <span className="text-cream-500 font-medium">{label}</span>
                  <span className="text-cream-700">{typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}</span>
                </div>
              )
            })}
            {event.error_message && (
              <div className="bg-error-bg text-error text-xs rounded-md p-2 mt-1">
                {event.error_message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

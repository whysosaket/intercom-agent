import { useState } from "react"
import { cn } from "@/lib/utils"
import type { TraceEventData } from "@/lib/types"
import { escapeHtml } from "@/lib/utils"

const CALL_TYPE_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  mem0_search: { icon: "M", color: "#818cf8", label: "Mem0" },
  llm_call: { icon: "AI", color: "#60a5fa", label: "LLM" },
  http_fetch: { icon: "H", color: "#6b7280", label: "HTTP" },
  computation: { icon: "C", color: "#8b95a5", label: "Compute" },
  agent_call: { icon: "A", color: "#818cf8", label: "Agent" },
}

function getConfig(callType: string) {
  return CALL_TYPE_CONFIG[callType] || { icon: "?", color: "#6b7280", label: callType }
}

function formatDetailLabel(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

function getConfidenceColor(confidence: number) {
  if (confidence >= 0.8) return "#34d399"
  if (confidence >= 0.5) return "#fbbf24"
  return "#f87171"
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
      {/* Connector */}
      <div className="flex flex-col items-center w-8 flex-shrink-0">
        <div
          className={cn(
            "w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 transition-all duration-300",
            statusClass === "completed"
              ? "text-white shadow-[0_0_10px_rgba(0,0,0,0.2)]"
              : "bg-graphite-900 border-2",
          )}
          style={{
            borderColor: statusClass !== "completed" ? config.color : undefined,
            backgroundColor: statusClass === "completed" ? config.color : undefined,
            color: statusClass !== "completed" ? config.color : undefined,
            boxShadow: statusClass === "completed" ? `0 0 12px ${config.color}30` : undefined,
          }}
        >
          {config.icon}
        </div>
        {!isLast && <div className="w-px flex-1 bg-[rgba(255,255,255,0.06)] min-h-[16px]" />}
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
                className="inline-flex px-1.5 py-0.5 rounded-md text-[10px] font-semibold"
                style={{
                  backgroundColor: `${config.color}15`,
                  color: config.color,
                }}
              >
                {config.label}
              </span>
              <span className="text-sm font-medium text-graphite-200">{event.label}</span>
            </div>
            {(event.input_summary || event.output_summary) && (
              <div className="flex flex-col gap-0.5 mt-1">
                {event.input_summary && (
                  <span className="text-xs text-graphite-400 truncate block">{event.input_summary}</span>
                )}
                {event.output_summary && (
                  <span className="text-xs text-graphite-500 truncate block">{event.output_summary}</span>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
            {statusClass === "error" && (
              <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-error/10 text-error">ERROR</span>
            )}
            {statusClass === "skipped" && (
              <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-[rgba(255,255,255,0.04)] text-graphite-500">SKIPPED</span>
            )}
            {durationLabel && <span className="text-xs text-graphite-500 font-mono">{durationLabel}</span>}
            <span
              className={cn(
                "text-[10px] text-graphite-500 transition-transform duration-200",
                expanded && "rotate-90",
              )}
            >
              &#9654;
            </span>
          </div>
        </button>

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
                    <span className="text-graphite-400 font-medium">{label}</span>
                    <span className="text-graphite-200">
                      {pct}%
                      <span className="inline-block ml-1.5 w-16 h-1.5 bg-graphite-800 rounded-full overflow-hidden align-middle">
                        <span className="block h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
                      </span>
                    </span>
                  </div>
                )
              }

              if (typeof value === "object") {
                return (
                  <div key={key} className="text-xs">
                    <span className="text-graphite-400 font-medium block mb-0.5">{label}</span>
                    <pre className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] rounded-lg p-2 text-[11px] font-mono text-graphite-300 overflow-auto max-h-40">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  </div>
                )
              }

              if (typeof value === "string" && value.length > 120) {
                return (
                  <div key={key} className="text-xs">
                    <span className="text-graphite-400 font-medium block mb-0.5">{label}</span>
                    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] rounded-lg p-2 text-[11px] text-graphite-300 overflow-auto max-h-40 whitespace-pre-wrap">
                      {escapeHtml(value)}
                    </div>
                  </div>
                )
              }

              return (
                <div key={key} className="flex items-baseline gap-2 text-xs">
                  <span className="text-graphite-400 font-medium">{label}</span>
                  <span className="text-graphite-200">{typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}</span>
                </div>
              )
            })}
            {event.error_message && (
              <div className="bg-error/8 text-error text-xs rounded-lg p-2 mt-1 border border-error/10">
                {event.error_message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

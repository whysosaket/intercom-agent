import type { TraceEventData } from "@/lib/types"
import { TraceEvent } from "./TraceEvent"

interface TraceTimelineProps {
  trace: TraceEventData[]
  totalMs?: number
  content?: string
  confidence?: number
}

function getConfidenceColor(confidence: number) {
  if (confidence >= 0.8) return "#34d399"
  if (confidence >= 0.5) return "#fbbf24"
  return "#f87171"
}

export function TraceTimeline({ trace, totalMs, content, confidence }: TraceTimelineProps) {
  if (!trace || trace.length === 0) {
    return <p className="text-graphite-500 text-sm px-4 py-8 text-center">No trace data available.</p>
  }

  const confPct = ((confidence ?? 0) * 100).toFixed(0)
  const confColor = getConfidenceColor(confidence ?? 0)

  return (
    <div className="space-y-0">
      <div className="px-1">
        {trace.map((event, i) => (
          <TraceEvent key={i} event={event} isLast={i === trace.length - 1} />
        ))}
      </div>

      {content && (
        <div className="border-t border-[rgba(255,255,255,0.04)] pt-3 mt-2 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-graphite-400 font-medium">Final Response</span>
            <span className="text-graphite-200 flex items-center gap-1.5">
              {confPct}% confidence
              <span className="inline-block w-16 h-1.5 bg-graphite-800 rounded-full overflow-hidden">
                <span
                  className="block h-full rounded-full transition-all duration-700"
                  style={{ width: `${confPct}%`, backgroundColor: confColor }}
                />
              </span>
            </span>
          </div>
          {totalMs !== undefined && totalMs > 0 && (
            <div className="text-[11px] text-graphite-500 font-mono">{totalMs}ms total</div>
          )}
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] rounded-xl p-3 text-xs text-graphite-300 max-h-48 overflow-auto whitespace-pre-wrap">
            {content}
          </div>
        </div>
      )}
    </div>
  )
}

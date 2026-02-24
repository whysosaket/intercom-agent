import type { TraceEventData } from "@/lib/types"
import { TraceEvent } from "./TraceEvent"

interface TraceTimelineProps {
  trace: TraceEventData[]
  totalMs?: number
  content?: string
  confidence?: number
}

function getConfidenceColor(confidence: number) {
  if (confidence >= 0.8) return "#059669"
  if (confidence >= 0.5) return "#d97706"
  return "#dc2626"
}

export function TraceTimeline({ trace, totalMs, content, confidence }: TraceTimelineProps) {
  if (!trace || trace.length === 0) {
    return <p className="text-cream-400 text-sm px-4 py-8 text-center">No trace data available.</p>
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

      {/* Response summary */}
      {content && (
        <div className="border-t border-cream-200 pt-3 mt-2 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-cream-500 font-medium">Final Response</span>
            <span className="text-cream-700 flex items-center gap-1.5">
              {confPct}% confidence
              <span className="inline-block w-16 h-1.5 bg-cream-100 rounded-full overflow-hidden">
                <span
                  className="block h-full rounded-full"
                  style={{ width: `${confPct}%`, backgroundColor: confColor }}
                />
              </span>
            </span>
          </div>
          {totalMs !== undefined && totalMs > 0 && (
            <div className="text-[11px] text-cream-400 font-mono">{totalMs}ms total</div>
          )}
          <div className="bg-cream-50 border border-cream-200 rounded-md p-2 text-xs text-cream-700 max-h-48 overflow-auto whitespace-pre-wrap">
            {content}
          </div>
        </div>
      )}
    </div>
  )
}

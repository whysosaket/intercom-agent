import type { TraceEventData } from "@/lib/types"
import { TraceTimeline } from "@/components/shared/TraceTimeline"

interface PipelineTracePanelProps {
  trace: TraceEventData[] | undefined
  totalMs: number | undefined
  content: string | undefined
  confidence: number | undefined
}

export function PipelineTracePanel({ trace, totalMs, content, confidence }: PipelineTracePanelProps) {
  return (
    <aside className="w-[440px] bg-elevated border-l border-cream-200 flex-shrink-0 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-cream-200">
        <h2 className="text-sm font-semibold text-cream-800">Pipeline Trace</h2>
        {totalMs !== undefined && totalMs > 0 && (
          <span className="text-xs text-cream-400 font-mono">{totalMs}ms total</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {trace && trace.length > 0 ? (
          <TraceTimeline trace={trace} totalMs={totalMs} content={content} confidence={confidence} />
        ) : (
          <p className="text-cream-400 text-sm text-center py-8">Click an assistant message to see the pipeline trace.</p>
        )}
      </div>
    </aside>
  )
}

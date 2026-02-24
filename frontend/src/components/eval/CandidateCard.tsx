import { useState } from "react"
import { cn } from "@/lib/utils"
import type { Candidate } from "@/lib/types"
import { ConfidenceBadge } from "@/components/shared/ConfidenceBadge"
import { TraceTimeline } from "@/components/shared/TraceTimeline"
import { Button } from "@/components/ui/button"

interface CandidateCardProps {
  candidate: Candidate
  index: number
  isSent: boolean
  onApprove: (text: string) => void
  onEdit: (text: string) => void
}

export function CandidateCard({ candidate, index, isSent, onApprove, onEdit }: CandidateCardProps) {
  const [showTrace, setShowTrace] = useState(false)

  return (
    <div className={cn(
      "glass-elevated rounded-2xl p-4 transition-all duration-300",
      candidate.error && "border-error/20 bg-error/5"
    )}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-graphite-400">Candidate {index + 1}</span>
        <ConfidenceBadge confidence={candidate.confidence || 0} />
        <span className="text-[11px] text-graphite-600 font-mono ml-auto">{candidate.total_duration_ms || 0}ms</span>
      </div>

      <div className="text-sm text-graphite-200 whitespace-pre-wrap mb-2">
        {candidate.text || "(empty)"}
      </div>

      {candidate.reasoning && (
        <div className="text-xs text-graphite-500 mb-3">
          <span className="font-medium text-graphite-400">Reasoning:</span> {candidate.reasoning}
        </div>
      )}

      {!isSent && !candidate.error && (
        <div className="flex gap-2 mb-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-success/20 text-success hover:bg-success/10 hover:border-success/30 hover:shadow-[0_0_12px_rgba(52,211,153,0.1)]"
            onClick={() => onApprove(candidate.text)}
          >
            &#10003; Approve &amp; Send
          </Button>
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => onEdit(candidate.text)}>
            Edit &amp; Send
          </Button>
        </div>
      )}

      {isSent && (
        <span className="text-[11px] text-graphite-500 block mb-2">Response sent to this conversation</span>
      )}

      {candidate.pipeline_trace && candidate.pipeline_trace.length > 0 && (
        <>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 text-[11px] text-graphite-500 px-0"
            onClick={() => setShowTrace(!showTrace)}
          >
            {showTrace ? "Hide Trace" : "Show Trace"}
          </Button>
          {showTrace && (
            <div className="mt-2 border-t border-[rgba(255,255,255,0.04)] pt-2">
              <TraceTimeline
                trace={candidate.pipeline_trace}
                totalMs={candidate.total_duration_ms}
                content={candidate.text}
                confidence={candidate.confidence}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}

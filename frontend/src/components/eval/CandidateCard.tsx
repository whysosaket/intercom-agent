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
    <div className={cn("border border-cream-200 rounded-xl p-4 bg-elevated", candidate.error && "border-error/30 bg-error-bg")}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-cream-600">Candidate {index + 1}</span>
        <ConfidenceBadge confidence={candidate.confidence || 0} />
        <span className="text-[11px] text-cream-400 font-mono ml-auto">{candidate.total_duration_ms || 0}ms</span>
      </div>

      {/* Response text */}
      <div className="text-sm text-cream-800 whitespace-pre-wrap mb-2">
        {candidate.text || "(empty)"}
      </div>

      {/* Reasoning */}
      {candidate.reasoning && (
        <div className="text-xs text-cream-500 mb-3">
          <span className="font-medium text-cream-600">Reasoning:</span> {candidate.reasoning}
        </div>
      )}

      {/* Action buttons */}
      {!isSent && !candidate.error && (
        <div className="flex gap-2 mb-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-success/30 text-success hover:bg-success-bg"
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
        <span className="text-[11px] text-cream-400 block mb-2">Response sent to this conversation</span>
      )}

      {/* Trace toggle */}
      {candidate.pipeline_trace && candidate.pipeline_trace.length > 0 && (
        <>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 text-[11px] text-cream-400 px-0"
            onClick={() => setShowTrace(!showTrace)}
          >
            {showTrace ? "Hide Trace" : "Show Trace"}
          </Button>
          {showTrace && (
            <div className="mt-2 border-t border-cream-200 pt-2">
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

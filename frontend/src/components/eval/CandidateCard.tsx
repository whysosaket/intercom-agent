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
  onRefine?: (index: number, instructions: string) => void
  isRefining?: boolean
}

export function CandidateCard({ candidate, index, isSent, onApprove, onEdit, onRefine, isRefining }: CandidateCardProps) {
  const [showTrace, setShowTrace] = useState(false)
  const [showRefine, setShowRefine] = useState(false)
  const [refineInput, setRefineInput] = useState("")

  return (
    <div className={cn("border border-cream-200 rounded-xl p-4 bg-elevated", candidate.error && "border-error/30 bg-error-bg")}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-cream-600">Candidate {index + 1}</span>
        <ConfidenceBadge confidence={candidate.confidence || 0} />
        {candidate.refined && (
          <span className="text-[10px] font-medium text-accent-600 bg-accent-600/10 px-1.5 py-0.5 rounded-full">
            Refined
          </span>
        )}
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

      {/* Refinement UI for low-confidence candidates */}
      {!isSent && !candidate.error && candidate.confidence < 0.8 && onRefine && (
        <div className="mt-2">
          {!showRefine ? (
            <Button
              size="sm"
              variant="ghost"
              className="h-6 text-[11px] text-accent-600 px-0"
              onClick={() => setShowRefine(true)}
              disabled={isRefining}
            >
              {isRefining ? "Refining..." : "Refine Response"}
            </Button>
          ) : (
            <div className="flex flex-col gap-2 mt-1 p-3 bg-cream-50 rounded-lg border border-cream-200">
              <label className="text-[11px] font-medium text-cream-600">
                Describe what to add or change:
              </label>
              <textarea
                value={refineInput}
                onChange={(e) => setRefineInput(e.target.value)}
                placeholder="e.g., Add information about pricing tiers..."
                rows={2}
                className="resize-none rounded-lg border border-cream-200 bg-white px-3 py-2 text-xs text-cream-900 placeholder:text-cream-400 outline-none focus:ring-2 focus:ring-accent-300"
                disabled={isRefining}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => {
                    if (refineInput.trim()) {
                      onRefine(index, refineInput.trim())
                      setRefineInput("")
                      setShowRefine(false)
                    }
                  }}
                  disabled={!refineInput.trim() || isRefining}
                >
                  {isRefining ? "Refining..." : "Refine"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => {
                    setShowRefine(false)
                    setRefineInput("")
                  }}
                  disabled={isRefining}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
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

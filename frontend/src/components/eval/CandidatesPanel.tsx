import type { Candidate } from "@/lib/types"
import { CandidateCard } from "./CandidateCard"
import { EmptyState } from "@/components/shared/EmptyState"

interface CandidatesPanelProps {
  candidates: Candidate[]
  isSent: boolean
  onApprove: (text: string) => void
  onEdit: (text: string) => void
  onRefine?: (index: number, instructions: string) => void
  refiningIndex?: number | null
}

export function CandidatesPanel({ candidates, isSent, onApprove, onEdit, onRefine, refiningIndex }: CandidatesPanelProps) {
  return (
    <aside className="flex flex-col border-l border-cream-200 bg-elevated overflow-hidden">
      <div className="flex items-center px-5 py-3 border-b border-cream-200 flex-shrink-0">
        <h2 className="text-sm font-semibold text-cream-800">Candidate Responses</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {candidates.length === 0 ? (
          <EmptyState title="Generate responses to see candidates here." />
        ) : (
          candidates.map((candidate, i) => (
            <CandidateCard
              key={i}
              candidate={candidate}
              index={i}
              isSent={isSent}
              onApprove={onApprove}
              onEdit={onEdit}
              onRefine={onRefine}
              isRefining={refiningIndex === i}
            />
          ))
        )}
      </div>
    </aside>
  )
}

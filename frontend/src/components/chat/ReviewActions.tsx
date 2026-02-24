import { Button } from "@/components/ui/button"

interface ReviewActionsProps {
  onApprove: () => void
  onEdit: () => void
  onReject: () => void
}

export function ReviewActions({ onApprove, onEdit, onReject }: ReviewActionsProps) {
  return (
    <div className="flex gap-1.5 mt-2">
      <Button
        size="sm"
        variant="outline"
        className="h-7 text-xs border-success/20 text-success hover:bg-success/10 hover:border-success/30 hover:shadow-[0_0_12px_rgba(52,211,153,0.1)]"
        onClick={onApprove}
      >
        Approve
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-7 text-xs"
        onClick={onEdit}
      >
        Edit
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 text-xs text-graphite-500 hover:text-error"
        onClick={onReject}
      >
        Reject
      </Button>
    </div>
  )
}

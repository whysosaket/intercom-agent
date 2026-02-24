import { Button } from "@/components/ui/button"

interface ReviewActionsProps {
  onApprove: () => void
  onEdit: () => void
  onReject: () => void
}

export function ReviewActions({ onApprove, onEdit, onReject }: ReviewActionsProps) {
  return (
    <div className="flex gap-1.5 mt-1.5">
      <Button
        size="sm"
        variant="outline"
        className="h-7 text-xs border-success/30 text-success hover:bg-success-bg hover:text-success"
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
        className="h-7 text-xs text-cream-500 hover:text-error"
        onClick={onReject}
      >
        Reject
      </Button>
    </div>
  )
}

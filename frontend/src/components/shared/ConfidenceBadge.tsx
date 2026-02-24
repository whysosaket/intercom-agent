import { cn } from "@/lib/utils"

interface ConfidenceBadgeProps {
  confidence: number
  className?: string
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const pct = (confidence * 100).toFixed(0)

  const colorClass =
    confidence >= 0.8
      ? "bg-success-bg text-success"
      : confidence >= 0.5
        ? "bg-warning-bg text-warning"
        : "bg-error-bg text-error"

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
        colorClass,
        className,
      )}
    >
      Confidence: {pct}%
    </span>
  )
}

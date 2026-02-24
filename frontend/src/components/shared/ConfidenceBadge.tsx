import { cn } from "@/lib/utils"

interface ConfidenceBadgeProps {
  confidence: number
  className?: string
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const pct = (confidence * 100).toFixed(0)

  const colorClass =
    confidence >= 0.8
      ? "bg-success/10 text-success border-success/15"
      : confidence >= 0.5
        ? "bg-warning/10 text-warning border-warning/15"
        : "bg-error/10 text-error border-error/15"

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border transition-all duration-300",
        colorClass,
        className,
      )}
    >
      Confidence: {pct}%
    </span>
  )
}

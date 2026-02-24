import { cn } from "@/lib/utils"

interface ReportStats {
  total: number
  autoSend: number
  needsReview: number
  escalated: number
  errors: number
  avgConf: number
  pending: number
}

interface EvalReportProps {
  stats: ReportStats | null
}

function StatItem({
  value,
  label,
  className,
}: {
  value: string | number
  label: string
  className?: string
}) {
  return (
    <div className={cn("flex flex-col items-center", className)}>
      <span className="text-lg font-semibold tracking-tight">{value}</span>
      <span className="text-[11px] text-graphite-500">{label}</span>
    </div>
  )
}

export function EvalReport({ stats }: EvalReportProps) {
  if (!stats) return null

  const avgConfDisplay = stats.avgConf > 0 ? `${(stats.avgConf * 100).toFixed(0)}%` : "—"

  return (
    <div className="flex items-center gap-7 flex-wrap px-5 py-3 border-b border-[rgba(255,255,255,0.04)] glass-elevated">
      <StatItem value={stats.total} label="Generated" className="text-graphite-200" />
      <StatItem value={stats.autoSend} label="Auto-send" className="text-success" />
      <StatItem value={stats.needsReview} label="Needs review" className="text-warning" />
      <StatItem value={stats.escalated} label="Escalated" className="text-error" />
      {stats.errors > 0 && <StatItem value={stats.errors} label="Errors" className="text-error" />}
      <StatItem value={avgConfDisplay} label="Avg confidence" className="text-graphite-200" />
      {stats.pending > 0 && <StatItem value={stats.pending} label="Pending" className="text-ice-400" />}
    </div>
  )
}

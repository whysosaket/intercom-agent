interface EmptyStateProps {
  title: string
  hint?: string
}

export function EmptyState({ title, hint }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <p className="text-graphite-400 text-base font-light">{title}</p>
      {hint && <p className="text-graphite-600 text-sm mt-1.5">{hint}</p>}
    </div>
  )
}

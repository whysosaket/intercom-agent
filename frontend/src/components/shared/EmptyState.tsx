interface EmptyStateProps {
  title: string
  hint?: string
}

export function EmptyState({ title, hint }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <p className="text-cream-500 text-base">{title}</p>
      {hint && <p className="text-cream-400 text-sm mt-1">{hint}</p>}
    </div>
  )
}

"use client"

import { cn } from "@/lib/utils"

export type GenerateMode = "unanswered" | "all"

interface GenerateModePickerProps {
  value: GenerateMode
  onChange: (mode: GenerateMode) => void
  disabled?: boolean
}

const options: { value: GenerateMode; label: string }[] = [
  { value: "unanswered", label: "Unanswered" },
  { value: "all", label: "All" },
]

export function GenerateModePicker({
  value,
  onChange,
  disabled = false,
}: GenerateModePickerProps) {
  return (
    <div
      role="group"
      aria-label="Generate mode"
      className={cn(
        "inline-flex h-8 rounded-lg border border-cream-200 bg-cream-50/80 p-0.5 shadow-xs",
        "dark:border-zinc-700 dark:bg-zinc-800/50",
        disabled && "opacity-60"
      )}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={value === opt.value}
          disabled={disabled}
          onClick={() => onChange(opt.value)}
          className={cn(
            "relative w-full min-w-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors outline-none",
            "focus-visible:ring-2 focus-visible:ring-accent-400/40 focus-visible:ring-offset-1 focus-visible:ring-offset-cream-50",
            "dark:focus-visible:ring-offset-zinc-800",
            value === opt.value
              ? "bg-elevated text-cream-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
              : "text-cream-900 hover:text-cream-800 dark:text-zinc-900 dark:hover:text-zinc-200",
            !disabled && value !== opt.value && "hover:bg-cream-100/80 dark:hover:bg-zinc-700/50"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

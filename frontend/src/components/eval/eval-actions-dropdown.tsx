"use client"

import { useState, useCallback } from "react"
import { ChevronDownIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { GenerateModePicker } from "@/components/eval/components/generate-mode-picker"
import { cn } from "@/lib/utils"

const PRESET_LIMITS = [10, 20, 50, 100]
const MIN_LIMIT = 1
const MAX_LIMIT = 500

export type GenerateMode = "unanswered" | "all"

export interface EvalActionsDropdownProps {
  fetchLimit: number
  onFetchLimitChange: (limit: number) => void
  onFetch: () => void
  generateMode: GenerateMode
  onGenerateModeChange: (mode: GenerateMode) => void
  onGenerate: () => void
  fetchDisabled: boolean
  generateDisabled: boolean
}

export function EvalActionsDropdown({
  fetchLimit,
  onFetchLimitChange,
  onFetch,
  generateMode,
  onGenerateModeChange,
  onGenerate,
  fetchDisabled,
  generateDisabled,
}: EvalActionsDropdownProps) {
  const [open, setOpen] = useState(false)
  const [limitInput, setLimitInput] = useState(String(fetchLimit))

  const handleOpenChange = (next: boolean) => {
    setOpen(next)
    if (next) setLimitInput(String(fetchLimit))
  }

  const applyLimit = useCallback(
    (value: number) => {
      const clamped = Math.min(MAX_LIMIT, Math.max(MIN_LIMIT, Math.floor(value)))
      onFetchLimitChange(clamped)
      setLimitInput(String(clamped))
    },
    [onFetchLimitChange]
  )

  const handleLimitInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value
    setLimitInput(raw)
    const n = Number(raw)
    if (!Number.isNaN(n) && n >= MIN_LIMIT && n <= MAX_LIMIT) {
      onFetchLimitChange(Math.floor(n))
    }
  }

  const handleFetch = () => {
    onFetch()
    setOpen(false)
  }

  const handleGenerate = () => {
    onGenerate()
    setOpen(false)
  }

  const disabled = fetchDisabled && generateDisabled

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 rounded-lg px-3 border-cream-200 bg-cream-50 text-cream-900 hover:bg-cream-100"
          disabled={disabled}
        >
          Eval actions
          <ChevronDownIcon
            className={cn("size-4 transition-transform", open && "rotate-180")}
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-56 rounded-lg p-3 flex flex-col gap-3 border-cream-200 bg-cream-50"
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <div className="flex flex-col gap-2">
          <DropdownMenuLabel className="text-xs font-medium text-cream-600 px-0">
            Fetch
          </DropdownMenuLabel>
          <div className="flex flex-col gap-1.5">
            <input
              type="number"
              min={MIN_LIMIT}
              max={MAX_LIMIT}
              step={1}
              value={limitInput}
              onChange={handleLimitInputChange}
              onBlur={() => {
                const n = Number(limitInput)
                if (Number.isNaN(n) || n < MIN_LIMIT) {
                  applyLimit(MIN_LIMIT)
                } else if (n > MAX_LIMIT) {
                  applyLimit(MAX_LIMIT)
                } else {
                  applyLimit(Math.floor(n))
                }
              }}
              className="h-8 w-full rounded-lg border border-cream-200 bg-cream-100 text-cream-900 text-xs px-3 outline-none focus:ring-2 focus:ring-cream-300"
            />
            <div className="flex flex-wrap gap-1">
              {PRESET_LIMITS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => applyLimit(preset)}
                  className={cn(
                    "h-6 min-w-7 rounded-md px-2 text-[11px] font-medium transition-colors",
                    fetchLimit === preset
                      ? "bg-cream-300 text-cream-900"
                      : "bg-cream-100 text-cream-600 hover:bg-cream-200 hover:text-cream-800"
                  )}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>
          <Button
            size="sm"
            className="h-8 w-full rounded-lg text-xs border-cream-200 bg-cream-100 text-cream-900 hover:bg-cream-200"
            onClick={handleFetch}
            disabled={fetchDisabled}
          >
            Fetch
          </Button>
        </div>
        <DropdownMenuSeparator className="bg-cream-200" />
        <div className="flex flex-col gap-2">
          <DropdownMenuLabel className="text-xs font-medium text-cream-600 px-0">
            Generate
          </DropdownMenuLabel>
          <GenerateModePicker
            value={generateMode}
            onChange={onGenerateModeChange}
            disabled={generateDisabled}
          />
          <Button
            size="sm"
            className="h-8 w-full rounded-lg text-xs border-cream-200 bg-cream-100 text-cream-900 hover:bg-cream-200"
            onClick={handleGenerate}
            disabled={generateDisabled}
          >
            Generate replies
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

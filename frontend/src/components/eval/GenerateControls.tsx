import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface GenerateControlsProps {
  generateMode: "unanswered" | "all"
  onModeChange: (mode: "unanswered" | "all") => void
  onGenerate: () => void
  disabled: boolean
}

export function GenerateControls({
  generateMode,
  onModeChange,
  onGenerate,
  disabled,
}: GenerateControlsProps) {
  const label = generateMode === "unanswered" ? "Generate Unanswered" : "Generate All"

  return (
    <div className="flex">
      <Button size="sm" onClick={onGenerate} disabled={disabled} className="rounded-r-none">
        {label}
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm" disabled={disabled} className="rounded-l-none border-l border-l-white/10 px-2">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => onModeChange("unanswered")}>
            Generate Unanswered
            {generateMode === "unanswered" && <span className="ml-auto text-ice-400">&#10003;</span>}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => onModeChange("all")}>
            Generate All
            {generateMode === "all" && <span className="ml-auto text-ice-400">&#10003;</span>}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

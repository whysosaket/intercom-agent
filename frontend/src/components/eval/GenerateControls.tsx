import { Button } from "@/components/ui/button"
import { GenerateModePicker } from "@/components/eval/components/generate-mode-picker"

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
  return (
    <div className="flex items-center gap-2">
      <GenerateModePicker
        value={generateMode}
        onChange={onModeChange}
        disabled={disabled}
      />
      <Button size="sm" onClick={onGenerate} disabled={disabled} className="h-8 rounded-lg">
        Generate
      </Button>
    </div>
  )
}

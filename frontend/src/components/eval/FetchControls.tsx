import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface FetchControlsProps {
  limit: number
  onLimitChange: (limit: number) => void
  onFetch: () => void
  disabled: boolean
}

export function FetchControls({ limit, onLimitChange, onFetch, disabled }: FetchControlsProps) {
  return (
    <div className="flex items-center gap-2">
      <Select value={String(limit)} onValueChange={(v) => onLimitChange(Number(v))}>
        <SelectTrigger className="h-8 w-20 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="10">10</SelectItem>
          <SelectItem value="20">20</SelectItem>
          <SelectItem value="50">50</SelectItem>
          <SelectItem value="100">100</SelectItem>
        </SelectContent>
      </Select>
      <Button size="sm" onClick={onFetch} disabled={disabled}>
        Fetch Conversations
      </Button>
    </div>
  )
}

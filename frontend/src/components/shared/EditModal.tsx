import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

interface EditModalProps {
  open: boolean
  initialText: string
  onSave: (text: string) => void
  onCancel: () => void
}

export function EditModal({ open, initialText, onSave, onCancel }: EditModalProps) {
  const [text, setText] = useState(initialText)

  useEffect(() => {
    if (open) setText(initialText)
  }, [open, initialText])

  const handleSave = () => {
    const trimmed = text.trim()
    if (trimmed) onSave(trimmed)
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel() }}>
      <DialogContent className="sm:max-w-lg bg-elevated">
        <DialogHeader>
          <DialogTitle>Edit Response</DialogTitle>
        </DialogHeader>
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          className="resize-y"
          autoFocus
        />
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save &amp; Send</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

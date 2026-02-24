import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.03)] px-4 py-3 text-sm text-graphite-100 placeholder:text-graphite-500 shadow-xs transition-all duration-300 outline-none backdrop-blur-sm focus:border-[rgba(59,115,245,0.3)] focus:bg-[rgba(255,255,255,0.04)] focus:shadow-[0_0_0_3px_rgba(59,115,245,0.08),0_0_16px_rgba(59,115,245,0.06)] disabled:cursor-not-allowed disabled:opacity-40",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }

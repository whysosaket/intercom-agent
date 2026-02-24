import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-ice-500/30 focus-visible:ring-offset-0 active:scale-[0.98] cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-ice-600 text-white hover:bg-ice-500 shadow-[0_0_16px_rgba(59,115,245,0.2),inset_0_1px_0_rgba(255,255,255,0.1)] hover:shadow-[0_0_24px_rgba(59,115,245,0.3),inset_0_1px_0_rgba(255,255,255,0.15)]",
        destructive:
          "bg-error/80 text-white hover:bg-error shadow-[0_0_12px_rgba(248,113,113,0.15)]",
        outline:
          "border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.03)] text-graphite-200 hover:bg-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.12)] hover:text-graphite-50 backdrop-blur-sm",
        secondary:
          "bg-[rgba(255,255,255,0.05)] text-graphite-200 hover:bg-[rgba(255,255,255,0.08)] hover:text-graphite-50 border border-[rgba(255,255,255,0.04)]",
        ghost:
          "text-graphite-300 hover:text-graphite-100 hover:bg-[rgba(255,255,255,0.05)]",
        link: "text-ice-400 underline-offset-4 hover:underline hover:text-ice-300",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        xs: "h-6 gap-1 rounded-lg px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 rounded-lg gap-1.5 px-3 has-[>svg]:px-2.5 text-xs",
        lg: "h-10 rounded-xl px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-xs": "size-6 rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8 rounded-lg",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }

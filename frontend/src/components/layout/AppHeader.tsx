import { Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

interface AppHeaderProps {
  statusBadge?: string
  actions?: ReactNode
}

export function AppHeader({ statusBadge, actions }: AppHeaderProps) {
  const location = useLocation()
  const isChat = location.pathname === "/chat" || location.pathname === "/"

  return (
    <header className="glass-elevated flex items-center justify-between h-14 px-6 flex-shrink-0 border-b border-[rgba(255,255,255,0.04)]">
      <div className="flex items-center gap-4">
        <Link
          to="/chat"
          className="text-lg font-semibold text-graphite-50 no-underline tracking-tight hover:text-ice-400 transition-colors duration-300"
        >
          AutoMeet
        </Link>

        <nav className="flex items-center gap-1 ml-2">
          <Link to="/chat">
            <span
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium tracking-wide transition-all duration-300 cursor-pointer",
                isChat
                  ? "bg-[rgba(59,115,245,0.12)] text-ice-400 shadow-[0_0_12px_rgba(59,115,245,0.1)]"
                  : "text-graphite-400 hover:text-graphite-200 hover:bg-[rgba(255,255,255,0.04)]",
              )}
            >
              Chat
            </span>
          </Link>
          <Link to="/eval">
            <span
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium tracking-wide transition-all duration-300 cursor-pointer",
                !isChat
                  ? "bg-[rgba(59,115,245,0.12)] text-ice-400 shadow-[0_0_12px_rgba(59,115,245,0.1)]"
                  : "text-graphite-400 hover:text-graphite-200 hover:bg-[rgba(255,255,255,0.04)]",
              )}
            >
              Evals
            </span>
          </Link>
        </nav>

        {statusBadge && (
          <span className="text-xs text-graphite-400 bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.06)] px-2.5 py-1 rounded-full font-mono">
            {statusBadge}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {actions}
      </div>
    </header>
  )
}

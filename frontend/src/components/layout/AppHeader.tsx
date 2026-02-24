import { Link, useLocation } from "react-router-dom"
import { Button } from "@/components/ui/button"
import type { ReactNode } from "react"

interface AppHeaderProps {
  statusBadge?: string
  actions?: ReactNode
}

export function AppHeader({ statusBadge, actions }: AppHeaderProps) {
  const location = useLocation()
  const isChat = location.pathname === "/chat" || location.pathname === "/"
  const pageLabel = isChat ? "Chat" : "Dashboard"

  return (
    <header className="flex items-center justify-between h-14 px-5 border-b border-cream-200 bg-elevated flex-shrink-0">
      <div className="flex items-center gap-3">
        <Link to="/chat" className="text-lg font-semibold text-cream-900 no-underline hover:text-accent-600 transition-colors">
          AutoMeet
        </Link>
        <span className="text-xs font-medium text-cream-400 uppercase tracking-wider">{pageLabel}</span>
        {statusBadge && (
          <span className="text-xs text-cream-500 bg-cream-100 px-2 py-0.5 rounded-full">{statusBadge}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {isChat ? (
          <Link to="/dashboard">
            <Button variant="ghost" size="sm">
              Dashboard &rarr;
            </Button>
          </Link>
        ) : (
          <Link to="/chat">
            <Button variant="ghost" size="sm">
              &larr; Chat
            </Button>
          </Link>
        )}
        {actions}
      </div>
    </header>
  )
}

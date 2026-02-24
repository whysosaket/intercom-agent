import { Outlet } from "react-router-dom"

export function AppLayout() {
  return (
    <div className="flex flex-col h-screen bg-surface relative">
      {/* Ambient background orbs */}
      <div className="ambient-bg" aria-hidden="true">
        <div className="ambient-orb ambient-orb-1" />
        <div className="ambient-orb ambient-orb-2" />
        <div className="ambient-orb ambient-orb-3" />
      </div>
      <div className="relative z-10 flex flex-col h-full">
        <Outlet />
      </div>
    </div>
  )
}

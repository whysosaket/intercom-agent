import { Outlet } from "react-router-dom"

export function AppLayout() {
  return (
    <div className="flex flex-col h-screen bg-surface">
      <Outlet />
    </div>
  )
}

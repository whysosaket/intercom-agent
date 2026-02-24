import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppLayout } from "./layout"
import { ChatPage } from "@/pages/ChatPage"
import { EvalPage } from "@/pages/EvalPage"

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <Navigate to="/chat" replace /> },
      { path: "/chat", element: <ChatPage /> },
      { path: "/eval", element: <EvalPage /> },
    ],
  },
])

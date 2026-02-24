export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 justify-start animate-glass-in">
      <div className="glass-elevated rounded-2xl rounded-bl-lg px-5 py-3.5">
        <div className="flex gap-1.5 items-center h-5">
          <span
            className="w-2 h-2 rounded-full bg-ice-400/60"
            style={{ animation: "typing-dot 1.4s ease-in-out infinite", animationDelay: "0ms" }}
          />
          <span
            className="w-2 h-2 rounded-full bg-ice-400/60"
            style={{ animation: "typing-dot 1.4s ease-in-out infinite", animationDelay: "200ms" }}
          />
          <span
            className="w-2 h-2 rounded-full bg-ice-400/60"
            style={{ animation: "typing-dot 1.4s ease-in-out infinite", animationDelay: "400ms" }}
          />
        </div>
      </div>
    </div>
  )
}

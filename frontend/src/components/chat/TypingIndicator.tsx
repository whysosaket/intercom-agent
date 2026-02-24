export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 justify-start">
      <div className="bg-elevated border border-cream-200 rounded-xl rounded-bl-[6px] px-4 py-3 shadow-sm">
        <div className="flex gap-1 items-center h-5">
          <span className="w-1.5 h-1.5 rounded-full bg-cream-400 animate-bounce [animation-delay:0ms]" />
          <span className="w-1.5 h-1.5 rounded-full bg-cream-400 animate-bounce [animation-delay:150ms]" />
          <span className="w-1.5 h-1.5 rounded-full bg-cream-400 animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  )
}

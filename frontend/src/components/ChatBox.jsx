/**
 * ChatBox — message list + input for interactive Q&A.
 *
 * Disabled until the summary panel is visible (status === "ready").
 * Streams tokens in-place into the latest assistant bubble.
 * Appends a "Sources" section at the end of each assistant answer.
 *
 * Props:
 *   messages: {role: 'human'|'ai', content: string, sources?: string[]}[]
 *   collectionId: string
 *   onNewMessage(msg: {role, content}) called when a human turn is appended
 *   onStreamToken(token: string) appends a token to the last AI bubble
 *   onStreamDone(sources: string[]) marks the last AI bubble complete
 *   disabled: boolean
 *   streaming: boolean
 *
 * Implemented in: T-26
 */
import { useEffect, useRef, useState } from 'react'
import { streamChat } from '../api'

function TypingDots() {
  return (
    <span className="inline-flex items-end gap-0.5 h-4">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
          style={{ animationDelay: `${i * 0.18}s`, animationDuration: '0.9s' }}
        />
      ))}
    </span>
  )
}

export default function ChatBox({
  messages,
  collectionId,
  onNewMessage,
  onStreamToken,
  onStreamDone,
  disabled,
  streaming,
}) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e) {
    e.preventDefault()
    const question = input.trim()
    if (!question || disabled || streaming) return
    setInput('')
    onNewMessage({ role: 'human', content: question })
    // AI placeholder added by parent before streaming starts
    try {
      await streamChat(
        question,
        collectionId,
        messages.filter(m => m.role === 'human' || m.role === 'ai'),
        onStreamToken,
        onStreamDone,
      )
    } catch (err) {
      onStreamDone([]) // end streaming even on error
      console.error('Chat stream error:', err)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Message list */}
      <div className="flex flex-col gap-3 max-h-[60vh] overflow-y-auto pr-1">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${
              msg.role === 'human' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                msg.role === 'human'
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm'
              }`}
            >
              {msg.role === 'ai' && msg.content === '' && streaming && i === messages.length - 1
                ? <TypingDots />
                : <span className="whitespace-pre-wrap">{msg.content}</span>
              }
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 border-t border-gray-200 pt-2">
                  <p className="text-xs font-semibold text-gray-500 mb-1">Sources</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {msg.sources.map((s, si) => (
                      <li key={si} className="text-xs text-gray-500">{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={disabled ? 'Ingest an article first…' : 'Ask a question…'}
          disabled={disabled || streaming}
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={disabled || streaming || !input.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {streaming ? '…' : 'Send'}
        </button>
      </form>
    </div>
  )
}

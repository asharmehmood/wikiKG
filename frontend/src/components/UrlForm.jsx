/**
 * UrlForm — Wikipedia URL input with submit button.
 *
 * Props:
 *   onSubmit(url: string)  called when the user submits a valid URL
 *   isLoading: boolean     disables the form while ingestion is in progress
 *   error: string | null   displayed as an error banner below the input
 *
 * Implemented in: T-26
 */
import { useEffect, useState } from 'react'

const STEPS = [
  { label: 'Fetching Wikipedia article…',  pct: 15 },
  { label: 'Chunking article text…',        pct: 38 },
  { label: 'Generating embeddings…',        pct: 65 },
  { label: 'Summarising with AI…',          pct: 85 },
]

export default function UrlForm({ onSubmit, isLoading, error }) {
  const [value, setValue] = useState('')
  const [stepIdx, setStepIdx] = useState(0)

  // Advance through stages while loading
  useEffect(() => {
    if (!isLoading) { setStepIdx(0); return }
    const delays = [3000, 5000, 14000] // ms to wait before advancing each step
    const timers = delays.map((d, i) =>
      setTimeout(() => setStepIdx(i + 1), delays.slice(0, i + 1).reduce((a, b) => a + b, 0))
    )
    return () => timers.forEach(clearTimeout)
  }, [isLoading])

  const step = STEPS[Math.min(stepIdx, STEPS.length - 1)]

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = value.trim()
    if (trimmed) onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-3">
      <div className="flex gap-2">
        <input
          type="url"
          value={value}
          onChange={e => setValue(e.target.value)}
          placeholder="https://en.wikipedia.org/wiki/…"
          disabled={isLoading}
          required
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={isLoading || !value.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <>
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Processing…
            </>
          ) : 'Ingest'}
        </button>
      </div>

      {/* Ingestion progress */}
      {isLoading && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-blue-700 font-medium">{step.label}</span>
            <span className="text-blue-500">{step.pct}%</span>
          </div>
          <div className="w-full bg-blue-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-1.5 rounded-full bg-blue-500 transition-all duration-700 ease-in-out"
              style={{ width: `${step.pct}%` }}
            />
          </div>
          <p className="text-xs text-blue-400">
            Step {stepIdx + 1} of {STEPS.length} — this may take up to 90 s on first run
          </p>
        </div>
      )}

      {error && (
        <p className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </form>
  )
}

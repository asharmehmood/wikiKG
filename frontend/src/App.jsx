/**
 * Root application component.
 *
 * Top-level state:
 *   status        — "idle" | "loading" | "ready" | "error"
 *   collectionId  — returned by POST /api/ingest
 *   articleTitle  — from ingest response
 *   summary       — from ingest response
 *   messages      — chat history [{ role, content }]
 *   error         — error string shown when status === "error"
 *
 * Implemented in: T-26
 */
export default function App() {
  // TODO T-26: implement state, layout, and wiring to child components
  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <p className="text-gray-400 text-sm">wikiKG loading…</p>
    </div>
  )
}

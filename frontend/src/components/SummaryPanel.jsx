/**
 * SummaryPanel — displays article title and AI-generated summary.
 *
 * Hidden until ingestion completes (status === "ready").
 *
 * Props:
 *   articleTitle: string
 *   summary: string
 *
 * Implemented in: T-26
 */
export default function SummaryPanel({ articleTitle, summary }) {
  if (!articleTitle) return null

  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50 p-5 shadow-sm">
      <h2 className="mb-2 text-lg font-semibold text-blue-900">{articleTitle}</h2>
      <p className="text-sm leading-relaxed text-blue-800 whitespace-pre-wrap">{summary}</p>
    </div>
  )
}

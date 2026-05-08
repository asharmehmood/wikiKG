/**
 * API client for the wikiKG backend.
 *
 * ingestUrl(url)
 *   POST /api/ingest → { article_title, summary, chunk_count, collection_id }
 *
 * streamChat(question, collectionId, history, onToken, onDone)
 *   POST /api/chat (SSE stream)
 *   Calls onToken(token: string) for each streamed token.
 *   Calls onDone(sources: string[]) on the final {"done": true, "sources": […]} event.
 *
 * SSE format emitted by routes.py (must match exactly):
 *   data: {"token": "…"}\n\n
 *   data: {"done": true, "sources": ["Section A", "…"]}\n\n
 *
 * Implemented in: T-25
 */

// Vite dev-server proxies /api → http://localhost:8000 (vite.config.js)
const BASE = ''

/**
 * @param {string} url - Wikipedia article URL
 * @returns {Promise<{article_title: string, summary: string, chunk_count: number, collection_id: string}>}
 */
export async function ingestUrl(url) {
  throw new Error('Implemented in T-25')
}

/**
 * @param {string} question
 * @param {string} collectionId
 * @param {{role: 'human'|'ai', content: string}[]} history
 * @param {(token: string) => void} onToken
 * @param {(sources: string[]) => void} onDone
 * @returns {Promise<void>}
 */
export async function streamChat(question, collectionId, history, onToken, onDone) {
  throw new Error('Implemented in T-25')
}

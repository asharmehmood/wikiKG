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
  const response = await fetch(`${BASE}/api/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })

  if (!response.ok) {
    let detail = `Server error (${response.status})`
    try {
      const body = await response.json()
      if (body.detail) detail = body.detail
    } catch (_) { /* swallow JSON parse error */ }
    throw new Error(detail)
  }

  return response.json()
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
  const response = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, collection_id: collectionId, history }),
  })

  if (!response.ok) {
    let detail = `Server error (${response.status})`
    try {
      const body = await response.json()
      if (body.detail) detail = body.detail
    } catch (_) { /* swallow */ }
    throw new Error(detail)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE chunks may contain multiple events separated by \n\n
    const parts = buffer.split('\n\n')
    buffer = parts.pop() // keep incomplete last chunk

    for (const part of parts) {
      for (const line of part.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const json = line.slice(6).trim()
        if (!json) continue

        let event
        try { event = JSON.parse(json) } catch (_) { continue }

        if (event.done === true) {
          onDone(event.sources ?? [])
        } else if (event.token !== undefined) {
          onToken(event.token)
        } else if (event.error) {
          throw new Error(event.error)
        }
      }
    }
  }
}


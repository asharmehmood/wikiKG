/**
 * Root application component.
 *
 * Top-level state:
 *   status        — "idle" | "loading" | "ready" | "error"
 *   collectionId  — returned by POST /api/ingest
 *   articleTitle  — from ingest response
 *   summary       — from ingest response
 *   messages      — chat history [{ role, content, sources? }]
 *   error         — error string shown when status === "error"
 *   streaming     — true while an AI response is being streamed
 *
 * Implemented in: T-26
 */
import { useState } from 'react'
import { ingestUrl } from './api'
import ChatBox from './components/ChatBox'
import SummaryPanel from './components/SummaryPanel'
import UrlForm from './components/UrlForm'

export default function App() {
  const [status, setStatus] = useState('idle')     // 'idle'|'loading'|'ready'|'error'
  const [collectionId, setCollectionId] = useState(null)
  const [articleTitle, setArticleTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [messages, setMessages] = useState([])
  const [error, setError] = useState(null)
  const [streaming, setStreaming] = useState(false)

  async function handleIngest(url) {
    setStatus('loading')
    setError(null)
    setMessages([])
    try {
      const data = await ingestUrl(url)
      setCollectionId(data.collection_id)
      setArticleTitle(data.article_title)
      setSummary(data.summary)
      setStatus('ready')
    } catch (err) {
      setError(err.message ?? 'Failed to ingest article.')
      setStatus('error')
    }
  }

  // Called when the user sends a question — adds human msg + AI placeholder
  function handleNewMessage(msg) {
    setMessages(prev => [
      ...prev,
      msg,
      { role: 'ai', content: '' }, // streaming placeholder
    ])
    setStreaming(true)
  }

  // Called per-token: append to last (AI) message
  function handleStreamToken(token) {
    setMessages(prev => {
      const updated = [...prev]
      const last = { ...updated[updated.length - 1] }
      last.content += token
      updated[updated.length - 1] = last
      return updated
    })
  }

  // Called when stream ends: attach sources, stop streaming
  function handleStreamDone(sources) {
    setMessages(prev => {
      const updated = [...prev]
      const last = { ...updated[updated.length - 1], sources }
      updated[updated.length - 1] = last
      return updated
    })
    setStreaming(false)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-2xl px-4 py-10 flex flex-col gap-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">wikiKG</h1>
          <p className="mt-1 text-sm text-gray-500">
            Chat with any Wikipedia article using local AI.
          </p>
        </div>

        {/* URL input */}
        <UrlForm
          onSubmit={handleIngest}
          isLoading={status === 'loading'}
          error={status === 'error' ? error : null}
        />

        {/* Article summary */}
        {status === 'ready' && (
          <SummaryPanel articleTitle={articleTitle} summary={summary} />
        )}

        {/* Chat */}
        <ChatBox
          messages={messages}
          collectionId={collectionId}
          onNewMessage={handleNewMessage}
          onStreamToken={handleStreamToken}
          onStreamDone={handleStreamDone}
          disabled={status !== 'ready'}
          streaming={streaming}
        />
      </div>
    </div>
  )
}

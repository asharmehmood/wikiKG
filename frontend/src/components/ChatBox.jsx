/**
 * ChatBox — message list + input for interactive Q&A.
 *
 * Disabled until the summary panel is visible (status === "ready").
 * Streams tokens in-place into the latest assistant bubble.
 * Appends a "Sources" section at the end of each assistant answer.
 *
 * Props:
 *   messages: {role: 'human'|'ai', content: string}[]
 *   collectionId: string
 *   onNewMessage(msg: {role, content}) called when a turn is complete
 *   disabled: boolean
 *
 * Implemented in: T-26
 */
export default function ChatBox({ messages, collectionId, onNewMessage, disabled }) {
  // TODO T-26
  return null
}

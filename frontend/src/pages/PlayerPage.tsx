import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import { VideoPlayer } from '@/components/VideoPlayer.tsx'
import type { VideoPlayerHandle } from '@/components/VideoPlayer.tsx'
import { chatVideo, getTranscript, queryVideo } from '@/lib/api.ts'
import type { ChatMessage, ChatSegment, Segment, TranscriptSegment, Video } from '@/lib/types.ts'

type PlayerPageProps = {
  videoId: string
  file: File
  segments: Segment[]
  onQueryComplete: (segments: Segment[]) => void
  onBackToUpload: () => void
}

function formatTime(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return [
    hours.toString().padStart(2, '0'),
    minutes.toString().padStart(2, '0'),
    remainingSeconds.toString().padStart(2, '0'),
  ].join(':')
}

function getTranscriptIndexForTime(transcript: TranscriptSegment[], time: number) {
  const index = transcript.findIndex((segment) => time >= segment.start && time < segment.end)
  return index >= 0 ? index : null
}

export function PlayerPage({
  videoId,
  file,
  segments,
  onQueryComplete,
  onBackToUpload,
}: PlayerPageProps) {
  const [video, setVideo] = useState<Video | null>(null)
  const videoPlayerRef = useRef<VideoPlayerHandle | null>(null)
  const transcriptItemRefs = useRef<Array<HTMLElement | null>>([])
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([])
  const [isTranscriptLoading, setIsTranscriptLoading] = useState(true)
  const [currentTime, setCurrentTime] = useState(0)

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [chatSessionId, setChatSessionId] = useState<string | undefined>(undefined)
  const chatEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setVideo({ id: videoId, url })
    setCurrentTime(0)

    return () => {
      URL.revokeObjectURL(url)
    }
  }, [file, videoId])

  useEffect(() => {
    let isCancelled = false

    async function loadTranscript() {
      setIsTranscriptLoading(true)

      try {
        const { transcript: nextTranscript } = await getTranscript(videoId)
        if (!isCancelled) {
          setTranscript(nextTranscript)
        }
      } finally {
        if (!isCancelled) {
          setIsTranscriptLoading(false)
        }
      }
    }

    void loadTranscript()

    return () => {
      isCancelled = true
    }
  }, [videoId])

  const activeTranscriptIndex = getTranscriptIndexForTime(transcript, currentTime)

  useEffect(() => {
    if (activeTranscriptIndex === null) return

    transcriptItemRefs.current[activeTranscriptIndex]?.scrollIntoView({
      block: 'nearest',
      behavior: 'smooth',
    })
  }, [activeTranscriptIndex])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!query.trim()) return

    setIsSearching(true)

    try {
      const { segments: nextSegments } = await queryVideo(videoId, query.trim())
      onQueryComplete(nextSegments)
    } finally {
      setIsSearching(false)
    }
  }

  function handleBackToUpload() {
    videoPlayerRef.current?.pause()
    onBackToUpload()
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  async function handleChatSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = chatInput.trim()
    if (!text || isChatLoading) return

    const userMessage: ChatMessage = { role: 'user', content: text }
    setChatMessages((prev) => [...prev, userMessage])
    setChatInput('')
    setIsChatLoading(true)

    try {
      const { answer, sessionId, segments } = await chatVideo(videoId, text, chatSessionId)
      setChatSessionId(sessionId)
      const assistantMessage: ChatMessage = { role: 'assistant', content: answer, segments }
      setChatMessages((prev) => [...prev, assistantMessage])
    } catch {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
      }
      setChatMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsChatLoading(false)
    }
  }

  function preprocessChatContent(content: string): string {
    // Convert [Segment N] references into markdown links so ReactMarkdown
    // can render them as clickable buttons via the custom `a` component.
    return content.replace(/\[Segment (\d+)\]/g, '[Segment $1](#segment-$1)')
  }

  return (
    <section className="page-content">
      <h2>Relevant lecture moments</h2>
      <p>Playing only the segments that match your query.</p>

      <form className="page-content" onSubmit={handleSubmit}>
        <div className="field-group">
          <label htmlFor="player-query">Try a different query</label>
          <input
            id="player-query"
            type="text"
            placeholder="What did the speaker say about neural networks?"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="button-row">
          <button className="primary-button" type="submit" disabled={!query.trim() || isSearching}>
            {isSearching ? 'Searching...' : 'Update query'}
          </button>
          <button className="secondary-button" type="button" onClick={handleBackToUpload}>
            Upload a different video
          </button>
        </div>
      </form>

      <div className="player-layout">
        <div className="player-main">
          {video && (
            <VideoPlayer
              ref={videoPlayerRef}
              src={video.url}
              segments={segments}
              onPlaybackTimeUpdate={setCurrentTime}
            />
          )}
        </div>

        <aside className="transcript-sidebar" aria-label="Transcript">
          <div className="transcript-sidebar-header">
            <div>
              <h3>Transcript</h3>
              <p>Follows the current playback position.</p>
            </div>
            <span className="transcript-current-time">{formatTime(currentTime)}</span>
          </div>

          {isTranscriptLoading ? (
            <p className="transcript-status">Loading transcript...</p>
          ) : transcript.length === 0 ? (
            <p className="transcript-status">No transcript available for this video yet.</p>
          ) : (
            <ol className="transcript-list">
              {transcript.map((segment, index) => {
                const isActive = index === activeTranscriptIndex

                return (
                  <li
                    key={`${segment.start}-${segment.end}-${index}`}
                    ref={(element) => {
                      transcriptItemRefs.current[index] = element
                    }}
                    className={isActive ? 'active' : ''}
                  >
                    <article className="transcript-item">
                      <div className="transcript-item-meta">
                        <span>{formatTime(segment.start)}</span>
                        {segment.speaker ? <span>{segment.speaker}</span> : null}
                      </div>
                      <p>{segment.text}</p>
                    </article>
                  </li>
                )
              })}
            </ol>
          )}
        </aside>
      </div>

      <section className="chat-panel" aria-label="Chat with lecture">
        <div className="chat-panel-header">
          <h3>Chat with this lecture</h3>
          <p>Ask questions and get answers grounded in the video content.</p>
        </div>

        <div className="chat-messages" role="log" aria-live="polite">
          {chatMessages.length === 0 && (
            <p className="chat-empty">No messages yet. Ask a question below.</p>
          )}
          {chatMessages.map((msg, i) => (
            <div key={i} className={`chat-message chat-message--${msg.role}`}>
              <div className="chat-bubble">
                {msg.role === 'user' ? (
                  <p>{msg.content}</p>
                ) : (
                  <div className="chat-markdown">
                    <ReactMarkdown
                      components={{
                        a({ href, children }) {
                          const match = href?.match(/^#segment-(\d+)$/)
                          if (match && msg.segments) {
                            const seg = msg.segments[parseInt(match[1], 10) - 1] as ChatSegment | undefined
                            return (
                              <button
                                type="button"
                                className="chat-segment-ref"
                                onClick={() => seg && videoPlayerRef.current?.seekTo(seg.start)}
                              >
                                {children}
                              </button>
                            )
                          }
                          return <a href={href}>{children}</a>
                        },
                      }}
                    >
                      {preprocessChatContent(msg.content)}
                    </ReactMarkdown>
                  </div>
                )}
                {msg.role === 'assistant' && msg.segments && msg.segments.length > 0 && (
                  <div className="chat-cited-segments">
                    {msg.segments.map((seg, j) => (
                      <button
                        key={j}
                        type="button"
                        className="chat-segment-chip"
                        onClick={() => videoPlayerRef.current?.seekTo(seg.start)}
                      >
                        Segment {j + 1} &nbsp; {formatTime(seg.start)} – {formatTime(seg.end)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isChatLoading && (
            <div className="chat-message chat-message--assistant">
              <div className="chat-bubble chat-bubble--loading">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <form className="chat-input-form" onSubmit={handleChatSubmit}>
          <input
            className="chat-input"
            type="text"
            placeholder="Ask about this lecture..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            disabled={isChatLoading}
          />
          <button
            className="primary-button"
            type="submit"
            disabled={!chatInput.trim() || isChatLoading}
          >
            Send
          </button>
        </form>
      </section>
    </section>
  )
}

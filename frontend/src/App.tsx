import { useState } from 'react'
import { PlayerPage } from './pages/PlayerPage'
import { QueryPage } from './pages/QueryPage'
import { UploadPage } from './pages/UploadPage'
import type { Segment } from './lib/types'

function App() {
  const [videoId, setVideoId] = useState<string | null>(null)
  const [segments, setSegments] = useState<Segment[]>([])

  return (
    <main className="app-shell">
      <div className="page-card">
        <header className="page-header">
          <p className="eyebrow">LectureClip</p>
          <h1>Find the moments that answer your question.</h1>
        </header>

        {!videoId && <UploadPage onUploadComplete={setVideoId} />}
        {videoId && segments.length === 0 && (
          <QueryPage videoId={videoId} onQueryComplete={setSegments} />
        )}
        {videoId && segments.length > 0 && (
          <PlayerPage videoId={videoId} segments={segments} />
        )}
      </div>
    </main>
  )
}

export default App

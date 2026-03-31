import { useEffect, useRef, useState } from 'react'
import { listVideos } from '@/lib/api.ts'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import type { Video } from '@/lib/types.ts'

const POLL_INTERVAL_MS = 8_000
const TIMEOUT_MS = 20 * 60 * 1000 // 20 minutes

type ProcessingPageProps = {
  videoId: string
  userId: string
  onProcessingComplete: (video: Video) => void
  onCancel: () => void
}

export function ProcessingPage({ videoId, userId, onProcessingComplete, onCancel }: ProcessingPageProps) {
  const [elapsed, setElapsed] = useState(0)
  const [timedOut, setTimedOut] = useState(false)
  const startRef = useRef(Date.now())
  const doneRef = useRef(false)

  useEffect(() => {
    async function poll() {
      if (doneRef.current) return
      if (Date.now() - startRef.current >= TIMEOUT_MS) {
        setTimedOut(true)
        return
      }
      try {
        const { videos } = await listVideos(userId)
        const match = videos.find((v) => v.videoId.endsWith(videoId))
        if (match) {
          doneRef.current = true
          onProcessingComplete(match)
          return
        }
      } catch {
        // ignore transient errors and keep polling
      }
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000))
    }

    poll()
    const id = window.setInterval(poll, POLL_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [videoId, userId, onProcessingComplete])

  const minutes = Math.floor(elapsed / 60)
  const seconds = elapsed % 60
  const elapsedLabel = minutes > 0
    ? `${minutes}m ${seconds}s`
    : `${seconds}s`

  if (timedOut) {
    return (
      <div className="max-w-lg mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>Processing is taking longer than expected</CardTitle>
            <CardDescription>
              The pipeline has been running for over 20 minutes. You can wait on the dashboard
              and open the lecture once it appears there.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={onCancel} className="w-full">Go to dashboard</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-lg mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Processing your lecture</CardTitle>
          <CardDescription>
            Your video was uploaded successfully. We're now transcribing it and building
            the search index — this usually takes a few minutes.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="relative h-12 w-12">
              <div className="absolute inset-0 rounded-full border-4 border-muted" />
              <div className="absolute inset-0 rounded-full border-4 border-primary border-t-transparent animate-spin" />
            </div>
            <div className="text-center space-y-1">
              <p className="text-sm font-medium">Building search index…</p>
              <p className="text-xs text-muted-foreground">
                {elapsed > 0 ? `Running for ${elapsedLabel}` : 'Starting pipeline…'}
              </p>
            </div>
          </div>

          <div className="space-y-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              <span>Video uploaded to S3</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
              <span>Transcribing audio</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/20" />
              <span>Generating embeddings</span>
            </div>
          </div>

          <Button variant="outline" onClick={onCancel} className="w-full">
            Cancel — go to dashboard
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
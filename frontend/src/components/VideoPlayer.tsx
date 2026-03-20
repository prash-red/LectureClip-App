import { useEffect, useRef, useState } from 'react'
import type { Segment } from '../lib/types'

type VideoPlayerProps = {
  src: string
  segments: Segment[]
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

export function VideoPlayer({ src, segments }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState(0)

  useEffect(() => {
    setCurrentSegmentIndex(0)
  }, [src, segments])

  function startSegment(index: number) {
    const video = videoRef.current
    const segment = segments[index]

    if (!video || !segment) return

    setCurrentSegmentIndex(index)
    video.currentTime = segment.start
    void video.play()
  }

  function handleLoadedMetadata() {
    startSegment(0)
  }

  function handleTimeUpdate() {
    const video = videoRef.current
    const segment = segments[currentSegmentIndex]

    if (!video || !segment) return

    if (video.currentTime < segment.start) {
      video.currentTime = segment.start
      return
    }

    if (video.currentTime < segment.end) return

    const nextIndex = currentSegmentIndex + 1

    if (nextIndex >= segments.length) {
      video.pause()
      video.currentTime = segment.end
      return
    }

    startSegment(nextIndex)
  }

  return (
    <div className="video-player">
      <video
        ref={videoRef}
        src={src}
        controls
        autoPlay
        onLoadedMetadata={handleLoadedMetadata}
        onTimeUpdate={handleTimeUpdate}
      />

      <p className="segment-meta">
        Segment {currentSegmentIndex + 1} of {segments.length}
      </p>

      <div>
        <h3>Segments</h3>
        <ul className="segment-list">
          {segments.map((segment, index) => (
            <li key={`${segment.start}-${segment.end}`} className={index === currentSegmentIndex ? 'active' : ''}>
              <span>Segment {index + 1}</span>
              <span>
                {formatTime(segment.start)} - {formatTime(segment.end)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

import { VideoPlayer } from '../components/VideoPlayer'
import type { Segment, Video } from '../lib/types'

type PlayerPageProps = {
  videoId: string
  segments: Segment[]
}

export function PlayerPage({ videoId, segments }: PlayerPageProps) {
  const video: Video = {
    id: videoId,
    url: `http://localhost:3000/videos/${videoId}.mp4`,
  }

  return (
    <section className="page-content">
      <h2>Relevant lecture moments</h2>
      <p>Playing only the segments that match your query.</p>
      <VideoPlayer src={video.url} segments={segments} />
    </section>
  )
}

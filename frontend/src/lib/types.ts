export type Segment = {
  segmentId: string
  start: number
  end: number
  idx: number
  text: string
  similarity: number
}

export type TranscriptSegment = {
  start: number
  end: number
  text: string
  speaker?: string
}

export type Video = {
  lectureId: string
  videoId: string
  title: string
  ingestedAt: string
  playbackUrl: string | null
}

export type ChatSegment = {
  segmentId: number
  start: number
  end: number
  text: string
  similarity: number
}

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  segments?: ChatSegment[]
}

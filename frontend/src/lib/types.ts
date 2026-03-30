export type Segment = {
  start: number
  end: number
}

export type TranscriptSegment = {
  start: number
  end: number
  text: string
  speaker?: string
}

export type Video = {
  id: string
  url: string
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

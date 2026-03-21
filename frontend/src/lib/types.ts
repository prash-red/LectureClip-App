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

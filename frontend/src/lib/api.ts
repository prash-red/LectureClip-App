import type { Segment, TranscriptSegment } from '@/lib/types.ts'

const mockSegments: Segment[] = [
  { start: 12, end: 28 },
  { start: 46, end: 64 },
  { start: 88, end: 102 },
]

const mockTranscript: TranscriptSegment[] = [
  {
    start: 0,
    end: 10,
    speaker: 'Speaker',
    text: 'Today we are going to look at how models learn patterns from examples.',
  },
  {
    start: 10,
    end: 21,
    speaker: 'Speaker',
    text: 'When we talk about neural networks, the key idea is learning layered representations.',
  },
  {
    start: 21,
    end: 34,
    speaker: 'Speaker',
    text: 'Each layer transforms the input a little further so the model can capture more abstract features.',
  },
  {
    start: 34,
    end: 46,
    speaker: 'Speaker',
    text: 'That is why we spend time thinking carefully about the structure of the network.',
  },
  {
    start: 46,
    end: 58,
    speaker: 'Speaker',
    text: 'Backpropagation gives us a way to measure which parameters should change after each example.',
  },
  {
    start: 58,
    end: 71,
    speaker: 'Speaker',
    text: 'Once gradients are available, optimization methods like gradient descent update the weights.',
  },
  {
    start: 71,
    end: 88,
    speaker: 'Speaker',
    text: 'In practice, we tune batch size, learning rate, and regularization together rather than separately.',
  },
  {
    start: 88,
    end: 96,
    speaker: 'Speaker',
    text: 'Evaluation matters because a lower training loss does not always mean better generalization.',
  },
  {
    start: 96,
    end: 108,
    speaker: 'Speaker',
    text: 'You want to compare validation metrics and inspect where the model still makes mistakes.',
  },
]

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export async function uploadVideo(file: File): Promise<{ videoId: string }> {
  void file
  await sleep(400)
  return { videoId: 'vid_123' }
}

export async function queryVideo(
  videoId: string,
  query: string,
): Promise<{ segments: Segment[] }> {
  void videoId
  void query
  await sleep(400)
  return { segments: mockSegments }
}

export async function getTranscript(videoId: string): Promise<{ transcript: TranscriptSegment[] }> {
  void videoId
  await sleep(400)
  return { transcript: mockTranscript }
}

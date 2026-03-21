import { describe, expect, it, vi } from 'vitest'
import { getTranscript, queryVideo, uploadVideo } from '@/lib/api.ts'

describe('api mocks', () => {
  it('returns a video id after the simulated upload delay', async () => {
    vi.useFakeTimers()

    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })
    const uploadPromise = uploadVideo(file)

    await vi.runAllTimersAsync()

    await expect(uploadPromise).resolves.toEqual({ videoId: 'vid_123' })

    vi.useRealTimers()
  })

  it('returns canned segments for queries', async () => {
    vi.useFakeTimers()

    const queryPromise = queryVideo('vid_123', 'neural networks')

    await vi.runAllTimersAsync()

    await expect(queryPromise).resolves.toEqual({
      segments: [
        { start: 12, end: 28 },
        { start: 46, end: 64 },
        { start: 88, end: 102 },
      ],
    })

    vi.useRealTimers()
  })

  it('returns the mock transcript for transcript requests', async () => {
    vi.useFakeTimers()

    const transcriptPromise = getTranscript('vid_123')

    await vi.runAllTimersAsync()

    await expect(transcriptPromise).resolves.toMatchObject({
      transcript: expect.arrayContaining([
        expect.objectContaining({
          start: 10,
          end: 21,
          speaker: 'Speaker',
        }),
      ]),
    })

    vi.useRealTimers()
  })
})

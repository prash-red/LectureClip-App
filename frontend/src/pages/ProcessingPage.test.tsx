import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { listVideos } from '@/lib/api.ts'
import { ProcessingPage } from '@/pages/ProcessingPage.tsx'
import type { Video } from '@/lib/types.ts'

vi.mock('@/lib/api.ts', () => ({
  listVideos: vi.fn(),
}))

const matchingVideo: Video = {
  lectureId: 'lec-1',
  videoId: 's3://bucket/ts/user@example.com/lecture.mp4',
  title: 'lecture.mp4',
  ingestedAt: '2024-01-15T10:00:00Z',
  playbackUrl: null,
}

// ── Tests using real timers ──────────────────────────────────────────────────

describe('ProcessingPage — basic behaviour', () => {
  it('shows the processing card with initial status', () => {
    vi.mocked(listVideos).mockResolvedValue({ videos: [] })
    render(
      <ProcessingPage
        videoId="ts/user@example.com/lecture.mp4"
        userId="user@example.com"
        onProcessingComplete={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByText('Processing your lecture')).toBeInTheDocument()
    expect(screen.getByText('Starting pipeline…')).toBeInTheDocument()
    expect(screen.getByText('Video uploaded to S3')).toBeInTheDocument()
  })

  it('calls onProcessingComplete when the video appears in the list', async () => {
    const onProcessingComplete = vi.fn()
    vi.mocked(listVideos).mockResolvedValue({ videos: [matchingVideo] })

    render(
      <ProcessingPage
        videoId="ts/user@example.com/lecture.mp4"
        userId="user@example.com"
        onProcessingComplete={onProcessingComplete}
        onCancel={vi.fn()}
      />,
    )

    await waitFor(() => expect(onProcessingComplete).toHaveBeenCalledWith(matchingVideo))
  })

  it('does not complete when the returned videoId does not match', async () => {
    const onProcessingComplete = vi.fn()
    vi.mocked(listVideos).mockResolvedValue({
      videos: [{ ...matchingVideo, videoId: 's3://bucket/other/video.mp4' }],
    })

    render(
      <ProcessingPage
        videoId="ts/user@example.com/lecture.mp4"
        userId="user@example.com"
        onProcessingComplete={onProcessingComplete}
        onCancel={vi.fn()}
      />,
    )

    // Give the initial poll time to settle
    await act(async () => { await Promise.resolve() })
    expect(onProcessingComplete).not.toHaveBeenCalled()
  })

  it('calls onCancel when the cancel button is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    vi.mocked(listVideos).mockResolvedValue({ videos: [] })

    render(
      <ProcessingPage
        videoId="ts/user@example.com/lecture.mp4"
        userId="user@example.com"
        onProcessingComplete={vi.fn()}
        onCancel={onCancel}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Cancel — go to dashboard' }))
    expect(onCancel).toHaveBeenCalled()
  })

})

// ── Tests using fake timers ──────────────────────────────────────────────────

describe('ProcessingPage — timeout', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the timeout card after 20 minutes have elapsed', async () => {
    const startTime = Date.now()
    vi.setSystemTime(startTime)
    vi.mocked(listVideos).mockResolvedValue({ videos: [] })

    render(
      <ProcessingPage
        videoId="ts/user@example.com/lecture.mp4"
        userId="user@example.com"
        onProcessingComplete={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    vi.setSystemTime(startTime + 20 * 60 * 1000 + 1)

    await act(async () => {
      vi.advanceTimersByTime(8_001)
      await Promise.resolve()
    })

    expect(screen.getByText('Processing is taking longer than expected')).toBeInTheDocument()
  })

  it('continues polling after a transient listVideos error', async () => {
    const onProcessingComplete = vi.fn()
    vi.mocked(listVideos)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue({ videos: [matchingVideo] })

    render(
      <ProcessingPage
        videoId="ts/user@example.com/lecture.mp4"
        userId="user@example.com"
        onProcessingComplete={onProcessingComplete}
        onCancel={vi.fn()}
      />,
    )

    // First poll (on mount) fails silently
    await act(async () => { await Promise.resolve() })
    expect(onProcessingComplete).not.toHaveBeenCalled()

    // Second poll fires after the interval
    await act(async () => {
      vi.advanceTimersByTime(8_001)
      await Promise.resolve()
    })

    expect(onProcessingComplete).toHaveBeenCalledWith(matchingVideo)
  })

  it('calls onCancel from the timeout card', async () => {
    const startTime = Date.now()
    vi.setSystemTime(startTime)
    const onCancel = vi.fn()
    vi.mocked(listVideos).mockResolvedValue({ videos: [] })

    render(
      <ProcessingPage
        videoId="ts/user@example.com/lecture.mp4"
        userId="user@example.com"
        onProcessingComplete={vi.fn()}
        onCancel={onCancel}
      />,
    )

    vi.setSystemTime(startTime + 20 * 60 * 1000 + 1)
    await act(async () => {
      vi.advanceTimersByTime(8_001)
      await Promise.resolve()
    })

    // Use fireEvent instead of userEvent to avoid fake-timer interactions
    screen.getByRole('button', { name: 'Go to dashboard' }).click()
    expect(onCancel).toHaveBeenCalled()
  })
})

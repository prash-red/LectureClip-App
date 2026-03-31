import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { chatVideo, queryVideo } from '@/lib/api.ts'
import { PlayerPage } from '@/pages/PlayerPage.tsx'

const pauseSpy = vi.fn()

vi.mock('@/lib/api.ts', () => ({
  queryVideo: vi.fn(),
  chatVideo: vi.fn(),
}))

vi.mock('@/components/VideoPlayer.tsx', async () => {
  const React = await import('react')

  return {
    VideoPlayer: React.forwardRef(function MockVideoPlayer(
      props: {
        src: string
        segments: { start: number; end: number }[]
        onPlaybackTimeUpdate?: (seconds: number) => void
      },
      ref: React.ForwardedRef<{ pause: () => void }>,
    ) {
      React.useImperativeHandle(ref, () => ({
        pause: pauseSpy,
      }))

      return (
        <div>
          <p>{props.src}</p>
          <p>Segment count: {props.segments.length}</p>
          <button type="button" onClick={() => props.onPlaybackTimeUpdate?.(47)}>
            Advance playback
          </button>
        </div>
      )
    }),
  }
})

describe('PlayerPage', () => {
  it('renders transcript text from segment text field and highlights the active entry', async () => {
    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })
    render(
      <PlayerPage
        videoId="vid_player"
        file={file}
        segments={[
          { segmentId: 'seg-1', start: 12, end: 28, idx: 0, text: 'Intro section', similarity: 0.9 },
          { segmentId: 'seg-2', start: 46, end: 58, idx: 1, text: 'Backpropagation section', similarity: 0.85 },
        ]}
        onQueryComplete={vi.fn()}
        onBackToUpload={vi.fn()}
      />,
    )

    expect(screen.getByText('Intro section')).toBeInTheDocument()
    expect(screen.getByText('Backpropagation section')).toBeInTheDocument()
    expect(URL.createObjectURL).toHaveBeenCalledWith(file)
  })

  it('submits a trimmed follow-up query and can pause the player before returning to upload', async () => {
    const user = userEvent.setup()
    const onQueryComplete = vi.fn()
    const onBackToUpload = vi.fn()
    const nextSegments = [
      { segmentId: 'seg-3', start: 88, end: 102, idx: 2, text: 'Gradient descent', similarity: 0.92 },
    ]

    vi.mocked(queryVideo).mockResolvedValue({ segments: nextSegments })

    render(
      <PlayerPage
        videoId="vid_player"
        file={new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })}
        segments={[{ segmentId: 'seg-1', start: 12, end: 28, idx: 0, text: 'Intro section', similarity: 0.9 }]}
        onQueryComplete={onQueryComplete}
        onBackToUpload={onBackToUpload}
      />,
    )

    await user.type(screen.getByPlaceholderText('Try a different query…'), '  gradient descent  ')
    await user.keyboard('{Enter}')

    await waitFor(() => {
      expect(queryVideo).toHaveBeenCalledWith('vid_player', 'gradient descent')
    })

    expect(onQueryComplete).toHaveBeenCalledWith(nextSegments)
  })

  it('uses the videoUrl prop when no file is provided', () => {
    render(
      <PlayerPage
        videoId="vid_player"
        file={null}
        videoUrl="https://cdn.example.com/lecture.mp4"
        segments={[{ segmentId: 'seg-1', start: 0, end: 10, idx: 0, text: 'Intro', similarity: 0.9 }]}
        onQueryComplete={vi.fn()}
        onBackToUpload={vi.fn()}
      />,
    )
    expect(screen.getByText('https://cdn.example.com/lecture.mp4')).toBeInTheDocument()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('sends a chat message and displays the assistant reply', async () => {
    const user = userEvent.setup()
    vi.mocked(chatVideo).mockResolvedValue({
      answer: 'Backpropagation is the key algorithm.',
      sessionId: 'sess-1',
      segments: [],
    })

    render(
      <PlayerPage
        videoId="vid_player"
        file={new File(['bytes'], 'lecture.mp4', { type: 'video/mp4' })}
        segments={[{ segmentId: 'seg-1', start: 0, end: 10, idx: 0, text: 'Intro', similarity: 0.9 }]}
        onQueryComplete={vi.fn()}
        onBackToUpload={vi.fn()}
      />,
    )

    const chatInput = screen.getByPlaceholderText('Ask about this lecture…')
    await user.type(chatInput, 'What is backpropagation?')
    await user.keyboard('{Enter}')

    expect(await screen.findByText('Backpropagation is the key algorithm.')).toBeInTheDocument()
    expect(chatVideo).toHaveBeenCalledWith('vid_player', 'What is backpropagation?', undefined)
  })

  it('shows an error message when the chat request fails', async () => {
    const user = userEvent.setup()
    vi.mocked(chatVideo).mockRejectedValue(new Error('Network error'))

    render(
      <PlayerPage
        videoId="vid_player"
        file={new File(['bytes'], 'lecture.mp4', { type: 'video/mp4' })}
        segments={[{ segmentId: 'seg-1', start: 0, end: 10, idx: 0, text: 'Intro', similarity: 0.9 }]}
        onQueryComplete={vi.fn()}
        onBackToUpload={vi.fn()}
      />,
    )

    await user.type(screen.getByPlaceholderText('Ask about this lecture…'), 'bad query')
    await user.keyboard('{Enter}')

    expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument()
  })
})

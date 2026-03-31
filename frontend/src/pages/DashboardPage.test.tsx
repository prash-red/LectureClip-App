import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { listVideos } from '@/lib/api.ts'
import { DashboardPage } from '@/pages/DashboardPage.tsx'
import type { Video } from '@/lib/types.ts'

vi.mock('@/lib/api.ts', () => ({
  listVideos: vi.fn(),
}))

const mockVideos: Video[] = [
  {
    lectureId: 'lec-1',
    videoId: 's3://bucket/2024/user/lecture1.mp4',
    title: 'Introduction to ML',
    ingestedAt: '2024-01-15T10:00:00Z',
    playbackUrl: 'https://example.com/vid1.mp4',
  },
  {
    lectureId: 'lec-2',
    videoId: 's3://bucket/2024/user/lecture2.mp4',
    title: 'Deep Learning Basics',
    ingestedAt: '2024-02-20T14:30:00Z',
    playbackUrl: null,
  },
]

describe('DashboardPage', () => {
  it('shows loading skeleton cards while fetching', () => {
    vi.mocked(listVideos).mockImplementation(() => new Promise(() => {}))
    render(<DashboardPage userId="user@example.com" onSelectVideo={vi.fn()} onUploadNew={vi.fn()} />)
    expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('renders video cards after a successful fetch', async () => {
    vi.mocked(listVideos).mockResolvedValue({ videos: mockVideos })
    render(<DashboardPage userId="user@example.com" onSelectVideo={vi.fn()} onUploadNew={vi.fn()} />)
    expect(await screen.findByText('Introduction to ML')).toBeInTheDocument()
    expect(screen.getByText('Deep Learning Basics')).toBeInTheDocument()
  })

  it('shows empty state when the library has no videos', async () => {
    vi.mocked(listVideos).mockResolvedValue({ videos: [] })
    render(<DashboardPage userId="user@example.com" onSelectVideo={vi.fn()} onUploadNew={vi.fn()} />)
    expect(await screen.findByText('No lectures yet')).toBeInTheDocument()
  })

  it('shows an error message when the fetch fails', async () => {
    vi.mocked(listVideos).mockRejectedValue(new Error('Network error'))
    render(<DashboardPage userId="user@example.com" onSelectVideo={vi.fn()} onUploadNew={vi.fn()} />)
    expect(await screen.findByText('Failed to load your videos.')).toBeInTheDocument()
  })

  it('calls onSelectVideo with the clicked video', async () => {
    const user = userEvent.setup()
    const onSelectVideo = vi.fn()
    vi.mocked(listVideos).mockResolvedValue({ videos: mockVideos })
    render(<DashboardPage userId="user@example.com" onSelectVideo={onSelectVideo} onUploadNew={vi.fn()} />)
    await user.click(await screen.findByText('Introduction to ML'))
    expect(onSelectVideo).toHaveBeenCalledWith(mockVideos[0])
  })

  it('calls onUploadNew when the Upload video button is clicked', async () => {
    const user = userEvent.setup()
    const onUploadNew = vi.fn()
    vi.mocked(listVideos).mockResolvedValue({ videos: [] })
    render(<DashboardPage userId="user@example.com" onSelectVideo={vi.fn()} onUploadNew={onUploadNew} />)
    await user.click(await screen.findByRole('button', { name: /Upload video/i }))
    expect(onUploadNew).toHaveBeenCalled()
  })

  it('calls onUploadNew from the empty-state Upload button', async () => {
    const user = userEvent.setup()
    const onUploadNew = vi.fn()
    vi.mocked(listVideos).mockResolvedValue({ videos: [] })
    render(<DashboardPage userId="user@example.com" onSelectVideo={vi.fn()} onUploadNew={onUploadNew} />)
    await user.click(await screen.findByRole('button', { name: 'Upload a video' }))
    expect(onUploadNew).toHaveBeenCalled()
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { chatVideo, getTranscript, listVideos, queryVideo, registerUser, uploadVideo } from '@/lib/api.ts'

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('uploadVideo', () => {
  it('returns the fileKey as videoId on a successful direct upload', async () => {
    // Small file → directUpload path (POST /upload then PUT to S3)
    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })

    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ uploadUrl: 'https://s3.example.com/presigned', fileKey: 'vid_123' }),
        { status: 200 },
      ))
      .mockResolvedValueOnce(new Response(null, { status: 200 })),
    )

    const result = await uploadVideo(file, 'anonymous')
    expect(result).toEqual({ videoId: 'vid_123' })
  })

  it('throws when the upload init request fails', async () => {
    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(null, { status: 500 }),
    ))

    await expect(uploadVideo(file, 'anonymous')).rejects.toThrow('Upload init failed: 500')
  })
})

describe('queryVideo', () => {
  it('returns segments from the API response', async () => {
    const segments = [
      { start: 12, end: 28 },
      { start: 46, end: 64 },
      { start: 88, end: 102 },
    ]

    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ segments }), { status: 200 }),
    ))

    const result = await queryVideo('vid_123', 'neural networks')
    expect(result).toEqual({ segments })
  })

  it('throws when the query request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(null, { status: 400 }),
    ))

    await expect(queryVideo('vid_123', 'neural networks')).rejects.toThrow('Query failed: 400')
  })
})

describe('uploadVideo — validation', () => {
  it('throws when the file is empty', async () => {
    const file = new File([], 'empty.mp4', { type: 'video/mp4' })
    await expect(uploadVideo(file, 'user')).rejects.toThrow('File is empty')
  })

  it('throws when the file exceeds 5 GB', async () => {
    const file = new File(['x'], 'big.mp4', { type: 'video/mp4' })
    Object.defineProperty(file, 'size', { value: 5 * 1024 * 1024 * 1024 + 1 })
    await expect(uploadVideo(file, 'user')).rejects.toThrow('File exceeds maximum size of 5 GB')
  })

  it('throws for unsupported file formats', async () => {
    const file = new File(['x'], 'lecture.avi', { type: 'video/avi' })
    await expect(uploadVideo(file, 'user')).rejects.toThrow("File format 'avi' is not allowed")
  })
})

describe('uploadVideo — multipart path', () => {
  it('uses multipart upload for files larger than 10 MB and returns the fileKey', async () => {
    const largeContent = new Uint8Array(11 * 1024 * 1024)
    const file = new File([largeContent], 'big.mp4', { type: 'video/mp4' })

    vi.stubGlobal('fetch', vi.fn()
      // POST /multipart/init
      .mockResolvedValueOnce(new Response(
        JSON.stringify({
          uploadId: 'upload-123',
          fileKey: 'ts/user/big.mp4',
          partSize: 11 * 1024 * 1024,
          presignedUrls: [{ partNumber: 1, uploadUrl: 'https://s3.example.com/part1' }],
        }),
        { status: 200, headers: { ETag: '"etag-1"' } },
      ))
      // PUT part 1
      .mockResolvedValueOnce(new Response(null, {
        status: 200,
        headers: { ETag: '"etag-1"' },
      }))
      // POST /multipart/complete
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ fileKey: 'ts/user/big.mp4' }),
        { status: 200 },
      )),
    )

    const result = await uploadVideo(file, 'user')
    expect(result).toEqual({ videoId: 'ts/user/big.mp4' })
  })

  it('throws when multipart init fails', async () => {
    const largeContent = new Uint8Array(11 * 1024 * 1024)
    const file = new File([largeContent], 'big.mp4', { type: 'video/mp4' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(null, { status: 500 })))
    await expect(uploadVideo(file, 'user')).rejects.toThrow('Multipart init failed: 500')
  })
})

describe('listVideos', () => {
  it('returns the lectures array from the API response', async () => {
    const lectures = [
      { lectureId: 'lec-1', videoId: 's3://b/v.mp4', title: 'Lecture', ingestedAt: '2024-01-01T00:00:00Z', playbackUrl: null },
    ]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ lectures }), { status: 200 }),
    ))
    const result = await listVideos('user@example.com')
    expect(result.videos).toEqual(lectures)
  })

  it('encodes the userId in the query string', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ lectures: [] }), { status: 200 }),
    )
    vi.stubGlobal('fetch', mockFetch)
    await listVideos('user+test@example.com')
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('userId=user%2Btest%40example.com'))
  })

  it('throws when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(null, { status: 403 })))
    await expect(listVideos('user@example.com')).rejects.toThrow('Failed to load videos: 403')
  })
})

describe('registerUser', () => {
  it('resolves on a 200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(null, { status: 200 })))
    await expect(registerUser('user@example.com')).resolves.toBeUndefined()
  })

  it('throws on a non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(null, { status: 409 })))
    await expect(registerUser('user@example.com')).rejects.toThrow('Failed to register user: 409')
  })
})

describe('chatVideo', () => {
  it('returns answer, sessionId, and segments', async () => {
    const body = { answer: 'Neural networks learn...', sessionId: 'sess-1', segments: [] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify(body), { status: 200 }),
    ))
    const result = await chatVideo('vid-1', 'What is a neural network?', 'sess-0')
    expect(result).toEqual(body)
  })

  it('throws on a non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(null, { status: 500 })))
    await expect(chatVideo('vid-1', 'query')).rejects.toThrow('Chat failed: 500')
  })
})

describe('getTranscript', () => {
  it('returns the mock transcript', async () => {
    vi.useFakeTimers()

    const transcriptPromise = getTranscript('vid_123')
    await vi.runAllTimersAsync()

    await expect(transcriptPromise).resolves.toMatchObject({
      transcript: expect.arrayContaining([
        expect.objectContaining({ start: 10, end: 21, speaker: 'Speaker' }),
      ]),
    })
  })
})
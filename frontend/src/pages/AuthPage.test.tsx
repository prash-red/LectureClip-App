import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { confirmSignUp, signIn, signUp } from '@/lib/auth.ts'
import { registerUser } from '@/lib/api.ts'
import { AuthPage } from '@/pages/AuthPage.tsx'

vi.mock('@/lib/auth.ts', () => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
}))

vi.mock('@/lib/api.ts', () => ({
  registerUser: vi.fn().mockResolvedValue(undefined),
}))

const fakeSession = { email: 'user@example.com', idToken: 'mock-jwt' }

describe('AuthPage — sign in', () => {
  it('renders the sign in form by default', () => {
    render(<AuthPage onSignIn={vi.fn()} />)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('calls onSignIn with the session after a successful sign in', async () => {
    const user = userEvent.setup()
    const onSignIn = vi.fn()
    vi.mocked(signIn).mockResolvedValue(fakeSession)
    vi.mocked(registerUser).mockResolvedValue(undefined)

    render(<AuthPage onSignIn={onSignIn} />)

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(onSignIn).toHaveBeenCalledWith(fakeSession))
  })

  it('shows an error message when sign in fails', async () => {
    const user = userEvent.setup()
    vi.mocked(signIn).mockRejectedValue(new Error('Incorrect username or password'))

    render(<AuthPage onSignIn={vi.fn()} />)

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Incorrect username or password')).toBeInTheDocument()
  })

  it('shows "Signing in…" while the request is in flight', async () => {
    const user = userEvent.setup()
    let resolve: (value: typeof fakeSession) => void
    vi.mocked(signIn).mockImplementation(() => new Promise((r) => { resolve = r }))

    render(<AuthPage onSignIn={vi.fn()} />)

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Password'), 'password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled()

    resolve!(fakeSession)
  })
})

describe('AuthPage — sign up', () => {
  it('renders the sign up form after switching tabs', async () => {
    const user = userEvent.setup()
    render(<AuthPage onSignIn={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: 'Create account' }))
    expect(screen.getByRole('button', { name: 'Create account' })).toBeInTheDocument()
  })

  it('transitions to the verify view after a successful sign up', async () => {
    const user = userEvent.setup()
    vi.mocked(signUp).mockResolvedValue(undefined)

    render(<AuthPage onSignIn={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: 'Create account' }))

    await user.type(screen.getAllByLabelText('Email')[0], 'user@example.com')
    await user.type(screen.getAllByLabelText('Password')[0], 'password123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Check your email')).toBeInTheDocument()
    expect(screen.getByLabelText('Verification code')).toBeInTheDocument()
  })

  it('shows an error message when sign up fails', async () => {
    const user = userEvent.setup()
    vi.mocked(signUp).mockRejectedValue(new Error('Email already in use'))

    render(<AuthPage onSignIn={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: 'Create account' }))

    await user.type(screen.getAllByLabelText('Email')[0], 'taken@example.com')
    await user.type(screen.getAllByLabelText('Password')[0], 'password123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Email already in use')).toBeInTheDocument()
  })
})

describe('AuthPage — verify', () => {
  async function navigateToVerify(user: ReturnType<typeof userEvent.setup>) {
    vi.mocked(signUp).mockResolvedValue(undefined)
    render(<AuthPage onSignIn={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: 'Create account' }))
    await user.type(screen.getAllByLabelText('Email')[0], 'user@example.com')
    await user.type(screen.getAllByLabelText('Password')[0], 'password123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    await screen.findByText('Check your email')
  }

  it('returns to the sign in view after successful verification', async () => {
    const user = userEvent.setup()
    vi.mocked(confirmSignUp).mockResolvedValue(undefined)

    await navigateToVerify(user)

    await user.type(screen.getByLabelText('Verification code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify email' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument(),
    )
  })

  it('shows an error when the verification code is wrong', async () => {
    const user = userEvent.setup()
    vi.mocked(confirmSignUp).mockRejectedValue(new Error('Invalid verification code'))

    await navigateToVerify(user)

    await user.type(screen.getByLabelText('Verification code'), 'bad')
    await user.click(screen.getByRole('button', { name: 'Verify email' }))

    expect(await screen.findByText('Invalid verification code')).toBeInTheDocument()
  })

  it('navigates back to sign in when the Back button is clicked', async () => {
    const user = userEvent.setup()
    await navigateToVerify(user)
    await user.click(screen.getByRole('button', { name: 'Back to sign in' }))
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })
})

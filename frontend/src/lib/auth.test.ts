import { describe, expect, it, vi } from 'vitest'
import { confirmSignUp, getSession, signIn, signOut, signUp } from '@/lib/auth.ts'

// Shared mock instances — hoisted so the vi.mock factory can reference them
const mockCognitoUser = vi.hoisted(() => ({
  authenticateUser: vi.fn(),
  confirmRegistration: vi.fn(),
  getSession: vi.fn(),
  getUsername: vi.fn().mockReturnValue('user@example.com'),
}))

const mockUserPool = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  signUp: vi.fn(),
}))

vi.mock('amazon-cognito-identity-js', () => ({
  // eslint-disable-next-line prefer-arrow-callback
  CognitoUserPool: vi.fn(function () { return mockUserPool }),
  // eslint-disable-next-line prefer-arrow-callback
  CognitoUser: vi.fn(function () { return mockCognitoUser }),
  CognitoUserAttribute: vi.fn(),
  AuthenticationDetails: vi.fn(),
}))

const fakeSession = {
  isValid: () => true,
  getIdToken: () => ({ getJwtToken: () => 'mock-jwt' }),
}

describe('signIn', () => {
  it('resolves with email and idToken on success', async () => {
    mockCognitoUser.authenticateUser.mockImplementation(
      (_: unknown, { onSuccess }: { onSuccess: (s: typeof fakeSession) => void }) => {
        onSuccess(fakeSession)
      },
    )
    await expect(signIn('user@example.com', 'pass')).resolves.toEqual({
      email: 'user@example.com',
      idToken: 'mock-jwt',
    })
  })

  it('rejects on authentication failure', async () => {
    const error = new Error('Incorrect username or password')
    mockCognitoUser.authenticateUser.mockImplementation(
      (_: unknown, { onFailure }: { onFailure: (e: Error) => void }) => {
        onFailure(error)
      },
    )
    await expect(signIn('user@example.com', 'wrong')).rejects.toThrow('Incorrect username or password')
  })
})

describe('signUp', () => {
  it('resolves on successful registration', async () => {
    mockUserPool.signUp.mockImplementation(
      (...args: unknown[]) => {
        ;(args[args.length - 1] as (err: null) => void)(null)
      },
    )
    await expect(signUp('user@example.com', 'password')).resolves.toBeUndefined()
  })

  it('rejects when registration fails', async () => {
    const error = new Error('Email already exists')
    mockUserPool.signUp.mockImplementation(
      (...args: unknown[]) => {
        ;(args[args.length - 1] as (err: Error) => void)(error)
      },
    )
    await expect(signUp('user@example.com', 'password')).rejects.toThrow('Email already exists')
  })
})

describe('confirmSignUp', () => {
  it('resolves when confirmation succeeds', async () => {
    mockCognitoUser.confirmRegistration.mockImplementation(
      (_code: string, _force: boolean, cb: (err: null) => void) => cb(null),
    )
    await expect(confirmSignUp('user@example.com', '123456')).resolves.toBeUndefined()
  })

  it('rejects on invalid code', async () => {
    const error = new Error('Invalid verification code')
    mockCognitoUser.confirmRegistration.mockImplementation(
      (_code: string, _force: boolean, cb: (err: Error) => void) => cb(error),
    )
    await expect(confirmSignUp('user@example.com', 'bad')).rejects.toThrow('Invalid verification code')
  })
})

describe('signOut', () => {
  it('signs out the current user when one exists', () => {
    const userSignOut = vi.fn()
    mockUserPool.getCurrentUser.mockReturnValue({ signOut: userSignOut })
    signOut()
    expect(userSignOut).toHaveBeenCalled()
  })

  it('does nothing when there is no current user', () => {
    mockUserPool.getCurrentUser.mockReturnValue(null)
    expect(() => signOut()).not.toThrow()
  })
})

describe('getSession', () => {
  it('resolves with session data when valid session exists', async () => {
    mockUserPool.getCurrentUser.mockReturnValue({
      getUsername: () => 'user@example.com',
      getSession: (cb: (err: null, s: typeof fakeSession) => void) => cb(null, fakeSession),
    })
    await expect(getSession()).resolves.toEqual({ email: 'user@example.com', idToken: 'mock-jwt' })
  })

  it('resolves with null when no current user', async () => {
    mockUserPool.getCurrentUser.mockReturnValue(null)
    await expect(getSession()).resolves.toBeNull()
  })

  it('resolves with null when session is invalid', async () => {
    mockUserPool.getCurrentUser.mockReturnValue({
      getUsername: () => 'user@example.com',
      getSession: (cb: (err: null, s: { isValid: () => boolean; getIdToken: () => { getJwtToken: () => string } }) => void) =>
        cb(null, { isValid: () => false, getIdToken: () => ({ getJwtToken: () => '' }) }),
    })
    await expect(getSession()).resolves.toBeNull()
  })

  it('resolves with null when getSession returns an error', async () => {
    mockUserPool.getCurrentUser.mockReturnValue({
      getUsername: () => 'user@example.com',
      getSession: (cb: (err: Error, s: null) => void) => cb(new Error('Session expired'), null),
    })
    await expect(getSession()).resolves.toBeNull()
  })
})

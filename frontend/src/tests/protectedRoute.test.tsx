import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from '../components/auth/ProtectedRoute'
import { useAuth } from '../state/AuthProvider'

vi.mock('../state/AuthProvider', () => ({
  useAuth: vi.fn(),
}))

function LoginLocationProbe() {
  const location = useLocation()
  return (
    <span data-testid="return-location">
      {(location.state as { from?: string } | null)?.from}
    </span>
  )
}

describe('protected route return location', () => {
  it('preserves path, query, and hash through login redirection', () => {
    vi.mocked(useAuth).mockReturnValue({
      status: 'unauthenticated',
      bootstrapRequired: false,
    } as ReturnType<typeof useAuth>)

    render(
      <MemoryRouter
        initialEntries={[
          '/apartments/12345?sourceId=source-1&runId=run-2#listing-listing-9',
        ]}
      >
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/apartments/:complexId" element={<span>private</span>} />
          </Route>
          <Route path="/login" element={<LoginLocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId('return-location')).toHaveTextContent(
      '/apartments/12345?sourceId=source-1&runId=run-2#listing-listing-9',
    )
  })
})

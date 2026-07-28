import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { UrlAnalysisPanel } from '../components/analysis/UrlAnalysisPanel'

describe('Chrome 화면 탐색 지연 프리셋', () => {
  it('기본 프리셋으로 시작하고 선택한 빠름 값을 분석 요청에 전달한다', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()

    render(
      <UrlAnalysisPanel
        status="idle"
        progress={0}
        error=""
        onStart={onStart}
      />,
    )

    expect(
      screen.getByRole('radio', { name: /기본.*1~2.5초/ }),
    ).toBeChecked()
    expect(screen.getByLabelText('네이버 부동산 URL')).toHaveValue('')
    expect(screen.getByRole('button', { name: '분석 시작' })).toBeDisabled()

    await user.type(
      screen.getByLabelText('네이버 부동산 URL'),
      'https://fin.land.naver.com/map?demo=true',
    )
    await user.click(
      screen.getByRole('radio', { name: /빠름.*0.7~1.2초/ }),
    )
    await user.click(screen.getByRole('button', { name: '분석 시작' }))

    expect(onStart).toHaveBeenCalledWith(
      expect.objectContaining({ interactionDelayPreset: 'fast' }),
    )
  })

  it('매우 빠름 선택 시 접근 제한 위험을 안내한다', async () => {
    const user = userEvent.setup()

    render(
      <UrlAnalysisPanel
        status="idle"
        progress={0}
        error=""
        onStart={vi.fn()}
      />,
    )

    await user.click(
      screen.getByRole('radio', { name: /매우 빠름.*0.5초/ }),
    )

    expect(
      screen.getByText('접근 제한 가능성이 높아질 수 있습니다.'),
    ).toBeInTheDocument()
  })

  it('분석 실행 중에는 모든 지연 프리셋을 변경할 수 없다', () => {
    render(
      <UrlAnalysisPanel
        status="running"
        progress={35}
        error=""
        onStart={vi.fn()}
      />,
    )

    const options = screen.getAllByRole('radio')
    expect(options).toHaveLength(5)
    options.forEach((option) => expect(option).toBeDisabled())
  })
})

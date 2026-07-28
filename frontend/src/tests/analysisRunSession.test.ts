import { beforeEach, describe, expect, it } from 'vitest'
import {
  ACTIVE_ANALYSIS_SESSION_KEY,
  clearActiveAnalysisSession,
  readActiveAnalysisSession,
  writeActiveAnalysisSession,
} from '../state/analysisRunSession'

const RUN_ID = '7f43e80d-4d5f-4d68-b41b-0ed4e260cae4'

describe('활성 분석 sessionStorage 계약', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('버전이 붙은 UUID run ID만 저장하고 복원한다', () => {
    writeActiveAnalysisSession(RUN_ID)

    expect(window.sessionStorage).toHaveLength(1)
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBe(
      `{"version":1,"runId":"${RUN_ID}"}`,
    )
    expect(readActiveAnalysisSession()).toEqual({ version: 1, runId: RUN_ID })
  })

  it.each([
    ['손상된 JSON', '{'],
    ['지원하지 않는 버전', `{"version":2,"runId":"${RUN_ID}"}`],
    ['UUID가 아닌 run ID', '{"version":1,"runId":"queued-run"}'],
    ['추가 필드가 있는 값', `{"version":1,"runId":"${RUN_ID}","sourceUrl":"https://example.com"}`],
  ])('%s을 복원하지 않고 저장값을 정리한다', (_label, storedValue) => {
    window.sessionStorage.setItem(ACTIVE_ANALYSIS_SESSION_KEY, storedValue)

    expect(readActiveAnalysisSession()).toBeNull()
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBeNull()
  })

  it('유효하지 않은 run ID는 저장하지 않는다', () => {
    writeActiveAnalysisSession('not-a-uuid')

    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBeNull()
  })

  it('storage 접근 예외가 발생해도 읽기·쓰기·삭제가 앱을 중단시키지 않는다', () => {
    const unavailableStorage = {
      getItem() {
        throw new DOMException('denied')
      },
      setItem() {
        throw new DOMException('denied')
      },
      removeItem() {
        throw new DOMException('denied')
      },
    } as unknown as Storage

    expect(readActiveAnalysisSession(unavailableStorage)).toBeNull()
    expect(() => writeActiveAnalysisSession(RUN_ID, unavailableStorage)).not.toThrow()
    expect(() => clearActiveAnalysisSession(unavailableStorage)).not.toThrow()
  })
})

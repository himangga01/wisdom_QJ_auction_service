const RUN_ERROR_MESSAGES: Record<string, string> = {
  browser_unavailable:
    '수집용 Chrome에 연결할 수 없습니다. 실행 상태를 확인한 뒤 다시 시도해 주세요.',
  browser_disconnected:
    '조사 중 Chrome 연결이 끊겼습니다. Chrome이 준비되면 분석을 다시 시작해 주세요.',
  access_blocked: '네이버에서 접근을 제한해 조사를 중단했습니다.',
  login_required: 'Chrome에서 로그인이 필요한 상태입니다.',
  captcha_detected: '추가 사용자 확인이 필요해 조사를 중단했습니다.',
}

export function runErrorMessage(errorCode: string | null | undefined): string | null {
  if (!errorCode) return null
  return RUN_ERROR_MESSAGES[errorCode] ?? null
}

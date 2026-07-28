export interface ActiveAnalysisSessionV1 {
  version: 1
  runId: string
}

export const ACTIVE_ANALYSIS_SESSION_KEY =
  'wisdom-qj-auction.active-analysis-run.v1'

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function resolveStorage(storage?: Storage): Storage | null {
  if (storage) return storage
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage
  } catch {
    return null
  }
}

function isActiveAnalysisSessionV1(
  value: unknown,
): value is ActiveAnalysisSessionV1 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const record = value as Record<string, unknown>
  return (
    Object.keys(record).length === 2
    && record.version === 1
    && typeof record.runId === 'string'
    && UUID_PATTERN.test(record.runId)
  )
}

export function clearActiveAnalysisSession(storage?: Storage): void {
  try {
    resolveStorage(storage)?.removeItem(ACTIVE_ANALYSIS_SESSION_KEY)
  } catch {
    // Storage can be unavailable in private browsing or restricted webviews.
  }
}

export function readActiveAnalysisSession(
  storage?: Storage,
): ActiveAnalysisSessionV1 | null {
  const target = resolveStorage(storage)
  if (!target) return null

  try {
    const storedValue = target.getItem(ACTIVE_ANALYSIS_SESSION_KEY)
    if (storedValue === null) return null
    const parsed: unknown = JSON.parse(storedValue)
    if (isActiveAnalysisSessionV1(parsed)) return parsed
    clearActiveAnalysisSession(target)
  } catch {
    clearActiveAnalysisSession(target)
  }
  return null
}

export function writeActiveAnalysisSession(
  runId: string,
  storage?: Storage,
): void {
  const target = resolveStorage(storage)
  if (!target) return
  if (!UUID_PATTERN.test(runId)) {
    clearActiveAnalysisSession(target)
    return
  }

  try {
    target.setItem(
      ACTIVE_ANALYSIS_SESSION_KEY,
      JSON.stringify({ version: 1, runId } satisfies ActiveAnalysisSessionV1),
    )
  } catch {
    // The server remains authoritative even when browser storage is unavailable.
  }
}

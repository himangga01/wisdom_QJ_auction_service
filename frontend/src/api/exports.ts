import { apiFile, saveApiFile } from './client'

export async function downloadSourceExport(
  sourceId: string,
  range: { from?: string; to?: string } = {},
): Promise<void> {
  const file = await apiFile(`/exports/${encodeURIComponent(sourceId)}.xlsx`, range)
  saveApiFile(file)
}

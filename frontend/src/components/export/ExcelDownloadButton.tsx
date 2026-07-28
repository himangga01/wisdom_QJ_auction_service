import { Download, FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { downloadSourceExport } from '../../api/exports'
import { useAnalysis } from '../../state/AnalysisProvider'
import type { DashboardDataset } from '../../types/realEstate'
import { downloadDashboardWorkbook } from '../../utils/exportWorkbook'

interface ExcelDownloadButtonProps {
  dataset?: DashboardDataset
  sourceId?: string
  from?: string
  to?: string
}

export function ExcelDownloadButton({ dataset, sourceId, from, to }: ExcelDownloadButtonProps) {
  const analysis = useAnalysis()
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const resolvedSourceId = sourceId ?? analysis.selectedApartment?.sourceId

  const handleDownload = async () => {
    setError('')
    setDownloading(true)
    try {
      if (analysis.isDemo) {
        if (!dataset) throw new Error('데모 내보내기 데이터가 없습니다.')
        downloadDashboardWorkbook(dataset)
      } else {
        if (!resolvedSourceId) throw new Error('내보낼 조사 원본을 선택해 주세요.')
        await downloadSourceExport(resolvedSourceId, { from, to })
      }
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : 'Excel 파일을 내려받지 못했습니다.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => void handleDownload()}
        disabled={downloading || (!analysis.isDemo && !resolvedSourceId)}
        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-sm font-extrabold text-white shadow-sm shadow-emerald-200 transition hover:bg-emerald-700 focus:outline-none focus:ring-4 focus:ring-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-400 disabled:shadow-none"
      >
        <FileSpreadsheet size={17} /> {downloading ? '파일 생성 중...' : 'Excel 다운로드'} <Download size={15} />
      </button>
      {error ? <p role="alert" className="mt-2 max-w-xs text-xs font-bold text-rose-600">{error}</p> : null}
    </div>
  )
}

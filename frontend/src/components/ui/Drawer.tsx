import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface DrawerProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}

export function Drawer({ open, title, onClose, children }: DrawerProps) {
  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-50" role="presentation">
      <button className="absolute inset-0 bg-slate-950/45 backdrop-blur-[2px]" type="button" onClick={onClose} aria-label="상세 패널 닫기" />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        className="absolute inset-y-0 right-0 flex w-full max-w-[720px] flex-col bg-[#f7f8fa] shadow-[-20px_0_70px_rgba(15,23,42,0.22)]"
      >
        <header className="flex h-18 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-5 sm:px-7">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold text-emerald-700">아파트 상세 분석</p>
            <h2 id="drawer-title" className="truncate text-lg font-black tracking-tight text-slate-950">{title}</h2>
          </div>
          <button type="button" onClick={onClose} className="grid size-10 place-items-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-100" aria-label="닫기">
            <X size={20} />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-7">{children}</div>
      </section>
    </div>,
    document.body,
  )
}

import { Outlet } from 'react-router-dom'
import { PortalHeader } from './PortalHeader'
import { RuntimeModeStatus } from './RuntimeModeStatus'

export function PortalShell() {
  return (
    <div className="min-h-screen bg-[#f5f7f8] text-slate-950">
      <PortalHeader />
      <main className="mx-auto min-h-[calc(100vh-162px)] w-full max-w-[1440px] px-5 py-8 lg:px-8 lg:py-10">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white py-7 text-center text-xs text-slate-400">
        <RuntimeModeStatus variant="footer" />
      </footer>
    </div>
  )
}

import { createContext, useContext, type ReactNode } from 'react'
import { useDemoDashboard } from './useDemoDashboard'

type DemoAnalysisState = ReturnType<typeof useDemoDashboard>

const DemoAnalysisContext = createContext<DemoAnalysisState | null>(null)

export function DemoAnalysisProvider({ children }: { children: ReactNode }) {
  const state = useDemoDashboard()
  return <DemoAnalysisContext.Provider value={state}>{children}</DemoAnalysisContext.Provider>
}

export function useDemoAnalysis(): DemoAnalysisState {
  const context = useContext(DemoAnalysisContext)
  if (!context) throw new Error('useDemoAnalysis must be used inside DemoAnalysisProvider')
  return context
}

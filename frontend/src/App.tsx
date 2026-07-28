import { RouterProvider } from 'react-router-dom'
import { router } from './app/router'
import { AnalysisProvider } from './state/AnalysisProvider'
import { AuthProvider, useAuth } from './state/AuthProvider'
import { DemoAnalysisProvider } from './state/DemoAnalysisContext'

function SessionRouter() {
  const auth = useAuth()
  if (auth.status !== 'authenticated') return <RouterProvider router={router} />
  return (
    <AnalysisProvider>
      <RouterProvider router={router} />
    </AnalysisProvider>
  )
}

function App() {
  return (
    <DemoAnalysisProvider>
      <AuthProvider>
        <SessionRouter />
      </AuthProvider>
    </DemoAnalysisProvider>
  )
}

export default App

import { RouterProvider } from 'react-router-dom'
import { router } from './app/router'
import { AnalysisProvider } from './state/AnalysisProvider'
import { DemoAnalysisProvider } from './state/DemoAnalysisContext'

function App() {
  return (
    <DemoAnalysisProvider>
      <AnalysisProvider>
        <RouterProvider router={router} />
      </AnalysisProvider>
    </DemoAnalysisProvider>
  )
}

export default App

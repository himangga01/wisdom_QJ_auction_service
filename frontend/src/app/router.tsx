import { createBrowserRouter } from 'react-router-dom'
import { PortalShell } from '../components/layout/PortalShell'
import { AnalysisPage } from '../pages/AnalysisPage'
import { ApartmentDetailPage } from '../pages/ApartmentDetailPage'
import { ApartmentsPage } from '../pages/ApartmentsPage'
import { DashboardPage } from '../pages/DashboardPage'
import { ListingDetailPage } from '../pages/ListingDetailPage'
import { SchedulePage } from '../pages/SchedulePage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <PortalShell />,
    children: [
      { index: true, element: <AnalysisPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'apartments', element: <ApartmentsPage /> },
      { path: 'apartments/:complexId', element: <ApartmentDetailPage /> },
      { path: 'apartments/:complexId/listings/:listingId', element: <ListingDetailPage /> },
      { path: 'schedules', element: <SchedulePage /> },
    ],
  },
])

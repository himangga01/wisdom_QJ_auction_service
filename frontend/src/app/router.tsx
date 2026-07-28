import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { PortalShell } from '../components/layout/PortalShell'
import { AnalysisPage } from '../pages/AnalysisPage'
import { ApartmentDetailPage } from '../pages/ApartmentDetailPage'
import { ApartmentsPage } from '../pages/ApartmentsPage'
import { DashboardPage } from '../pages/DashboardPage'
import { ListingDetailPage } from '../pages/ListingDetailPage'
import { SchedulePage } from '../pages/SchedulePage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { RouteErrorPage } from '../pages/RouteErrorPage'
import { ProtectedRoute } from '../components/auth/ProtectedRoute'
import { AccountPage } from '../pages/AccountPage'
import { AdminUsersPage } from '../pages/AdminUsersPage'
import { BootstrapAdminPage } from '../pages/BootstrapAdminPage'
import { LoginPage } from '../pages/LoginPage'
import { NotificationsPage } from '../pages/NotificationsPage'

export const appRoutes: RouteObject[] = [
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/bootstrap',
    element: <BootstrapAdminPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <PortalShell />,
        errorElement: <RouteErrorPage />,
        children: [
          { index: true, element: <AnalysisPage /> },
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'apartments', element: <ApartmentsPage /> },
          { path: 'apartments/:complexId', element: <ApartmentDetailPage /> },
          { path: 'apartments/:complexId/listings/:listingId', element: <ListingDetailPage /> },
          { path: 'schedules', element: <SchedulePage /> },
          { path: 'notifications', element: <NotificationsPage /> },
          { path: 'account', element: <AccountPage /> },
          {
            element: <ProtectedRoute admin />,
            children: [
              { path: 'admin/users', element: <AdminUsersPage /> },
            ],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export const router = createBrowserRouter(appRoutes)

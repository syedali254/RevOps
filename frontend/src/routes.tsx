import { Link, Route, Routes } from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { Button, EmptyState, PageHeader } from './components/ui';
import { CampaignsPage } from './pages/CampaignsPage';
import { CompaniesPage } from './pages/CompaniesPage';
import { CompanyDetailPage } from './pages/CompanyDetailPage';
import { DiscoveryRunDetailPage } from './pages/DiscoveryRunDetailPage';
import { OverviewPage } from './pages/OverviewPage';
import { RunDetailPage } from './pages/RunDetailPage';
import { RunsPage } from './pages/RunsPage';

import { ReviewQueuePage } from './pages/ReviewQueuePage';

function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState
        title="That screen does not exist"
        description="The requested page could not be found."
        action={
          <Link to="/">
            <Button variant="primary">Back to overview</Button>
          </Link>
        }
      />
    </>
  );
}

/**
 * Route table kept separate from the router so tests can render the same
 * screens inside a MemoryRouter without touching the address bar.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="campaigns" element={<CampaignsPage />} />
        <Route path="campaigns/:campaignId/companies" element={<CompaniesPage />} />
        <Route path="campaigns/:campaignId/companies/:companyId" element={<CompanyDetailPage />} />
        <Route path="review" element={<ReviewQueuePage />} />
        <Route path="review/:companyId" element={<CompanyDetailPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="runs/:runId" element={<RunDetailPage />} />
        <Route path="discovery/:runId" element={<DiscoveryRunDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

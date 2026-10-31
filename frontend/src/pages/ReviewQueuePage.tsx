import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import type { CompanyListItem } from '../lib/types';
import { useAsync } from '../hooks/useAsync';
import { formatDate, getQualificationLabel } from '../lib/format';
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  StatusPill,
  Table,
  TD,
  TH,
} from '../components/ui';

export function ReviewQueuePage() {
  const { data, loading, error, reload } = useAsync(() => api.listCompaniesNeedingReview(), []);

  return (
    <>
      <PageHeader
        title="Review Queue"
        description="Companies requiring human review. Inspect evidence, approve, reject, or request more research."
        actions={
          <Button variant="secondary" onClick={reload}>
            Refresh
          </Button>
        }
      />

      {loading ? <LoadingState label="Loading review queue…" /> : null}

      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : null}

      {!loading && !error && data && data.length === 0 ? (
        <EmptyState
          title="No reviews needed"
          description="All companies have been processed. Great work!"
        />
      ) : null}

      {!loading && !error && data && data.length > 0 ? (
        <Table caption="Companies awaiting review">
          <thead>
            <tr>
              <TH>Company</TH>
              <TH>Score</TH>
              <TH>Evidence Conf.</TH>
              <TH>Qualification</TH>
              <TH>Review Reason</TH>
              <TH>Created</TH>
              <TH align="right">Actions</TH>
            </tr>
          </thead>
          <tbody>
            {data.map((company: CompanyListItem & { review_reason?: string }) => (
              <tr key={company.id} className="hover:bg-surface-muted">
                <TD className="font-medium text-ink">{company.canonical_name}</TD>
                <TD className="tabular-nums font-mono">
                  {company.lead_fit_score !== null ? company.lead_fit_score : <span style={{ color: 'var(--color-ink-muted)' }}>—</span>}
                </TD>
                <TD className="tabular-nums font-mono">
                  {company.evidence_confidence !== null ? company.evidence_confidence : <span style={{ color: 'var(--color-ink-muted)' }}>—</span>}
                </TD>
                <TD>
                  {company.qualification_status ? (
                    <StatusPill status={company.qualification_status} label={getQualificationLabel(company.qualification_status)} />
                  ) : (
                    <span style={{ color: 'var(--color-ink-muted)' }}>—</span>
                  )}
                </TD>
                <TD className="text-sm text-ink-muted max-w-xs truncate">
                  {company.review_reason || 'No reason recorded'}
                </TD>
                <TD className="whitespace-nowrap text-xs">{formatDate(company.created_at)}</TD>
                <TD align="right">
                  <Link
                    to={`/review/${company.id}`}
                    className="text-sm font-medium text-accent-600 hover:underline mr-3"
                  >
                    Review
                  </Link>
                </TD>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : null}
    </>
  );
}
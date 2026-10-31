import { Link, useParams } from 'react-router-dom';
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

export function CompaniesPage() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const cid = campaignId ? Number(campaignId) : 0;

  const { data, loading, error, reload } = useAsync(
    () => (cid ? api.listCompanies(cid) : Promise.resolve([])),
    [cid]
  );

  return (
    <>
      <PageHeader
        title="Companies"
        description="All companies discovered or seeded for this campaign. Click a company to view evidence, scoring, and approval status."
        actions={
          <Button
            variant="secondary"
            onClick={() => window.history.back()}
          >
            ← Back
          </Button>
        }
      />

      {loading ? <LoadingState label="Loading companies…" /> : null}

      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : null}

      {!loading && !error && data && data.length === 0 ? (
        <EmptyState
          title="No companies yet"
          description="Run a discovery workflow or seed a company to populate this list."
        />
      ) : null}

      {!loading && !error && data && data.length > 0 ? (
        <Table caption={`Companies in campaign ${cid}`}>
          <thead>
            <tr>
              <TH>Name</TH>
              <TH>Domain</TH>
              <TH>Country</TH>
              <TH>Sector</TH>
              <TH>Employees</TH>
              <TH>Score</TH>
              <TH>Evidence Conf.</TH>
              <TH>Qualification</TH>
              <TH>Created</TH>
              <TH align="right">Actions</TH>
            </tr>
          </thead>
          <tbody>
            {data.map((company: CompanyListItem) => (
              <tr key={company.id} className="hover:bg-surface-muted">
                <TD className="font-medium text-ink">{company.canonical_name}</TD>
                <TD className="text-xs font-mono">
                  {company.website_domain ? (
                    <a href={company.website_domain} target="_blank" rel="noopener noreferrer">
                      {company.website_domain}
                    </a>
                  ) : (
                    <span style={{ color: 'var(--color-ink-muted)' }}>—</span>
                  )}
                </TD>
                <TD>{company.country ?? <span style={{ color: 'var(--color-ink-muted)' }}>—</span>}</TD>
                <TD className="text-xs">{company.sector ?? <span style={{ color: 'var(--color-ink-muted)' }}>—</span>}</TD>
                <TD className="tabular-nums text-xs">
                  {company.employee_min && company.employee_max
                    ? `${company.employee_min} – ${company.employee_max}`
                    : <span style={{ color: 'var(--color-ink-muted)' }}>—</span>}
                </TD>
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
                <TD className="whitespace-nowrap text-xs">{formatDate(company.created_at)}</TD>
                <TD align="right">
                  <div className="flex items-center justify-end gap-2">
                    <Link
                      to={`/campaigns/${cid}/companies/${company.id}`}
                      className="text-xs font-semibold px-2.5 py-1 rounded bg-accent-50 text-accent-700 hover:bg-accent-100 border border-accent-200 transition-colors"
                    >
                      Dossier
                    </Link>
                  </div>
                </TD>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : null}
    </>
  );
}
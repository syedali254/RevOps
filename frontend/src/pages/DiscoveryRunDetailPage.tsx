import { Link, useParams } from 'react-router-dom';

import { api } from '../lib/api';
import { useAsync } from '../hooks/useAsync';
import {
  formatDateTime,
  formatDuration,
  outcomeLabel,
  outcomeTone,
  truncate,
} from '../lib/format';
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
  Table,
  TD,
  TH,
} from '../components/ui';

interface CheckDetail {
  rule: string;
  status: string;
  detail: string;
}

function EventDetails({ details }: { details: Record<string, unknown> }) {
  const checks = details.checks as CheckDetail[] | undefined;
  const createdCompanies = details.created_companies as Array<{ id: number; name: string; domain: string | null }> | undefined;
  const duplicates = details.duplicates as Array<{ candidate_name: string; existing_company_id: number; existing_company_name: string; domain: string }> | undefined;
  const entries = Object.entries(details).filter(
    ([key, value]) =>
      key !== 'checks' &&
      key !== 'created_companies' &&
      key !== 'duplicates' &&
      (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'),
  );

  if (!checks && !createdCompanies && !duplicates && entries.length === 0) {
    return <span className="text-xs text-ink-subtle">—</span>;
  }

  return (
    <div className="space-y-1.5">
      {createdCompanies ? (
        <div className="space-y-1">
          <p className="text-xs font-medium text-ink">Companies created:</p>
          <ul className="space-y-0.5 pl-4">
            {createdCompanies.map((c) => (
              <li key={c.id} className="flex gap-2 text-xs">
                <span className="font-medium text-ink">{c.name}</span>
                {c.domain && <span className="text-ink-subtle">({c.domain})</span>}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {duplicates ? (
        <div className="space-y-1">
          <p className="text-xs font-medium text-ink">Duplicates found:</p>
          <ul className="space-y-0.5 pl-4">
            {duplicates.map((d, idx) => (
              <li key={idx} className="flex gap-2 text-xs">
                <span className="text-ink">{d.candidate_name}</span>
                <span className="text-ink-subtle">→</span>
                <span className="font-medium text-ink">{d.existing_company_name}</span>
                <span className="text-ink-subtle">(#{d.existing_company_id})</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {checks ? (
        <ul className="space-y-1">
          {checks.map((check) => (
            <li key={check.rule} className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-medium text-ink">{check.rule}</span>
              <StatusPill
                label={check.status}
                tone={
                  check.status === 'pass'
                    ? 'ok'
                    : check.status === 'fail'
                      ? 'danger'
                      : 'warn'
                }
              />
              <span className="text-ink-subtle">{check.detail}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {entries.map(([key, value]) => (
        <p key={key} className="text-xs">
          <span className="font-medium text-ink">{key.replace(/_/g, ' ')}</span>{' '}
          <span className="text-ink-subtle">{String(value)}</span>
        </p>
      ))}
    </div>
  );
}

export function DiscoveryRunDetailPage() {
  const params = useParams();
  const runId = Number(params.runId);
  const { data: run, loading, error, reload } = useAsync(
    () => api.getDiscoveryRun(runId),
    [runId],
  );

  if (!Number.isFinite(runId)) {
    return <ErrorState message="That run id is not valid." />;
  }

  if (loading) return <LoadingState label="Loading run…" />;
  if (error || !run) return <ErrorState message={error ?? 'Run not found.'} onRetry={reload} />;

  const hasProblem = run.outcome === 'stopped_after_error';

  return (
    <>
      <div className="mb-4">
        <Link
          to="/runs"
          className="text-sm font-medium text-accent-600 hover:underline"
        >
          ← Back to workflow runs
        </Link>
      </div>

      <PageHeader
        title={`Discovery Run #${run.id}`}
        description={`Campaign “${run.campaign_name ?? '—'}”`}
        actions={
          <>
            <StatusPill status={run.status} />
            <Button
              variant="secondary"
              size="sm"
              loading={false}
              onClick={reload}
              title="Reload"
            >
              Reload
            </Button>
          </>
        }
      />

      {hasProblem ? (
        <div
          className="mb-4 rounded-md border border-danger/30 bg-danger-bg px-3.5 py-3"
        >
          <p className="text-sm font-medium text-danger">
            The run stopped after an error
          </p>
          <p className="mt-1 break-words text-sm text-ink-muted">
            {run.error_code ? `[${run.error_code}] ` : ''}
            {run.error_message ?? 'No detail recorded.'}
          </p>
          <p className="mt-1.5 text-xs text-ink-subtle">
            No companies were created from this run.
          </p>
        </div>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-3">
        <Panel title="Run summary" className="lg:col-span-2">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Outcome</dt>
              <dd className="mt-1.5">
                <StatusPill tone={outcomeTone(run.outcome)} label={outcomeLabel(run.outcome)} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Status</dt>
              <dd className="mt-1.5">
                <StatusPill status={run.status} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Started</dt>
              <dd className="mt-1.5 text-sm text-ink">{formatDateTime(run.started_at)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Duration</dt>
              <dd className="mt-1.5 text-sm tabular-nums text-ink">
                {formatDuration(run.started_at, run.finished_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Companies created</dt>
              <dd className="mt-1.5 text-sm tabular-nums text-ink">{run.companies_created}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Duplicates found</dt>
              <dd className="mt-1.5 text-sm tabular-nums text-ink">{run.duplicates_found}</dd>
            </div>
          </dl>
        </Panel>

        <Panel title="Stage history" className="lg:col-span-3 mt-5">
          <Table caption="Stage event history">
            <thead>
              <tr>
                <TH align="right">#</TH>
                <TH>Stage</TH>
                <TH>Status</TH>
                <TH>Started</TH>
                <TH align="right">Duration</TH>
                <TH>Details</TH>
              </tr>
            </thead>
            <tbody>
              {run.events.map((event, index) => (
                <tr key={event.id} className="align-top hover:bg-surface-muted">
                  <TD align="right" className="tabular-nums text-ink-subtle">
                    {index + 1}
                  </TD>
                  <TD className="font-medium text-ink">{event.stage}</TD>
                  <TD>
                    <StatusPill status={event.status} />
                  </TD>
                  <TD className="whitespace-nowrap text-xs">
                    {formatDateTime(event.started_at)}
                  </TD>
                  <TD align="right" className="whitespace-nowrap tabular-nums">
                    {formatDuration(event.started_at, event.finished_at)}
                  </TD>
                  <TD>
                    {event.error_message ? (
                      <p className="text-xs text-danger">
                        {event.error_code ? `[${event.error_code}] ` : ''}
                        {truncate(event.error_message, 220)}
                      </p>
                    ) : null}
                    <EventDetails details={event.details} />
                  </TD>
                </tr>
              ))}
            </tbody>
          </Table>
        </Panel>

        <Panel title="Companies discovered" className="mt-5">
          {run.companies_created === 0 ? (
            <EmptyState
              title="No companies created"
              description="This discovery run did not create any new company records."
            />
          ) : (
            <p className="text-sm text-ink-muted mb-3">
              Click a company to view its evidence and source records.
            </p>
          )}
        </Panel>
      </div>
    </>
  );
}
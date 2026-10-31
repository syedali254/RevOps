import { Link } from 'react-router-dom';

import { api } from '../lib/api';
import { useAsync } from '../hooks/useAsync';
import { formatDateTime, statusLabel } from '../lib/format';
import type { WorkflowRun } from '../lib/types';
import {
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
  Table,
  TD,
  TH,
  TestTag,
} from '../components/ui';

function Stat({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string | number;
  note?: string;
  tone?: 'ok' | 'warn' | 'danger';
}) {
  const valueTone =
    tone === 'ok' ? 'text-ok' : tone === 'warn' ? 'text-warn' : tone === 'danger' ? 'text-danger' : 'text-ink';
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3.5 shadow-xs">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-subtle">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold leading-none ${valueTone}`}>{value}</p>
      {note ? <p className="mt-1.5 text-xs text-ink-subtle">{note}</p> : null}
    </div>
  );
}

function RecentRuns({ runs }: { runs: WorkflowRun[] }) {
  if (runs.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        No workflow runs yet. Create a campaign, then start a run from{' '}
        <Link to="/runs" className="font-medium text-accent-600 hover:underline">
          Workflow runs
        </Link>
        .
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line">
      {runs.map((run) => (
        <li key={run.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
          <div className="min-w-0">
            <Link
              to={`/runs/${run.id}`}
              className="block truncate text-sm font-medium text-ink hover:text-accent-600"
            >
              Run #{run.id} · {run.company_name ?? 'Unknown company'}
            </Link>
            <p className="mt-0.5 truncate text-xs text-ink-subtle">
              {run.campaign_name ?? 'Unknown campaign'} · {formatDateTime(run.started_at)}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {run.is_test_run ? <TestTag /> : null}
            <StatusPill status={run.status} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function OverviewPage() {
  const { data, loading, error, reload } = useAsync(() => api.overview(), []);

  if (loading) return <LoadingState label="Loading overview…" />;
  if (error || !data) return <ErrorState message={error ?? 'No data returned.'} onRetry={reload} />;

  const { counts, safety, sources, recent_runs, next_actions } = data;
  const reviewCount = counts.runs_by_status.needs_review ?? 0;
  const failedCount = counts.runs_by_status.failed ?? 0;

  return (
    <>
      <PageHeader
        title="Overview"
        description="Live counts from the local database. Nothing here is mocked: every number comes from the API."
      />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Stat label="Campaigns" value={counts.campaigns} note="Saved target profiles" />
        <Stat
          label="Companies"
          value={counts.companies}
          note={`${counts.test_companies} test · ${counts.retrieved_companies} retrieved`}
        />
        <Stat label="Workflow runs" value={counts.runs} note="LangGraph executions" />
        <Stat
          label="Needs attention"
          value={reviewCount + failedCount}
          note={`${reviewCount} in review · ${failedCount} failed`}
          tone={reviewCount + failedCount > 0 ? 'warn' : undefined}
        />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Panel
          title="Recent workflow activity"
          description="Newest first"
          className="lg:col-span-2"
        >
          <RecentRuns runs={recent_runs} />
        </Panel>

        <div className="space-y-5">
          <Panel title="Next actions">
            <ul className="space-y-2.5 text-sm text-ink-muted">
              {next_actions.map((action) => (
                <li key={action} className="flex gap-2.5">
                  <span
                    aria-hidden="true"
                    className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-subtle"
                  />
                  <span>{action}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Safety status">
            <dl className="space-y-2.5 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-muted">Mode</dt>
                <dd>
                  <StatusPill
                    tone={safety.dry_run ? 'warn' : 'danger'}
                    label={safety.dry_run ? 'Dry run' : 'LIVE'}
                  />
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-muted">Messages sent</dt>
                <dd className="font-medium tabular-nums text-ink">{safety.messages_sent}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-muted">Send implemented</dt>
                <dd className="font-medium text-ink">
                  {safety.send_implemented ? 'Yes' : 'No — blocked in code'}
                </dd>
              </div>
            </dl>
            <p className="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-ink-subtle">
              {safety.detail}
            </p>
          </Panel>
        </div>
      </div>

      <Panel
        title="Source health"
        description="A source that is unavailable must never look like an empty market."
        className="mt-5"
      >
        <Table caption="Source connector health">
          <thead>
            <tr>
              <TH>Source</TH>
              <TH>Role</TH>
              <TH>Provider</TH>
              <TH>Status</TH>
              <TH>Notes</TH>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr key={source.key} className="hover:bg-surface-muted">
                <TD className="font-medium text-ink">{source.label}</TD>
                <TD className="capitalize">{source.role}</TD>
                <TD>{source.provider ?? '—'}</TD>
                <TD>
                  <StatusPill status={source.status} />
                </TD>
                <TD className="text-xs">{source.detail}</TD>
              </tr>
            ))}
          </tbody>
        </Table>
        <div className="mt-4 flex items-center justify-between gap-4">
          <p className="text-xs text-ink-subtle">
            Connectors are listed with an explicit status rather than being hidden.
          </p>
          <Link to="/campaigns">
            <Button size="sm" variant="secondary">
              Go to campaigns
            </Button>
          </Link>
        </div>
      </Panel>

      <p className="mt-5 text-xs text-ink-subtle">
        Data generated at {formatDateTime(data.generated_at)} ·{' '}
        <button
          type="button"
          onClick={reload}
          className="font-medium text-accent-600 hover:underline"
        >
          Refresh
        </button>
        {reviewCount > 0 ? ` · ${statusLabel('needs_review')} runs are blocked until reviewed` : ''}
        {failedCount > 0 && reviewCount === 0 ? ` · ${statusLabel('failed')} runs need inspection` : ''}
      </p>
    </>
  );
}

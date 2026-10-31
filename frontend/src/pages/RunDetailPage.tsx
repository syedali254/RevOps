import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useAsync } from '../hooks/useAsync';
import {
  formatDateTime,
  formatDuration,
  outcomeLabel,
  outcomeTone,
  truncate,
} from '../lib/format';
import type { StageEvent } from '../lib/types';
import {
  Button,
  ErrorState,
  Field,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
  Table,
  TD,
  TH,
  TestTag,
  inputClass,
} from '../components/ui';

interface CheckDetail {
  rule: string;
  status: string;
  detail: string;
}

function EventDetails({ details }: { details: Record<string, unknown> }) {
  const checks = details.checks as CheckDetail[] | undefined;
  const entries = Object.entries(details).filter(
    ([key, value]) =>
      key !== 'checks' && (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'),
  );

  if (!checks && entries.length === 0) {
    return <span className="text-xs text-ink-subtle">—</span>;
  }

  return (
    <div className="space-y-1.5">
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

function ManualNoteForm({ runId, onLogged }: { runId: number; onLogged: () => void }) {
  const [message, setMessage] = useState('');
  const [stage, setStage] = useState('human_review');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (!message.trim()) {
      setError('Write a note before saving.');
      return;
    }

    setSubmitting(true);
    try {
      await api.logManualEvent(runId, {
        stage,
        status: 'ok',
        message: message.trim(),
        details: { manual: true, entered_by: 'ui' },
      });
      setMessage('');
      setNotice('Manual event saved. It is labelled as manually logged, not as a system event.');
      onLogged();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.detail : String(cause));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Panel
      title="Log a human decision"
      description="Manually recorded events are clearly separated from workflow events."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Event type" htmlFor="manual-stage">
          <select
            id="manual-stage"
            className={inputClass}
            value={stage}
            onChange={(event) => setStage(event.target.value)}
          >
            <option value="human_review">Human review</option>
            <option value="manual_note">Manual note</option>
            <option value="call_outcome_logged">Call outcome (manually logged)</option>
          </select>
        </Field>

        <Field label="Note" htmlFor="manual-message" required>
          <textarea
            id="manual-message"
            rows={3}
            className={`${inputClass} h-auto py-2`}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Reviewer confirmed the domain belongs to the company."
          />
        </Field>

        {error ? (
          <p className="rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="rounded-md border border-ok/30 bg-ok-bg px-3 py-2 text-sm text-ok">
            {notice}
          </p>
        ) : null}

        <Button type="submit" variant="primary" size="sm" loading={submitting}>
          Save note
        </Button>
      </form>
    </Panel>
  );
}

export function RunDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const runId = Number(params.runId);
  const { data: run, loading, error, reload } = useAsync(
    () => api.getRun(runId),
    [runId],
  );
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  if (!Number.isFinite(runId)) {
    return <ErrorState message="That run id is not valid." />;
  }

  if (loading) return <LoadingState label="Loading run…" />;
  if (error || !run) return <ErrorState message={error ?? 'Run not found.'} onRetry={reload} />;

  async function handleRetry() {
    setRetryError(null);
    setRetrying(true);
    try {
      const retried = await api.retryRun(runId);
      navigate(`/runs/${retried.id}`);
    } catch (cause) {
      setRetryError(cause instanceof ApiError ? cause.detail : String(cause));
      setRetrying(false);
    }
  }

  const hasProblem = run.outcome === 'needs_human_review' || run.outcome === 'stopped_after_error';

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
        title={`Run #${run.id}`}
        description={`Campaign “${run.campaign_name ?? '—'}” · company “${run.company_name ?? '—'}”`}
        actions={
          <>
            {run.is_test_run ? <TestTag /> : null}
            <StatusPill status={run.status} />
            <Button
              variant="secondary"
              size="sm"
              loading={retrying}
              onClick={handleRetry}
              title="Runs the same campaign and company again without creating a duplicate company"
            >
              Retry run
            </Button>
          </>
        }
      />

      {retryError ? (
        <div className="mb-4">
          <ErrorState message={retryError} onRetry={handleRetry} />
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
            <div className="sm:col-span-2">
              <dt className="text-xs font-medium uppercase tracking-wide text-ink-subtle">
                Events recorded
              </dt>
              <dd className="mt-1.5 text-sm tabular-nums text-ink">{run.events.length}</dd>
            </div>
          </dl>

          {hasProblem ? (
            <div
              className={`mt-4 rounded-md border px-3.5 py-3 ${
                run.outcome === 'stopped_after_error'
                  ? 'border-danger/30 bg-danger-bg'
                  : 'border-warn/30 bg-warn-bg'
              }`}
            >
              <p
                className={`text-sm font-medium ${
                  run.outcome === 'stopped_after_error' ? 'text-danger' : 'text-warn'
                }`}
              >
                {run.outcome === 'stopped_after_error'
                  ? 'The run stopped after an error'
                  : 'Held for human review'}
              </p>
              <p className="mt-1 break-words text-sm text-ink-muted">
                {run.outcome === 'stopped_after_error'
                  ? `${run.error_code ? `[${run.error_code}] ` : ''}${run.error_message ?? 'No detail recorded.'}`
                  : run.review_reason ?? 'No reason recorded.'}
              </p>
              <p className="mt-1.5 text-xs text-ink-subtle">
                The record did not advance to the next stage.
              </p>
            </div>
          ) : null}
        </Panel>

        <ManualNoteForm runId={run.id} onLogged={reload} />
      </div>

      <Panel
        title="Stage history"
        description="Written by the LangGraph nodes, newest stage last."
        className="mt-5"
      >
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
            {run.events.map((event: StageEvent, index: number) => (
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
    </>
  );
}

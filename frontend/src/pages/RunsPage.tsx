import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useAsync } from '../hooks/useAsync';
import { formatDateTime, formatDuration, outcomeLabel, outcomeTone } from '../lib/format';
import type { DiscoveryRun, RunCreatePayload } from '../lib/types';
import {
  Button,
  EmptyState,
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

function NewRunForm({
  campaigns,
  defaultCampaignId,
  onDone,
}: {
  campaigns: { id: number; name: string }[];
  defaultCampaignId?: number;
  onDone: (runId: number) => void;
}) {
  const [campaignId, setCampaignId] = useState(
    String(defaultCampaignId ?? campaigns[0]?.id ?? ''),
  );
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [country, setCountry] = useState('United States');
  const [sector, setSector] = useState('');
  const [employeeMin, setEmployeeMin] = useState('');
  const [employeeMax, setEmployeeMax] = useState('');
  const [failAt, setFailAt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    if (!campaignId) {
      setFormError('Select a campaign.');
      return;
    }
    if (!name.trim()) {
      setFormError('Company name is required.');
      return;
    }

    const payload: RunCreatePayload = {
      campaign_id: Number(campaignId),
      company: {
        canonical_name: name.trim(),
        website_domain: domain.trim() || null,
        country: country.trim() || null,
        sector: sector.trim() || null,
        employee_min: employeeMin === '' ? null : Number(employeeMin),
        employee_max: employeeMax === '' ? null : Number(employeeMax),
      },
      fail_at: failAt ? (failAt as RunCreatePayload['fail_at']) : null,
    };

    setSubmitting(true);
    try {
      const run = await api.createRun(payload);
      onDone(run.id);
    } catch (cause) {
      setFormError(cause instanceof ApiError ? cause.detail : String(cause));
      setSubmitting(false);
    }
  }

  return (
    <Panel
      title="Start a workflow run"
      description="Milestone 1 only accepts hand-entered records, so everything created here is labelled TEST DATA."
      className="mb-5"
    >
      <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Field label="Campaign" htmlFor="run-campaign" required>
          <select
            id="run-campaign"
            className={inputClass}
            value={campaignId}
            onChange={(event) => setCampaignId(event.target.value)}
          >
            {campaigns.map((campaign) => (
              <option key={campaign.id} value={campaign.id}>
                {campaign.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Company name" htmlFor="run-company" required>
          <input
            id="run-company"
            className={inputClass}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Acme Analytics Co"
            autoComplete="off"
          />
        </Field>

        <Field
          label="Website domain"
          htmlFor="run-domain"
          hint="Leave empty to see the human-review path."
        >
          <input
            id="run-domain"
            className={inputClass}
            value={domain}
            onChange={(event) => setDomain(event.target.value)}
            placeholder="acme-analytics.com"
            autoComplete="off"
          />
        </Field>

        <Field label="Country" htmlFor="run-country">
          <input
            id="run-country"
            className={inputClass}
            value={country}
            onChange={(event) => setCountry(event.target.value)}
          />
        </Field>

        <Field label="Sector" htmlFor="run-sector">
          <input
            id="run-sector"
            className={inputClass}
            value={sector}
            onChange={(event) => setSector(event.target.value)}
            placeholder="software"
            autoComplete="off"
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Min employees" htmlFor="run-emp-min">
            <input
              id="run-emp-min"
              type="number"
              min={0}
              className={inputClass}
              value={employeeMin}
              onChange={(event) => setEmployeeMin(event.target.value)}
              placeholder="20"
            />
          </Field>
          <Field label="Max employees" htmlFor="run-emp-max">
            <input
              id="run-emp-max"
              type="number"
              min={0}
              className={inputClass}
              value={employeeMax}
              onChange={(event) => setEmployeeMax(event.target.value)}
              placeholder="80"
            />
          </Field>
        </div>

        <Field
          label="Test control"
          htmlFor="run-fail-at"
          hint="Optionally force a stage to fail so the failure path can be demonstrated. Nothing is faked silently."
        >
          <select
            id="run-fail-at"
            className={inputClass}
            value={failAt}
            onChange={(event) => setFailAt(event.target.value)}
          >
            <option value="">No forced failure</option>
            <option value="find">Fail at “find”</option>
            <option value="merge">Fail at “merge”</option>
            <option value="evaluate">Fail at “evaluate”</option>
          </select>
        </Field>

        {formError ? (
          <p className="rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger lg:col-span-3">
            {formError}
          </p>
        ) : null}

        <div className="lg:col-span-3">
          <Button type="submit" variant="primary" loading={submitting}>
            Run workflow
          </Button>
        </div>
      </form>
    </Panel>
  );
}

function DiscoveryRunRow({
  run,
  onClick,
}: {
  run: DiscoveryRun;
  onClick: () => void;
}) {
  return (
    <tr key={run.id} className="hover:bg-surface-muted cursor-pointer" onClick={onClick}>
      <TD className="font-medium text-ink">
        <span className="inline-flex items-center gap-1.5">
          <span className="text-xs font-medium px-1.5 py-0.5 rounded-sm border border-accent-200 bg-accent-50 text-accent-700">
            Discovery
          </span>
          #{run.id}
        </span>
      </TD>
      <TD>
        <span className="text-xs text-ink-muted">
          {run.companies_created} created · {run.duplicates_found} duplicates
        </span>
      </TD>
      <TD className="max-w-[14rem] truncate">{run.campaign_name ?? '—'}</TD>
      <TD>
        <StatusPill status={run.status} />
      </TD>
      <TD>
        <StatusPill tone={outcomeTone(run.outcome)} label={outcomeLabel(run.outcome)} />
      </TD>
      <TD className="whitespace-nowrap text-xs">{formatDateTime(run.started_at)}</TD>
      <TD align="right" className="tabular-nums">{formatDuration(run.started_at, run.finished_at)}</TD>
      <TD align="right" className="tabular-nums">{run.events.length}</TD>
    </tr>
  );
}

export function RunsPage() {
  const [searchParams] = useSearchParams();
  const campaignFilter = searchParams.get('campaign_id');
  const navigate = useNavigate();

  const campaignsState = useAsync(() => api.listCampaigns(), []);
  const runsState = useAsync(
    () => api.listRuns(campaignFilter ? Number(campaignFilter) : undefined),
    [campaignFilter],
  );
  const discoveryRunsState = useAsync(
    () => api.listDiscoveryRuns(campaignFilter ? Number(campaignFilter) : undefined),
    [campaignFilter],
  );

  const [showForm, setShowForm] = useState(false);
  const campaigns = campaignsState.data ?? [];
  const filteredCampaign = campaignFilter
    ? campaigns.find((campaign) => String(campaign.id) === campaignFilter)
    : undefined;

  return (
    <>
      <PageHeader
        title="Workflow runs"
        description={
          filteredCampaign
            ? `Showing runs for “${filteredCampaign.name}”.`
            : 'Every stage of every run, with the outcome the graph actually produced.'
        }
        actions={
          campaigns.length > 0 ? (
            <Button variant="primary" onClick={() => setShowForm((value) => !value)}>
              {showForm ? 'Close form' : 'New run'}
            </Button>
          ) : null
        }
      />

      {showForm ? (
        <NewRunForm
          campaigns={campaigns}
          defaultCampaignId={campaignFilter ? Number(campaignFilter) : undefined}
          onDone={(runId) => {
            setShowForm(false);
            navigate(`/runs/${runId}`);
          }}
        />
      ) : null}

      {campaignsState.loading ? <LoadingState label="Loading campaigns…" /> : null}

      {campaignsState.error ? (
        <ErrorState message={campaignsState.error} onRetry={campaignsState.reload} />
      ) : null}

      {!campaignsState.loading && !campaignsState.error && campaigns.length === 0 ? (
        <EmptyState
          title="A campaign is needed first"
          description="Workflow runs belong to a campaign. Create one before starting a run."
          action={
            <Link to="/campaigns">
              <Button variant="primary">Go to campaigns</Button>
            </Link>
          }
        />
      ) : null}

      {!campaignsState.loading && !campaignsState.error && campaigns.length > 0 ? (
        <>
          <div className="mb-4">
            <h3 className="text-sm font-medium text-ink mb-2">Qualification runs</h3>
            {runsState.loading ? <LoadingState label="Loading runs…" /> : null}
            {runsState.error ? (
              <ErrorState message={runsState.error} onRetry={runsState.reload} />
            ) : null}

            {!runsState.loading && !runsState.error && runsState.data?.length === 0 ? (
              <EmptyState
                title="No qualification runs yet"
                description="Start a workflow run to see the LangGraph stage history, review holds and failure handling."
                action={
                  <Button variant="primary" onClick={() => setShowForm(true)}>
                    Start the first run
                  </Button>
                }
              />
            ) : null}

            {!runsState.loading && !runsState.error && runsState.data && runsState.data.length > 0 ? (
              <Table caption="Qualification runs">
                <thead>
                  <tr>
                    <TH>Run</TH>
                    <TH>Company</TH>
                    <TH>Campaign</TH>
                    <TH>Status</TH>
                    <TH>Outcome</TH>
                    <TH>Started</TH>
                    <TH align="right">Duration</TH>
                    <TH align="right">Events</TH>
                  </tr>
                </thead>
                <tbody>
                  {runsState.data.map((run) => (
                    <tr key={run.id} className="hover:bg-surface-muted">
                      <TD className="font-medium text-ink">
                        <Link to={`/runs/${run.id}`} className="hover:text-accent-600">
                          #{run.id}
                        </Link>
                      </TD>
                      <TD>
                        <span className="flex items-center gap-2">
                          <span className="text-ink">{run.company_name ?? '—'}</span>
                          {run.is_test_run ? <TestTag /> : null}
                        </span>
                      </TD>
                      <TD className="max-w-[14rem] truncate">{run.campaign_name ?? '—'}</TD>
                      <TD>
                        <StatusPill status={run.status} />
                      </TD>
                      <TD>
                        <StatusPill tone={outcomeTone(run.outcome)} label={outcomeLabel(run.outcome)} />
                      </TD>
                      <TD className="whitespace-nowrap text-xs">
                        {formatDateTime(run.started_at)}
                      </TD>
                      <TD align="right" className="tabular-nums">
                        {formatDuration(run.started_at, run.finished_at)}
                      </TD>
                      <TD align="right" className="tabular-nums">
                        {run.events.length}
                      </TD>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : null}
          </div>

          <div>
            <h3 className="text-sm font-medium text-ink mb-2">Discovery runs</h3>
            {discoveryRunsState.loading ? <LoadingState label="Loading discovery runs…" /> : null}
            {discoveryRunsState.error ? (
              <ErrorState message={discoveryRunsState.error} onRetry={discoveryRunsState.reload} />
            ) : null}

            {!discoveryRunsState.loading && !discoveryRunsState.error && discoveryRunsState.data?.length === 0 ? (
              <EmptyState
                title="No discovery runs yet"
                description="Start a discovery run from the Campaigns page to find candidate companies."
                action={
                  <Link to="/campaigns">
                    <Button variant="primary">Go to campaigns</Button>
                  </Link>
                }
              />
            ) : null}

            {!discoveryRunsState.loading && !discoveryRunsState.error && discoveryRunsState.data && discoveryRunsState.data.length > 0 ? (
              <Table caption="Discovery runs">
                <thead>
                  <tr>
                    <TH>Run</TH>
                    <TH>Results</TH>
                    <TH>Campaign</TH>
                    <TH>Status</TH>
                    <TH>Outcome</TH>
                    <TH>Started</TH>
                    <TH align="right">Duration</TH>
                    <TH align="right">Events</TH>
                  </tr>
                </thead>
                <tbody>
                  {discoveryRunsState.data.map((run) => (
                    <DiscoveryRunRow key={run.id} run={run} onClick={() => navigate(`/discovery/${run.id}`)} />
                  ))}
                </tbody>
              </Table>
            ) : null}
          </div>
        </>
      ) : null}
    </>
  );
}

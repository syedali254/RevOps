import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useAsync } from '../hooks/useAsync';
import { formatDate, summarizeSettings } from '../lib/format';
import type { CampaignSettings, DiscoveryRunCreatePayload } from '../lib/types';
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
  inputClass,
} from '../components/ui';

const DEFAULT_SETTINGS: CampaignSettings = {
  countries: ['United States'],
  sectors: ['software', 'IT services', 'data'],
  employee_min: 20,
  employee_max: 200,
  target_titles: ['Founder', 'CEO', 'Head of Operations', 'Head of IT'],
  exclusions: [],
  require_domain: true,
};

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function NewCampaignForm({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');
  const [countries, setCountries] = useState(DEFAULT_SETTINGS.countries.join(', '));
  const [sectors, setSectors] = useState(DEFAULT_SETTINGS.sectors.join(', '));
  const [employeeMin, setEmployeeMin] = useState('20');
  const [employeeMax, setEmployeeMax] = useState('200');
  const [titles, setTitles] = useState(DEFAULT_SETTINGS.target_titles.join(', '));
  const [requireDomain, setRequireDomain] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    if (!name.trim()) {
      setFormError('Campaign name is required.');
      return;
    }

    setSubmitting(true);
    try {
      await api.createCampaign({
        name: name.trim(),
        settings: {
          countries: splitList(countries),
          sectors: splitList(sectors),
          employee_min: employeeMin === '' ? null : Number(employeeMin),
          employee_max: employeeMax === '' ? null : Number(employeeMax),
          target_titles: splitList(titles),
          exclusions: [],
          require_domain: requireDomain,
        },
      });
      onCreated();
    } catch (cause) {
      setFormError(cause instanceof ApiError ? cause.detail : String(cause));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Panel
      title="New campaign"
      description="Settings are saved as an immutable snapshot on the campaign, so runs stay comparable."
      className="mb-5"
    >
      <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <Field label="Campaign name" htmlFor="campaign-name" required>
            <input
              id="campaign-name"
              className={inputClass}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="US B2B software — autumn outreach"
              autoComplete="off"
            />
          </Field>
        </div>

        <Field
          label="Countries"
          htmlFor="campaign-countries"
          hint="Comma separated. Unknown countries never count as a match."
        >
          <input
            id="campaign-countries"
            className={inputClass}
            value={countries}
            onChange={(event) => setCountries(event.target.value)}
          />
        </Field>

        <Field
          label="Sectors"
          htmlFor="campaign-sectors"
          hint="Comma separated keywords matched against the company sector."
        >
          <input
            id="campaign-sectors"
            className={inputClass}
            value={sectors}
            onChange={(event) => setSectors(event.target.value)}
          />
        </Field>

        <Field label="Minimum employees" htmlFor="campaign-emp-min">
          <input
            id="campaign-emp-min"
            type="number"
            min={0}
            className={inputClass}
            value={employeeMin}
            onChange={(event) => setEmployeeMin(event.target.value)}
          />
        </Field>

        <Field label="Maximum employees" htmlFor="campaign-emp-max">
          <input
            id="campaign-emp-max"
            type="number"
            min={0}
            className={inputClass}
            value={employeeMax}
            onChange={(event) => setEmployeeMax(event.target.value)}
          />
        </Field>

        <div className="md:col-span-2">
          <Field
            label="Decision-maker titles"
            htmlFor="campaign-titles"
            hint="Stored exactly as entered; used later when researching people."
          >
            <input
              id="campaign-titles"
              className={inputClass}
              value={titles}
              onChange={(event) => setTitles(event.target.value)}
            />
          </Field>
        </div>

        <label className="flex items-center gap-2.5 text-sm text-ink-muted">
          <input
            type="checkbox"
            className="h-4 w-4 rounded-sm border-line-strong accent-[var(--color-accent-600)]"
            checked={requireDomain}
            onChange={(event) => setRequireDomain(event.target.checked)}
          />
          Require a website domain before a lead can qualify
        </label>

        {formError ? (
          <p className="rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger md:col-span-2">
            {formError}
          </p>
        ) : null}

        <div className="flex items-center gap-2 md:col-span-2">
          <Button type="submit" variant="primary" loading={submitting}>
            Create campaign
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        </div>
      </form>
    </Panel>
  );
}

function NewDiscoveryForm({
  campaignId,
  campaignName,
  onCancel,
  onSubmit,
}: {
  campaignId: number;
  campaignName: string;
  onCancel: () => void;
  onSubmit: (campaignId: number, payload: DiscoveryRunCreatePayload) => Promise<void>;
}) {
  const [maxResults, setMaxResults] = useState('');
  const [failAt, setFailAt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    const payload: DiscoveryRunCreatePayload = {
      campaign_id: campaignId,
      max_results: maxResults === '' ? null : Number(maxResults),
      fail_at: failAt ? (failAt as DiscoveryRunCreatePayload['fail_at']) : null,
    };

    setSubmitting(true);
    try {
      await onSubmit(campaignId, payload);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Panel
      title={`Start discovery for “${campaignName}”`}
      description="Runs the web search connector against the campaign criteria. Creates candidate companies with source evidence."
      className="mb-5"
    >
      <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
        <Field
          label="Max results"
          htmlFor="discovery-max-results"
          hint="Optional. Maximum candidates to retrieve from the connector."
        >
          <input
            id="discovery-max-results"
            type="number"
            min={1}
            max={200}
            className={inputClass}
            value={maxResults}
            onChange={(event) => setMaxResults(event.target.value)}
            placeholder="50"
          />
        </Field>

        <Field
          label="Test control"
          htmlFor="discovery-fail-at"
          hint="Optionally force a stage to fail for demonstration."
        >
          <select
            id="discovery-fail-at"
            className={inputClass}
            value={failAt}
            onChange={(event) => setFailAt(event.target.value)}
          >
            <option value="">No forced failure</option>
            <option value="find">Fail at "find"</option>
            <option value="merge">Fail at "merge"</option>
            <option value="evaluate">Fail at "evaluate"</option>
          </select>
        </Field>

        {formError ? (
          <p className="rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger md:col-span-2">
            {formError}
          </p>
        ) : null}

        <div className="flex items-center gap-2 md:col-span-2">
          <Button type="submit" variant="primary" loading={submitting}>
            Start discovery
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        </div>
      </form>
    </Panel>
  );
}

export function CampaignsPage() {
  const { data, loading, error, reload } = useAsync(() => api.listCampaigns(), []);
  const [showForm, setShowForm] = useState(false);
  const [showDiscoveryForm, setShowDiscoveryForm] = useState<{ campaignId: number; campaignName: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleDiscoverySubmit(_campaignId: number, payload: DiscoveryRunCreatePayload) {
    try {
      await api.createDiscoveryRun(payload);
      setShowDiscoveryForm(null);
      setNotice('Discovery run started. Results will appear on the Workflow runs page.');
      reload();
    } catch {
      // Error is handled inside NewDiscoveryForm via its own state
    }
  }

  function openDiscoveryForm(campaignId: number, campaignName: string) {
    setShowDiscoveryForm({ campaignId, campaignName });
  }

  return (
    <>
      <PageHeader
        title="Campaigns"
        description="Each campaign keeps its own copy of the target settings so results can be compared."
        actions={
          <Button
            variant="primary"
            onClick={() => {
              setNotice(null);
              setShowForm((value) => !value);
            }}
          >
            {showForm ? 'Close form' : 'New campaign'}
          </Button>
        }
      />

      {notice ? (
        <p
          role="status"
          className="mb-4 rounded-md border border-ok/30 bg-ok-bg px-3.5 py-2.5 text-sm text-ok"
        >
          {notice}
        </p>
      ) : null}

      {showForm ? (
        <NewCampaignForm
          onCancel={() => setShowForm(false)}
          onCreated={() => {
            setShowForm(false);
            setNotice('Campaign created and saved to the database.');
            reload();
          }}
        />
      ) : null}

      {showDiscoveryForm ? (
        <NewDiscoveryForm
          campaignId={showDiscoveryForm.campaignId}
          campaignName={showDiscoveryForm.campaignName}
          onCancel={() => setShowDiscoveryForm(null)}
          onSubmit={handleDiscoverySubmit}
        />
      ) : null}

      {loading ? <LoadingState label="Loading campaigns…" /> : null}

      {error ? (
        <div className="space-y-4">
          <ErrorState message={error} onRetry={reload} />
        </div>
      ) : null}

      {!loading && !error && data && data.length === 0 ? (
        <EmptyState
          title="No campaigns yet"
          description="Create a campaign to define the sector, country and company size you want to target."
          action={
            <Button variant="primary" onClick={() => setShowForm(true)}>
              Create the first campaign
            </Button>
          }
        />
      ) : null}

      {!loading && !error && data && data.length > 0 ? (
        <Table caption="Saved campaigns">
          <thead>
            <tr>
              <TH>Name</TH>
              <TH>Status</TH>
              <TH>Target settings</TH>
              <TH align="right">Companies</TH>
              <TH align="right">Runs</TH>
              <TH>Created</TH>
              <TH align="right">Actions</TH>
            </tr>
          </thead>
          <tbody>
            {data.map((campaign) => (
              <tr key={campaign.id} className="hover:bg-surface-muted">
                <TD className="font-medium text-ink">{campaign.name}</TD>
                <TD>
                  <StatusPill status={campaign.status} label={campaign.status} />
                </TD>
                <TD className="text-xs">{summarizeSettings(campaign.settings)}</TD>
                <TD align="right" className="tabular-nums">
                  {campaign.company_count}
                </TD>
                <TD align="right" className="tabular-nums">
                  {campaign.run_count}
                </TD>
                <TD className="whitespace-nowrap text-xs">{formatDate(campaign.created_at)}</TD>
                <TD align="right">
                  <div className="flex items-center gap-2 justify-end">
                    <Link
                      to={`/runs?campaign_id=${campaign.id}`}
                      className="text-sm font-medium text-accent-600 hover:underline"
                    >
                      View runs
                    </Link>
                    <Link
                      to={`/campaigns/${campaign.id}/companies`}
                      className="text-sm font-medium text-accent-600 hover:underline"
                    >
                      View companies
                    </Link>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => openDiscoveryForm(campaign.id, campaign.name)}
                    >
                      Start discovery
                    </Button>
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
// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppRoutes } from './routes';
import type { Campaign, Health, Overview, WorkflowRun } from './lib/types';

const SAFETY = {
  dry_run: true,
  messages_sent: 0,
  send_implemented: false,
  banner: 'DRY RUN — NO MESSAGES SENT',
  detail: 'No email, SMS, LinkedIn/social or website-form message can be sent from this build.',
};

const HEALTH: Health = {
  status: 'ok',
  app: 'B2B Lead Engine',
  version: '0.1.0',
  time: '2026-10-20T09:00:00Z',
  database: 'sqlite:///./b2b_lead_engine.db',
  safety: SAFETY,
  connectors: { web_search: 'not_configured', company_website: 'not_configured' },
  ai: { provider: null, status: 'not_configured' },
};

const CAMPAIGN: Campaign = {
  id: 1,
  name: 'US B2B software',
  status: 'draft',
  settings: {
    countries: ['United States'],
    sectors: ['software'],
    employee_min: 20,
    employee_max: 200,
    target_titles: ['CEO'],
    exclusions: [],
    require_domain: true,
  },
  settings_version: 1,
  company_count: 3,
  run_count: 3,
  created_at: '2026-10-19T10:00:00Z',
  updated_at: '2026-10-19T10:00:00Z',
};

const REVIEW_RUN: WorkflowRun = {
  id: 4,
  campaign_id: 1,
  campaign_name: 'US B2B software',
  company_id: 2,
  company_name: 'No Domain Co',
  status: 'needs_review',
  outcome: 'needs_human_review',
  review_reason: 'website_domain: No website domain, so facts cannot be evidenced.',
  error_code: null,
  error_message: null,
  is_test_run: true,
  started_at: '2026-10-20T08:59:00Z',
  finished_at: '2026-10-20T08:59:01Z',
  events: [],
};

const OVERVIEW: Overview = {
  generated_at: '2026-10-20T09:00:00Z',
  counts: {
    campaigns: 1,
    companies: 3,
    test_companies: 3,
    retrieved_companies: 0,
    runs: 3,
    runs_by_status: { completed: 1, needs_review: 1, failed: 1 },
  },
  safety: SAFETY,
  sources: [
    {
      key: 'web_search',
      label: 'Web search',
      role: 'discovery',
      provider: 'Brave Search API',
      status: 'not_configured',
      detail: 'Not implemented in Milestone 1.',
    },
  ],
  recent_runs: [REVIEW_RUN],
  next_actions: ['Create a campaign to define the target profile.'],
};

const RUN_DETAIL: WorkflowRun = {
  ...REVIEW_RUN,
  events: [
    {
      id: 10,
      stage: 'start',
      status: 'ok',
      attempt: 1,
      started_at: '2026-10-20T08:59:00Z',
      finished_at: '2026-10-20T08:59:00.050Z',
      error_code: null,
      error_message: null,
      details: {},
    },
    {
      id: 11,
      stage: 'evaluate',
      status: 'held_for_review',
      attempt: 1,
      started_at: '2026-10-20T08:59:00.100Z',
      finished_at: '2026-10-20T08:59:00.150Z',
      error_code: null,
      error_message: null,
      details: {
        checks: [
          { rule: 'website_domain', status: 'unknown', detail: 'No website domain.' },
        ],
        decision: 'needs_review',
      },
    },
  ],
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function installFetch(routes: Record<string, unknown>) {
  const mock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const match = Object.entries(routes)
      .filter(([path]) => url.includes(path))
      .sort((a, b) => b[0].length - a[0].length)[0];
    if (!match) return jsonResponse({ detail: `No mock for ${url}` }, 404);
    return jsonResponse(match[1]);
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('application shell', () => {
  it('always shows the dry-run banner and primary navigation', async () => {
    installFetch({ '/api/health': HEALTH, '/api/overview': OVERVIEW });
    renderRoute('/');

    const banner = await screen.findByText(/dry run — no messages sent/i);
    expect(banner).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeTruthy();
    for (const label of ['Overview', 'Campaigns', 'Workflow runs']) {
      expect(screen.getAllByRole('link', { name: label }).length).toBeGreaterThan(0);
    }
  });

  it('shows a real error state when the backend is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );
    renderRoute('/');

    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText(/Cannot reach the backend/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });
});

describe('overview page', () => {
  it('renders counts and source health from the API payload', async () => {
    installFetch({ '/api/health': HEALTH, '/api/overview': OVERVIEW });
    renderRoute('/');

    expect(await screen.findByText('Campaigns')).toBeTruthy();
    expect(screen.getByText('3 test · 0 retrieved')).toBeTruthy();
    expect(screen.getByText('1 in review · 1 failed')).toBeTruthy();
    expect(await screen.findByText('Web search')).toBeTruthy();
    expect(screen.getByText('Not configured')).toBeTruthy();
    expect(screen.getByText(/Send implemented/i).nextElementSibling?.textContent).toBe(
      'No — blocked in code',
    );
  });

  it('distinguishes test data from retrieved data', async () => {
    installFetch({ '/api/health': HEALTH, '/api/overview': OVERVIEW });
    renderRoute('/');

    await screen.findByText(/Run #4/);
    expect(screen.getAllByText(/test data/i).length).toBeGreaterThan(0);
  });
});

describe('campaigns page', () => {
  it('lists campaigns returned by the API', async () => {
    installFetch({ '/api/health': HEALTH, '/api/campaigns': [CAMPAIGN] });
    renderRoute('/campaigns');

    expect(await screen.findByText('US B2B software')).toBeTruthy();
    expect(screen.getByText(/United States · software · 20–200 employees/)).toBeTruthy();
  });

  it('shows an empty state instead of a blank screen', async () => {
    installFetch({ '/api/health': HEALTH, '/api/campaigns': [] });
    renderRoute('/campaigns');

    expect(await screen.findByText('No campaigns yet')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Create the first campaign' })).toBeTruthy();
  });
});

describe('workflow runs page', () => {
  it('lists runs with status, outcome and test-data label', async () => {
    installFetch({
      '/api/health': HEALTH,
      '/api/campaigns': [CAMPAIGN],
      '/api/runs': [REVIEW_RUN],
    });
    renderRoute('/runs');

    expect(await screen.findByRole('link', { name: '#4' })).toBeTruthy();
    expect(screen.getByText('No Domain Co')).toBeTruthy();
    expect(screen.getByText('Needs review')).toBeTruthy();
    expect(screen.getByText('Needs human review')).toBeTruthy();
    expect(screen.getAllByText(/test data/i).length).toBeGreaterThan(0);
  });
});

describe('run detail page', () => {
  it('shows the review reason and the stage history', async () => {
    installFetch({ '/api/health': HEALTH, '/api/runs/4': RUN_DETAIL });
    renderRoute('/runs/4');

    expect(await screen.findByText('Held for human review')).toBeTruthy();
    expect(
      screen.getByText(/website_domain: No website domain, so facts cannot be evidenced/),
    ).toBeTruthy();
    expect(screen.getByText('The record did not advance to the next stage.')).toBeTruthy();

    expect(await screen.findByText('Stage history')).toBeTruthy();
    await waitFor(() => expect(screen.getAllByText('evaluate').length).toBeGreaterThan(0));
    expect(screen.getByText('No website domain.')).toBeTruthy();
  });
});

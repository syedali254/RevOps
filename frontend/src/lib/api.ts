/**
 * The single typed API client.
 *
 * Components never call `fetch` directly — every backend interaction goes
 * through this module so the frontend/backend boundary stays in one place.
 * No secrets live here; only the public local API base URL.
 */

import type {
  Campaign,
  CampaignCreatePayload,
  CompanyDetail,
  CompanyListItem,
  DiscoveryRun,
  DiscoveryRunCreatePayload,
  Health,
  ManualEventPayload,
  Overview,
  RunCreatePayload,
  SourceHealth,
  SourceRecord,
  StageEvent,
  WorkflowRun,
} from './types';

const DEFAULT_BASE = 'http://127.0.0.1:8000';

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? DEFAULT_BASE;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

/** FastAPI validation errors arrive as objects with a `msg` field. */
function formatDetailItem(item: unknown): string {
  if (typeof item === 'string') return item;
  if (typeof item === 'object' && item !== null) {
    const record = item as Record<string, unknown>;
    if (typeof record.msg === 'string') {
      const loc = Array.isArray(record.loc) ? record.loc.slice(1).join('.') : '';
      return loc ? `${loc}: ${record.msg}` : record.msg;
    }
  }
  return String(item);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError(
      0,
      `Cannot reach the backend at ${API_BASE}. Start it with: .venv\\Scripts\\uvicorn app.main:app --reload`,
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail.map(formatDetailItem).join('; ');
      }
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>('/api/health'),

  overview: () => request<Overview>('/api/overview'),

  sources: () => request<SourceHealth[]>('/api/sources'),

  listCampaigns: () => request<Campaign[]>('/api/campaigns'),

  createCampaign: (payload: CampaignCreatePayload) =>
    request<Campaign>('/api/campaigns', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getCampaign: (id: number) => request<Campaign>(`/api/campaigns/${id}`),

  listRuns: (campaignId?: number) =>
    request<WorkflowRun[]>(
      campaignId ? `/api/runs?campaign_id=${campaignId}` : '/api/runs',
    ),

  getRun: (id: number) => request<WorkflowRun>(`/api/runs/${id}`),

  createRun: (payload: RunCreatePayload) =>
    request<WorkflowRun>('/api/runs', { method: 'POST', body: JSON.stringify(payload) }),

  retryRun: (id: number) =>
    request<WorkflowRun>(`/api/runs/${id}/retry`, { method: 'POST' }),

  logManualEvent: (runId: number, payload: ManualEventPayload) =>
    request<StageEvent>(`/api/runs/${runId}/events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Discovery runs
  listDiscoveryRuns: (campaignId?: number) =>
    request<DiscoveryRun[]>(
      campaignId ? `/api/discovery?campaign_id=${campaignId}` : '/api/discovery',
    ),

  getDiscoveryRun: (id: number) => request<DiscoveryRun>(`/api/discovery/${id}`),

  createDiscoveryRun: (payload: DiscoveryRunCreatePayload) =>
    request<DiscoveryRun>('/api/discovery', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Company sources
  listCompanySources: (companyId: number) => request<SourceRecord[]>(`/api/companies/${companyId}/sources`),

  // Company detail & list
  listCompanies: (campaignId: number) => request<CompanyListItem[]>(`/api/campaigns/${campaignId}/companies`),

  getCompany: (companyId: number) => request<CompanyDetail>(`/api/companies/${companyId}`),

  // Review & Approval
  listCompaniesNeedingReview: () => request<CompanyListItem[]>(`/api/companies/needing-review`),

  approveCompany: (companyId: number) =>
    request<CompanyDetail>(`/api/companies/${companyId}/approve`, { method: 'POST' }),

  rejectCompany: (companyId: number) =>
    request<CompanyDetail>(`/api/companies/${companyId}/reject`, { method: 'POST' }),
};

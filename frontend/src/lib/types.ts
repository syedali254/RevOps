/** Types mirroring the FastAPI (Pydantic) response models. */

export interface CampaignSettings {
  countries: string[];
  sectors: string[];
  employee_min: number | null;
  employee_max: number | null;
  target_titles: string[];
  exclusions: string[];
  require_domain: boolean;
}

export interface Campaign {
  id: number;
  name: string;
  status: string;
  settings: CampaignSettings;
  settings_version: number;
  company_count: number;
  run_count: number;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: number;
  campaign_id: number;
  canonical_name: string;
  website_domain: string | null;
  country: string | null;
  sector: string | null;
  employee_min: number | null;
  employee_max: number | null;
  record_kind: string;
  workflow_status: string;
  created_at: string;
  lead_fit_score: number | null;
  evidence_confidence: number | null;
  qualification_status: string | null;
  qualification_reason: string | null;
  scoring_version: number | null;
  scored_at: string | null;
  approval_status: string | null;
  approved_at: string | null;
  approved_by: string | null;
  research_brief: string | null;
  research_generated_at: string | null;
  research_model_version: number | null;
  is_excluded: boolean;
  exclusion_reason: string | null;
}

export interface CompanyDetail extends Company {
  sources: SourceRecord[];
}

export interface CompanyListItem {
  id: number;
  campaign_id: number;
  canonical_name: string;
  website_domain: string | null;
  country: string | null;
  sector: string | null;
  employee_min: number | null;
  employee_max: number | null;
  record_kind: string;
  workflow_status: string;
  created_at: string;
  lead_fit_score: number | null;
  evidence_confidence: number | null;
  qualification_status: string | null;
  review_reason?: string;
}

export interface StageEvent {
  id: number;
  stage: string;
  status: string;
  attempt: number;
  started_at: string;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
  details: Record<string, unknown>;
}

export interface WorkflowRun {
  id: number;
  campaign_id: number;
  campaign_name: string | null;
  company_id: number | null;
  company_name: string | null;
  status: string;
  outcome: string | null;
  review_reason: string | null;
  error_code: string | null;
  error_message: string | null;
  is_test_run: boolean;
  started_at: string;
  finished_at: string | null;
  events: StageEvent[];
}

export interface RunOut {
  id: number;
  campaign_id: number;
  campaign_name: string | null;
  company_id: number | null;
  company_name: string | null;
  run_type: string;
  status: string;
  outcome: string | null;
  review_reason: string | null;
  error_code: string | null;
  error_message: string | null;
  is_test_run: boolean;
  started_at: string;
  finished_at: string | null;
  events: StageEvent[];
}

export interface SourceHealth {
  key: string;
  label: string;
  role: string;
  provider: string | null;
  status: string;
  detail: string;
}

export interface DiscoveryRun {
  id: number;
  campaign_id: number;
  campaign_name: string | null;
  status: string;
  outcome: string | null;
  review_reason: string | null;
  error_code: string | null;
  error_message: string | null;
  is_test_run: boolean;
  started_at: string;
  finished_at: string | null;
  events: StageEvent[];
  companies_discovered: number;
  companies_created: number;
  duplicates_found: number;
}

export interface SourceRecord {
  id: number;
  company_id: number | null;
  source_type: string;
  provider: string;
  source_url: string | null;
  retrieved_at: string;
  published_at: string | null;
  status: string;
  error_message: string | null;
  raw_payload: Record<string, unknown>;
}

export interface Safety {
  dry_run: boolean;
  messages_sent: number;
  send_implemented: boolean;
  banner: string;
  detail: string;
}

export interface OverviewCounts {
  campaigns: number;
  companies: number;
  test_companies: number;
  retrieved_companies: number;
  runs: number;
  runs_by_status: Record<string, number>;
}

export interface Overview {
  generated_at: string;
  counts: OverviewCounts;
  safety: Safety;
  sources: SourceHealth[];
  recent_runs: WorkflowRun[];
  next_actions: string[];
}

export interface Health {
  status: string;
  app: string;
  version: string;
  time: string;
  database: string;
  safety: Safety;
  connectors: Record<string, string>;
  ai: { provider: string | null; status: string };
}

export interface CampaignCreatePayload {
  name: string;
  settings: CampaignSettings;
}

export interface CompanyCreatePayload {
  canonical_name: string;
  website_domain?: string | null;
  country?: string | null;
  sector?: string | null;
  employee_min?: number | null;
  employee_max?: number | null;
}

export interface RunCreatePayload {
  campaign_id: number;
  company_id?: number | null;
  company?: CompanyCreatePayload | null;
  fail_at?: 'start' | 'find' | 'merge' | 'evaluate' | null;
}

export interface DiscoveryRunCreatePayload {
  campaign_id: number;
  max_results?: number | null;
  fail_at?: 'start' | 'find' | 'merge' | 'evaluate' | null;
}

export interface ManualEventPayload {
  stage: string;
  status?: string;
  message?: string;
  details?: Record<string, unknown>;
}

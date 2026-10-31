/** Pure presentation helpers. Kept free of React and of network access. */

import type { CampaignSettings } from './types';

export type Tone = 'ok' | 'warn' | 'danger' | 'neutral' | 'muted';

const STATUS_TONE: Record<string, Tone> = {
  // run / company workflow states
  completed: 'ok',
  qualified: 'ok',
  needs_review: 'warn',
  needs_human_review: 'warn',
  running: 'neutral',
  rejected: 'neutral',
  failed: 'danger',
  failed_permanent: 'danger',
  blocked: 'danger',
  // stage event states
  ok: 'ok',
  held_for_review: 'warn',
  // source states
  success_with_results: 'ok',
  success_empty: 'muted',
  not_configured: 'muted',
  unsupported: 'muted',
  failed_permanent_source: 'danger',
};

const STATUS_LABEL: Record<string, string> = {
  completed: 'Completed',
  qualified: 'Qualified',
  needs_review: 'Needs review',
  needs_human_review: 'Needs human review',
  running: 'Running',
  rejected: 'Rejected',
  failed: 'Failed',
  failed_permanent: 'Failed (permanent)',
  blocked: 'Blocked',
  ok: 'OK',
  held_for_review: 'Held for review',
  success_with_results: 'Results returned',
  success_empty: 'No results',
  not_configured: 'Not configured',
  unsupported: 'Unsupported',
};

export function statusTone(status: string | null | undefined): Tone {
  if (!status) return 'muted';
  return STATUS_TONE[status] ?? 'muted';
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return 'Unknown';
  return STATUS_LABEL[status] ?? status.replace(/_/g, ' ');
}

export function outcomeLabel(outcome: string | null | undefined): string {
  switch (outcome) {
    case 'continue':
      return 'Continue';
    case 'needs_human_review':
      return 'Needs human review';
    case 'stopped_after_error':
      return 'Stopped after error';
    case 'rejected':
      return 'Rejected';
    case null:
    case undefined:
      return '—';
    default:
      return outcome;
  }
}

export function outcomeTone(outcome: string | null | undefined): Tone {
  switch (outcome) {
    case 'continue':
      return 'ok';
    case 'needs_human_review':
      return 'warn';
    case 'stopped_after_error':
      return 'danger';
    case 'rejected':
      return 'neutral';
    default:
      return 'neutral';
  }
}

const DATE_FMT = new Intl.DateTimeFormat('en-US', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});

const TIME_FMT = new Intl.DateTimeFormat('en-US', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return `${DATE_FMT.format(date)} · ${TIME_FMT.format(date)}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return DATE_FMT.format(date);
}

/** Duration in seconds between two ISO timestamps, e.g. "0.42s". */
export function formatDuration(started: string, finished: string | null | undefined): string {
  if (!finished) return '—';
  const from = new Date(started).getTime();
  const to = new Date(finished).getTime();
  if (Number.isNaN(from) || Number.isNaN(to) || to < from) return '—';
  const seconds = (to - from) / 1000;
  if (seconds < 0.01) return '<0.01s';
  if (seconds < 10) return `${seconds.toFixed(2)}s`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

/** One-line summary of a campaign's target settings. */
export function summarizeSettings(settings: CampaignSettings | undefined): string {
  if (!settings) return '—';
  const parts: string[] = [];
  if (settings.countries?.length) parts.push(settings.countries.join(', '));
  if (settings.sectors?.length) parts.push(settings.sectors.join(', '));
  if (settings.employee_min != null && settings.employee_max != null) {
    parts.push(`${settings.employee_min}–${settings.employee_max} employees`);
  } else {
    parts.push('size not set');
  }
  if (!settings.require_domain) parts.push('domain optional');
  return parts.join(' · ');
}

export function employeeRange(min: number | null, max: number | null): string {
  if (min == null && max == null) return 'Unknown';
  if (min != null && max != null) return `${min}–${max}`;
  if (min != null) return `${min}+`;
  return `≤${max}`;
}

/** Short, safe excerpt of a long detail string. */
export function truncate(text: string, max = 160): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

export function getQualificationLabel(status: string | null): string {
  if (!status) return 'Unknown';
  return status
    .split('_')
    .map(s => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' ');
}

export function getStatusColor(status: string | null): 'ok' | 'warn' | 'danger' | 'muted' {
  if (!status) return 'muted';
  const s = status.toLowerCase();
  if (['qualified', 'completed', 'ok', 'success_with_results', 'approved'].includes(s)) return 'ok';
  if (['needs_review', 'needs_human_review', 'held_for_review', 'pending', 'success_empty', 'not_configured', 'unsupported'].includes(s)) return 'warn';
  if (['rejected', 'failed', 'failed_permanent', 'blocked', 'error'].includes(s)) return 'danger';
  return 'muted';
}

export function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '—';
  return String(score);
}

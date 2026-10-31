import { describe, expect, it } from 'vitest';

import {
  employeeRange,
  formatDateTime,
  formatDuration,
  outcomeLabel,
  outcomeTone,
  statusLabel,
  statusTone,
  summarizeSettings,
  truncate,
} from './format';
import type { CampaignSettings } from './types';

describe('statusTone / statusLabel', () => {
  it('maps workflow states to restrained tones', () => {
    expect(statusTone('completed')).toBe('ok');
    expect(statusTone('needs_review')).toBe('warn');
    expect(statusTone('failed')).toBe('danger');
    expect(statusTone('not_configured')).toBe('muted');
  });

  it('falls back to muted for unknown states', () => {
    expect(statusTone('something_new')).toBe('muted');
    expect(statusTone(null)).toBe('muted');
    expect(statusTone(undefined)).toBe('muted');
  });

  it('turns snake_case into readable labels', () => {
    expect(statusLabel('needs_review')).toBe('Needs review');
    expect(statusLabel('not_configured')).toBe('Not configured');
    expect(statusLabel(null)).toBe('Unknown');
  });
});

describe('outcomes', () => {
  it('labels the three Milestone 1 outcomes', () => {
    expect(outcomeLabel('continue')).toBe('Continue');
    expect(outcomeLabel('needs_human_review')).toBe('Needs human review');
    expect(outcomeLabel('stopped_after_error')).toBe('Stopped after error');
    expect(outcomeLabel(null)).toBe('—');
  });

  it('tones outcomes honestly', () => {
    expect(outcomeTone('continue')).toBe('ok');
    expect(outcomeTone('needs_human_review')).toBe('warn');
    expect(outcomeTone('stopped_after_error')).toBe('danger');
  });
});

describe('formatDuration', () => {
  it('reports sub-second runs precisely', () => {
    expect(formatDuration('2026-10-20T10:00:00Z', '2026-10-20T10:00:00.420Z')).toBe('0.42s');
  });

  it('returns an em dash when the run has not finished', () => {
    expect(formatDuration('2026-10-20T10:00:00Z', null)).toBe('—');
  });

  it('rejects reversed timestamps instead of showing a negative value', () => {
    expect(formatDuration('2026-10-20T10:00:00Z', '2026-10-20T09:00:00Z')).toBe('—');
  });
});

describe('formatDateTime', () => {
  it('formats a valid ISO timestamp', () => {
    expect(formatDateTime('2026-10-20T10:05:00Z')).toMatch(
      /\w{3} \d{1,2}, \d{4} · \d{2}:\d{2}/,
    );
  });

  it('handles missing and invalid input', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('not-a-date')).toBe('—');
  });
});

describe('summarizeSettings', () => {
  const settings: CampaignSettings = {
    countries: ['United States'],
    sectors: ['software', 'data'],
    employee_min: 20,
    employee_max: 200,
    target_titles: [],
    exclusions: [],
    require_domain: true,
  };

  it('summarizes target settings on one line', () => {
    expect(summarizeSettings(settings)).toBe(
      'United States · software, data · 20–200 employees',
    );
  });

  it('marks an open size range honestly', () => {
    expect(summarizeSettings({ ...settings, employee_min: null, employee_max: null })).toBe(
      'United States · software, data · size not set',
    );
  });

  it('handles a missing settings object', () => {
    expect(summarizeSettings(undefined)).toBe('—');
  });
});

describe('employeeRange and truncate', () => {
  it('shows unknown as unknown', () => {
    expect(employeeRange(null, null)).toBe('Unknown');
  });

  it('shows a range when both bounds exist', () => {
    expect(employeeRange(20, 50)).toBe('20–50');
  });

  it('truncates long text with an ellipsis', () => {
    expect(truncate('abcdef', 4)).toBe('abc…');
    expect(truncate('abc', 4)).toBe('abc');
  });
});

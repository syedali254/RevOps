import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api, ApiError, API_BASE } from './api';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('api client', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses a localhost backend base URL by default', () => {
    expect(API_BASE).toMatch(/^https?:\/\/(127\.0\.0\.1|localhost):\d+$/);
  });

  it('parses a successful JSON response', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 'ok' }));
    await expect(api.health()).resolves.toEqual({ status: 'ok' });
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/health`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it('throws ApiError carrying the backend detail message', async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: 'Campaign not found' }, 404));
    await expect(api.getCampaign(9)).rejects.toBeInstanceOf(ApiError);
    await expect(api.getCampaign(9)).rejects.toMatchObject({
      status: 404,
      detail: 'Campaign not found',
    });
  });

  it('joins FastAPI validation arrays into one readable message', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: [{ msg: 'field required' }, { msg: 'too short' }] }, 422),
    );
    await expect(api.createCampaign({ name: '', settings: null as never })).rejects.toMatchObject(
      { status: 422, detail: 'field required; too short' },
    );
  });

  it('explains a connection failure instead of returning an empty result', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api.overview()).rejects.toMatchObject({
      status: 0,
      detail: expect.stringContaining('Cannot reach the backend'),
    });
  });

  it('sends JSON bodies for mutations', async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ id: 1 }, 201));
    await api.createRun({ campaign_id: 3, company: { canonical_name: 'Acme' } });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(init.body).toContain('"canonical_name":"Acme"');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });
});

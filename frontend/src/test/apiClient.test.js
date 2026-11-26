import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, apiCall } from '../api/apiClient.js';

const okResponse = () => ({ ok: true, status: 200, json: async () => ({ ok: true }) });

describe('apiCall', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('injects the session token as a Bearer Authorization header and returns the Response', async () => {
    sessionStorage.setItem('fide_token', 'tok-123');
    const response = okResponse();
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal('fetch', fetchMock);

    const result = await apiCall('/api/protected');

    expect(result).toBe(response);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/protected');
    expect(options.headers).toEqual({ Authorization: 'Bearer tok-123' });
    expect(options.signal).toBeInstanceOf(AbortSignal);
    expect(options.signal.aborted).toBe(false);
  });

  it('does not invent an Authorization header when no token is stored', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal('fetch', fetchMock);

    await apiCall('/api/public');

    expect(fetchMock.mock.calls[0][1].headers).toEqual({});
  });

  it('aborts the request when the configured timeout elapses', async () => {
    vi.useFakeTimers();
    let internalSignal;
    const fetchMock = vi.fn((_url, options) => {
      internalSignal = options.signal;
      return new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          reject(new DOMException('Aborted', 'AbortError'));
        });
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const pending = apiCall('/api/slow', { timeout: 250 });
    // Attach the rejection handler before advancing timers so the aborted
    // fetch promise is never reported as an unhandled rejection.
    const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' });

    await vi.advanceTimersByTimeAsync(249);
    expect(internalSignal.aborted).toBe(false);

    await vi.advanceTimersByTimeAsync(1);
    await rejected;
    expect(internalSignal.aborted).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('api.login keeps its explicit urlencoded Content-Type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal('fetch', fetchMock);

    await api.login('username=test&password=test');

    expect(fetchMock.mock.calls[0][1].headers['Content-Type']).toBe('application/x-www-form-urlencoded');
  });

  it('propagates a caller-supplied AbortSignal to the outgoing request', async () => {
    const response = okResponse();
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal('fetch', fetchMock);
    const external = new AbortController();

    const pending = apiCall('/api/cancellable', { signal: external.signal });
    const internalSignal = fetchMock.mock.calls[0][1].signal;
    expect(internalSignal.aborted).toBe(false);

    external.abort();
    expect(internalSignal.aborted).toBe(true);
    await expect(pending).resolves.toBe(response);
  });
});

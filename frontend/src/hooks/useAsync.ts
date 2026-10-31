import { useCallback, useEffect, useState, type DependencyList } from 'react';

import { ApiError } from '../lib/api';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Minimal data-fetching hook with honest loading / error / empty states.
 * `reload()` re-runs the same loader (used by retry buttons and after mutations).
 */
export function useAsync<T>(loader: () => Promise<T>, deps: DependencyList = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    loader()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setData(null);
        setLoading(false);
        setError(cause instanceof ApiError ? cause.detail : String(cause));
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  return { data, loading, error, reload };
}

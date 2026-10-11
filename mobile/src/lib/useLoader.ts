import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

import { ApiError } from './api';

/** Loads data whenever the screen gains focus; exposes loading/error/refresh for consistent status UI. */
export function useLoader<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    setError(null);
    try {
      setData(await fnRef.current());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useFocusEffect(
    useCallback(() => {
      run();
    }, [run]),
  );

  return { data, setData, error, loading, refreshing, reload: () => run(), refresh: () => run(true) };
}

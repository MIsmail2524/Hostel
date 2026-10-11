import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, getRefreshToken, onSessionChange, refreshSession, setSession } from './api';
import { getSecure, setSecure } from './secure';
import type { TokenResponse, User } from './types';

const KEY = 'kamra.refresh';

interface AuthCtx {
  user: User | null;
  ready: boolean;
  login: (identifier: string, password: string) => Promise<User>;
  register: (data: { full_name: string; email?: string; phone?: string; password: string; is_owner: boolean }) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
  reload: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    onSessionChange((s, u) => {
      setSecure(KEY, s?.refresh ?? null);
      if (!s) setUser(null);
      else if (u) setUser(u);
    });
    (async () => {
      const refresh = await getSecure(KEY);
      if (refresh) {
        setSession({ access: '', refresh });
        await refreshSession();
      }
      setReady(true);
    })();
  }, []);

  const accept = useCallback(async (t: TokenResponse) => {
    setSession({ access: t.access_token, refresh: t.refresh_token });
    await setSecure(KEY, t.refresh_token);
    setUser(t.user);
    return t.user;
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      ready,
      login: async (identifier, password) => accept(await api<TokenResponse>('/auth/login', { body: { identifier, password } })),
      register: async (data) => accept(await api<TokenResponse>('/auth/register', { body: data })),
      logout: async () => {
        const rt = getRefreshToken();
        if (rt) await api('/auth/logout', { body: { refresh_token: rt } }).catch(() => undefined);
        setSession(null);
        await setSecure(KEY, null);
        setUser(null);
      },
      setUser,
      reload: async () => setUser(await api<User>('/me')),
    }),
    [user, ready, accept],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth outside AuthProvider');
  return c;
}

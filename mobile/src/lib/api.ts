import Constants from 'expo-constants';
import { Platform } from 'react-native';

import type { TokenResponse } from './types';

const configured = process.env.EXPO_PUBLIC_API_URL ?? (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl;
// Android emulator reaches the host machine via 10.0.2.2
export const API_URL = (configured ?? (Platform.OS === 'android' ? 'http://10.0.2.2:8090' : 'http://localhost:8090')).replace(/\/$/, '');

export function mediaUrl(u?: string | null): string | undefined {
  if (!u) return undefined;
  return /^https?:\/\//.test(u) ? u : `${API_URL}${u}`;
}

export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;
  constructor(message: string, status: number, fields: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

type Session = { access: string; refresh: string } | null;
let session: Session = null;
let refreshing: Promise<boolean> | null = null;
let onSession: (s: Session, user?: TokenResponse['user']) => void = () => {};

export function setSession(s: Session) {
  session = s;
}
export function onSessionChange(cb: typeof onSession) {
  onSession = cb;
}
export function getRefreshToken() {
  return session?.refresh ?? null;
}

async function doRefresh(): Promise<boolean> {
  if (!session?.refresh) return false;
  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refresh }),
    });
    if (!res.ok) {
      session = null;
      onSession(null);
      return false;
    }
    const data = (await res.json()) as TokenResponse;
    session = { access: data.access_token, refresh: data.refresh_token };
    onSession(session, data.user);
    return true;
  } catch {
    return false; // network error: keep session, caller surfaces the error
  }
}

export function refreshSession(): Promise<boolean> {
  if (!refreshing) refreshing = doRefresh().finally(() => (refreshing = null));
  return refreshing;
}

interface Opts {
  method?: string;
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | boolean | string[] | undefined | null>;
  timeoutMs?: number;
}

function qs(query: Opts['query']) {
  if (!query) return '';
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === '' || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.append(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}

export async function api<T = unknown>(path: string, opts: Opts = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (session?.access) headers.Authorization = `Bearer ${session.access}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 30000);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}${qs(opts.query)}`, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, signal: ctrl.signal });
  } catch (e) {
    throw new ApiError(ctrl.signal.aborted ? 'The request timed out. Please try again.' : 'Can’t reach Kamra. Check your internet connection.', 0);
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401 && session?.refresh && !retried && !path.startsWith('/auth/')) {
    if (await refreshSession()) return api<T>(path, opts, true);
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const fields: Record<string, string> = {};
    for (const e of data?.errors ?? []) if (e.field) fields[e.field] = e.message;
    const msg = typeof data?.detail === 'string' ? data.detail : res.status === 429 ? 'Too many attempts. Please wait a minute.' : 'Something went wrong. Please try again.';
    throw new ApiError(msg, res.status, fields);
  }
  return data as T;
}

/** Append a picked file (native uri or web File) to FormData. */
export async function appendFile(form: FormData, field: string, asset: { uri: string; mimeType?: string | null; fileName?: string | null; file?: File }) {
  if (Platform.OS === 'web') {
    if (asset.file) {
      form.append(field, asset.file);
    } else {
      const blob = await (await fetch(asset.uri)).blob();
      form.append(field, blob, asset.fileName ?? 'upload');
    }
    return;
  }
  const type = asset.mimeType ?? (asset.uri.endsWith('.mp4') || asset.uri.endsWith('.mov') ? 'video/mp4' : 'image/jpeg');
  // React Native's FormData accepts {uri, name, type}
  form.append(field, { uri: asset.uri, name: asset.fileName ?? `upload.${type.split('/')[1]}`, type } as unknown as Blob);
}

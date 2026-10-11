import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { Banner, Button, Field, H1, P, Screen } from '../../components/ui';
import { api, ApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { space } from '../../lib/theme';
import type { User } from '../../lib/types';

export default function Verify() {
  const { user, setUser } = useAuth();
  const [code, setCode] = useState('');
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    setError(null);
    try {
      const r = await api<{ sent_to?: string; dev_code?: string; already_verified?: boolean }>('/auth/otp/request', { method: 'POST' });
      if (r.already_verified) return router.back();
      setSentTo(r.sent_to ?? null);
      setDevCode(r.dev_code ?? null);
      setCooldown(45);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send the code');
    }
  };

  useEffect(() => {
    if (user && !user.contact_verified) send();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const verify = async () => {
    setBusy(true);
    setError(null);
    try {
      const u = await api<User>('/auth/otp/verify', { body: { code } });
      setUser(u);
      if (router.canGoBack()) router.back();
      else router.replace('/');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Verification failed');
    } finally {
      setBusy(false);
    }
  };

  if (!user) {
    return (
      <Screen>
        <Banner text="Please log in first." />
        <Button title="Log in" onPress={() => router.replace('/auth/login')} />
      </Screen>
    );
  }

  return (
    <Screen style={{ maxWidth: 480, width: '100%', alignSelf: 'center' }}>
      <View style={{ gap: space.xs }}>
        <H1>Enter the 6-digit code</H1>
        <P muted>{sentTo ? `We sent it to ${sentTo}.` : 'Sending your code…'} Verified accounts keep Kamra free of fake listings.</P>
      </View>
      {devCode ? <Banner tone="primary" text={`Development mode — your code is ${devCode}`} /> : null}
      {error ? <Banner text={error} /> : null}
      <Field
        label="Verification code"
        value={code}
        onChangeText={(v) => setCode(v.replace(/\D/g, '').slice(0, 6))}
        keyboardType="number-pad"
        autoComplete="one-time-code"
        textContentType="oneTimeCode"
        maxLength={6}
        placeholder="••••••"
        style={{ letterSpacing: 8, fontSize: 22 }}
        onSubmitEditing={verify}
      />
      <Button title="Verify" onPress={verify} loading={busy} disabled={code.length !== 6} />
      <Button title={cooldown ? `Resend code in ${cooldown}s` : 'Resend code'} variant="ghost" disabled={cooldown > 0} onPress={send} />
      <Button title="Do this later" variant="ghost" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
    </Screen>
  );
}

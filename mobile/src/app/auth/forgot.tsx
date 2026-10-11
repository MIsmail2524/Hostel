import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Banner, Button, Field, H1, P, Screen } from '../../components/ui';
import { api, ApiError } from '../../lib/api';
import { space } from '../../lib/theme';

export default function Forgot() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [devCode, setDevCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ dev_code?: string }>('/auth/password/forgot', { body: { identifier: identifier.trim() } });
      setDevCode(r.dev_code ?? null);
      setStep(2);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send the code');
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    setError(null);
    try {
      await api('/auth/password/reset', { body: { identifier: identifier.trim(), code, new_password: password } });
      setStep(3);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Reset failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen style={{ maxWidth: 480, width: '100%', alignSelf: 'center' }}>
      <View style={{ gap: space.xs }}>
        <H1>{step === 3 ? 'Password updated' : 'Reset your password'}</H1>
        <P muted>{step === 1 ? 'Enter the phone or email on your account. We’ll send a code.' : step === 2 ? 'Enter the code and choose a new password.' : 'You can now log in with your new password. Other devices were signed out.'}</P>
      </View>
      {error ? <Banner text={error} /> : null}
      {step === 1 ? (
        <>
          <Field label="Phone or email" value={identifier} onChangeText={setIdentifier} autoCapitalize="none" keyboardType="email-address" />
          <Button title="Send code" onPress={request} loading={busy} disabled={identifier.trim().length < 3} />
        </>
      ) : step === 2 ? (
        <>
          {devCode ? <Banner tone="primary" text={`Development mode — your code is ${devCode}`} /> : null}
          <Field label="6-digit code" value={code} onChangeText={(v) => setCode(v.replace(/\D/g, '').slice(0, 6))} keyboardType="number-pad" autoComplete="one-time-code" />
          <Field label="New password" value={password} onChangeText={setPassword} secureTextEntry autoComplete="new-password" hint="At least 8 characters, mix letters with numbers or symbols" />
          <Button title="Update password" onPress={reset} loading={busy} disabled={code.length !== 6 || password.length < 8} />
        </>
      ) : (
        <Button title="Go to login" onPress={() => router.replace('/auth/login')} />
      )}
    </Screen>
  );
}

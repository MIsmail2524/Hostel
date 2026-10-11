import { Link, router } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, TextInput, View } from 'react-native';

import { Banner, Button, Field, H1, Ionicons, P, Screen } from '../../components/ui';
import { ApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { space, useColors } from '../../lib/theme';

export default function Login() {
  const c = useColors();
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pwRef = useRef<TextInput>(null);

  const submit = async () => {
    if (!identifier.trim() || !password) return setError('Enter your phone/email and password');
    setBusy(true);
    setError(null);
    try {
      const u = await login(identifier.trim(), password);
      if (router.canGoBack()) router.back();
      else router.replace('/');
      if (!u.contact_verified) router.push('/auth/verify');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen style={{ maxWidth: 480, width: '100%', alignSelf: 'center' }}>
        <View style={{ gap: space.xs }}>
          <H1>Welcome back</H1>
          <P muted>Log in to message owners, save places and request visits.</P>
        </View>
        {error ? <Banner text={error} /> : null}
        <Field
          label="Phone or email"
          value={identifier}
          onChangeText={setIdentifier}
          placeholder="03001234567 or you@example.com"
          autoCapitalize="none"
          autoComplete="username"
          textContentType="username"
          keyboardType="email-address"
          returnKeyType="next"
          onSubmitEditing={() => pwRef.current?.focus()}
        />
        <Field
          ref={pwRef}
          label="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry={!show}
          autoComplete="current-password"
          textContentType="password"
          returnKeyType="go"
          onSubmitEditing={submit}
          right={
            <Pressable accessibilityRole="button" accessibilityLabel={show ? 'Hide password' : 'Show password'} onPress={() => setShow(!show)} hitSlop={10}>
              <Ionicons name={show ? 'eye-off-outline' : 'eye-outline'} size={20} color={c.muted} />
            </Pressable>
          }
        />
        <Button title="Log in" onPress={submit} loading={busy} />
        <Link href="/auth/forgot" style={{ color: c.primary, fontWeight: '700', textAlign: 'center', padding: space.sm }}>
          Forgot password?
        </Link>
        <Button title="Create a new account" variant="secondary" onPress={() => router.replace('/auth/register')} />
      </Screen>
    </KeyboardAvoidingView>
  );
}

import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, Text, View } from 'react-native';

import { Banner, Button, Card, Field, H1, Ionicons, P, Row, Screen } from '../../components/ui';
import { ApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { font, space, useColors } from '../../lib/theme';

function strength(pw: string) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(4, s);
}

export default function Register() {
  const c = useColors();
  const { register } = useAuth();
  const [role, setRole] = useState<'seeker' | 'owner'>('seeker');
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const s = strength(password);
  const labels = ['Too weak', 'Weak', 'Okay', 'Good', 'Strong'];
  const colors = [c.danger, c.danger, c.warning, c.success, c.success];

  const submit = async () => {
    const f: Record<string, string> = {};
    if (name.trim().length < 2) f.full_name = 'Enter your name';
    if (!contact.trim()) f.contact = 'Enter your phone number or email';
    if (password.length < 8) f.password = 'Use at least 8 characters';
    setFields(f);
    if (Object.keys(f).length) return;
    setBusy(true);
    setError(null);
    const isEmail = contact.includes('@');
    try {
      await register({ full_name: name.trim(), ...(isEmail ? { email: contact.trim() } : { phone: contact.trim() }), password, is_owner: role === 'owner' });
      router.replace('/auth/verify');
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        setFields({ ...e.fields, ...(e.fields.phone || e.fields.email ? { contact: e.fields.phone ?? e.fields.email } : {}) });
      } else setError('Could not create your account');
    } finally {
      setBusy(false);
    }
  };

  const RoleCard = ({ value, icon, title, body }: { value: 'seeker' | 'owner'; icon: 'search' | 'home'; title: string; body: string }) => (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ checked: role === value }}
      accessibilityLabel={`${title}. ${body}`}
      onPress={() => setRole(value)}
      style={{ flex: 1 }}
    >
      <Card style={{ borderColor: role === value ? c.primary : c.border, borderWidth: 2, minHeight: 120 }}>
        <Ionicons name={icon} size={24} color={role === value ? c.primary : c.muted} />
        <Text style={{ fontWeight: '800', color: c.text, fontSize: font.md }}>{title}</Text>
        <Text style={{ color: c.muted, fontSize: font.sm }}>{body}</Text>
      </Card>
    </Pressable>
  );

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen style={{ maxWidth: 480, width: '100%', alignSelf: 'center' }}>
        <View style={{ gap: space.xs }}>
          <H1>Join Kamra</H1>
          <P muted>Safe, verified rooms and beds — no more WhatsApp group hunting.</P>
        </View>
        {error ? <Banner text={error} /> : null}
        <View accessibilityRole="radiogroup" style={{ gap: space.sm }}>
          <Text style={{ fontWeight: '600', color: c.text }}>I want to…</Text>
          <Row gap={space.md} style={{ alignItems: 'stretch' }}>
            <RoleCard value="seeker" icon="search" title="Find a place" body="Rooms, beds & hostel seats" />
            <RoleCard value="owner" icon="home" title="List my space" body="Hostel, flat or spare room" />
          </Row>
        </View>
        <Field label="Full name" value={name} onChangeText={setName} autoComplete="name" textContentType="name" error={fields.full_name} />
        <Field
          label="Phone number or email"
          value={contact}
          onChangeText={setContact}
          placeholder="03001234567"
          autoCapitalize="none"
          keyboardType="email-address"
          autoComplete="email"
          error={fields.contact}
          hint="We’ll send a 6-digit code to verify it. It’s never shown publicly."
        />
        <Field
          label="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry={!show}
          autoComplete="new-password"
          textContentType="newPassword"
          error={fields.password}
          right={
            <Pressable accessibilityRole="button" accessibilityLabel={show ? 'Hide password' : 'Show password'} onPress={() => setShow(!show)} hitSlop={10}>
              <Ionicons name={show ? 'eye-off-outline' : 'eye-outline'} size={20} color={c.muted} />
            </Pressable>
          }
        />
        {password ? (
          <View accessibilityLabel={`Password strength: ${labels[s]}`} style={{ gap: 4 }}>
            <Row gap={4}>
              {[0, 1, 2, 3].map((i) => (
                <View key={i} style={{ flex: 1, height: 5, borderRadius: 3, backgroundColor: i < s ? colors[s] : c.surfaceAlt }} />
              ))}
            </Row>
            <Text style={{ color: colors[s], fontSize: font.xs, fontWeight: '700' }}>{labels[s]} — mix letters, numbers & symbols</Text>
          </View>
        ) : null}
        <Button title="Create account" onPress={submit} loading={busy} />
        <P muted style={{ fontSize: font.xs, textAlign: 'center' }}>By continuing you agree to Kamra’s Terms and Privacy Policy.</P>
        <Button title="I already have an account" variant="ghost" onPress={() => router.replace('/auth/login')} />
      </Screen>
    </KeyboardAvoidingView>
  );
}

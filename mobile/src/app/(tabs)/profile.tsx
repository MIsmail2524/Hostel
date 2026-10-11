import { router } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { Badge, Banner, Button, Card, Empty, Field, H1, Ionicons, P, Row, Screen } from '../../components/ui';
import { api, ApiError, API_URL, setSession } from '../../lib/api';
import { confirm } from '../../lib/confirm';
import { useAuth } from '../../lib/auth';
import { font, space, useColors } from '../../lib/theme';
import type { User } from '../../lib/types';

export default function Profile() {
  const c = useColors();
  const { user, logout, setUser } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [delPw, setDelPw] = useState('');

  if (!user)
    return (
      <Screen>
        <Empty
          icon="person-circle-outline"
          title="Your Kamra account"
          body="Log in to message owners, request visits, or list your own room, bed or hostel."
          action={
            <View style={{ gap: space.sm, alignSelf: 'stretch' }}>
              <Button title="Log in" onPress={() => router.push('/auth/login')} />
              <Button title="Create account" variant="secondary" onPress={() => router.push('/auth/register')} />
            </View>
          }
        />
      </Screen>
    );

  const toggleOwner = async () => {
    setBusy(true);
    setError(null);
    try {
      setUser(await api<User>('/me', { method: 'PATCH', body: { is_owner: !user.is_owner } }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not update');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen style={{ maxWidth: 720, width: '100%', alignSelf: 'center' }}>
      <Row gap={space.md}>
        <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: c.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ fontSize: font.xxl, fontWeight: '800', color: c.primary }}>{user.full_name[0]}</Text>
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <H1>{user.full_name}</H1>
          <Row wrap>
            {user.contact_verified ? <Badge label="Verified contact" icon="checkmark-circle" tone="success" /> : <Badge label="Not verified" tone="warning" />}
            {user.is_owner ? <Badge label="Owner" tone="primary" /> : null}
            {user.is_verified_owner ? <Badge label="Verified owner" icon="shield-checkmark" tone="success" /> : null}
            {user.is_admin ? <Badge label="Admin" tone="danger" /> : null}
          </Row>
        </View>
      </Row>
      {error ? <Banner text={error} /> : null}
      {!user.contact_verified ? (
        <Card onPress={() => router.push('/auth/verify')} accessibilityLabel="Verify your phone or email">
          <Row>
            <Ionicons name="alert-circle" size={22} color={c.warning} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontWeight: '700', color: c.text }}>Verify your {user.phone ? 'phone' : 'email'}</Text>
              <P muted>Needed before you can message owners or publish a listing.</P>
            </View>
            <Ionicons name="chevron-forward" size={18} color={c.subtle} />
          </Row>
        </Card>
      ) : null}
      <Card>
        <P muted>{user.phone ?? user.email}</P>
        <P muted>Your contact details are private — owners and seekers talk through Kamra chat.</P>
      </Card>
      <Card>
        <Text style={{ fontWeight: '700', color: c.text, fontSize: font.md }}>{user.is_owner ? 'You can list spaces' : 'Have a room, bed or hostel to rent?'}</Text>
        <P muted>{user.is_owner ? 'Manage your listings and 3D tours from the “My listings” tab.' : 'Switch on owner tools to list it with a free 3D tour.'}</P>
        <Button title={user.is_owner ? 'Turn off owner tools' : 'Start listing'} variant={user.is_owner ? 'secondary' : 'primary'} loading={busy} onPress={toggleOwner} />
      </Card>
      <Button title="Visit requests" icon="calendar-outline" variant="secondary" onPress={() => router.push('/visits')} />
      {user.is_admin ? <Button title="Moderation queue" icon="shield-outline" variant="secondary" onPress={() => router.push('/admin')} /> : null}
      <Button
        title="Log out"
        icon="log-out-outline"
        variant="ghost"
        onPress={async () => {
          await logout();
          router.replace('/');
        }}
      />
      {deleting ? (
        <Card style={{ borderColor: c.danger }}>
          <Text style={{ fontWeight: '700', color: c.danger, fontSize: font.md }}>Delete your account</Text>
          <P muted>This permanently removes your profile, listings, photos, 3D tours and chats.</P>
          <Field label="Confirm with your password" value={delPw} onChangeText={setDelPw} secureTextEntry autoComplete="current-password" />
          <Row gap={space.md}>
            <Button title="Cancel" variant="secondary" style={{ flex: 1 }} onPress={() => { setDeleting(false); setDelPw(''); }} />
            <Button
              title="Delete forever"
              variant="danger"
              style={{ flex: 1 }}
              disabled={!delPw}
              loading={busy}
              onPress={async () => {
                if (!(await confirm('Delete account?', 'This cannot be undone.', 'Delete', true))) return;
                setBusy(true);
                setError(null);
                try {
                  await api('/me/delete', { body: { password: delPw } });
                  setSession(null);
                  await logout();
                  router.replace('/');
                } catch (e) {
                  setError(e instanceof ApiError ? e.message : 'Could not delete account');
                } finally {
                  setBusy(false);
                }
              }}
            />
          </Row>
        </Card>
      ) : (
        <Button title="Delete account" icon="trash-outline" variant="ghost" onPress={() => setDeleting(true)} />
      )}
      <P muted style={{ fontSize: font.xs, textAlign: 'center' }}>Kamra v1.0 · {API_URL.replace(/^https?:\/\//, '')}</P>
    </Screen>
  );
}

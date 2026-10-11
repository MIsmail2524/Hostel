import { router } from 'expo-router';
import { useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';

import { Badge, Banner, Button, Card, Empty, Loading, P, Row } from '../components/ui';
import { api, ApiError } from '../lib/api';
import { dateTime } from '../lib/format';
import { font, space, useColors } from '../lib/theme';
import type { Visit } from '../lib/types';
import { useLoader } from '../lib/useLoader';

const TONE = { pending: 'warning', accepted: 'success', declined: 'danger', cancelled: 'neutral' } as const;

export default function Visits() {
  const c = useColors();
  const { data, setData, error, loading, refreshing, refresh, reload } = useLoader(() => api<Visit[]>('/visits'));
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const update = async (v: Visit, status: 'accepted' | 'declined' | 'cancelled') => {
    setBusy(v.id + status);
    setNotice(null);
    try {
      const nv = await api<Visit>(`/visits/${v.id}`, { method: 'PATCH', body: { status } });
      setData((d) => (d ?? []).map((x) => (x.id === v.id ? nv : x)));
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : 'Could not update');
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: c.bg }}
      data={data ?? []}
      keyExtractor={(v) => v.id}
      contentContainerStyle={{ padding: space.lg, gap: space.md, maxWidth: 720, width: '100%', alignSelf: 'center' }}
      ListHeaderComponent={error || notice ? <Banner text={(error ?? notice)!} onRetry={error ? reload : undefined} /> : null}
      renderItem={({ item: v }) => (
        <Card>
          <Row style={{ justifyContent: 'space-between' }}>
            <Text style={{ fontWeight: '700', color: c.text, fontSize: font.md, flex: 1 }} numberOfLines={1} onPress={() => router.push(`/listing/${v.listing_id}`)}>
              {v.listing_title}
            </Text>
            <Badge label={v.status[0].toUpperCase() + v.status.slice(1)} tone={TONE[v.status]} />
          </Row>
          <P muted>
            {dateTime(v.proposed_at)} · {v.role === 'owner' ? `Requested by ${v.seeker.full_name}` : 'Your request'}
          </P>
          {v.note ? <P>“{v.note}”</P> : null}
          {v.address_line ? <Banner tone="success" icon="location" text={`Address: ${v.address_line}`} /> : null}
          {v.role === 'owner' && v.status === 'pending' ? (
            <Row gap={space.md}>
              <Button title="Decline" variant="secondary" style={{ flex: 1 }} loading={busy === v.id + 'declined'} onPress={() => update(v, 'declined')} />
              <Button title="Accept" style={{ flex: 1 }} loading={busy === v.id + 'accepted'} onPress={() => update(v, 'accepted')} accessibilityHint="Shares the exact address with this person" />
            </Row>
          ) : null}
          {v.role === 'seeker' && (v.status === 'pending' || v.status === 'accepted') ? (
            <Button title="Cancel visit" variant="ghost" loading={busy === v.id + 'cancelled'} onPress={() => update(v, 'cancelled')} />
          ) : null}
        </Card>
      )}
      ListEmptyComponent={<View><Empty icon="calendar-outline" title="No visit requests" body="Request a visit from any listing. Owners see requests here." /></View>}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.primary} />}
    />
  );
}

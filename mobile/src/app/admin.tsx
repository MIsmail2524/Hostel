import { router } from 'expo-router';
import { useState } from 'react';
import { FlatList, RefreshControl, View } from 'react-native';

import { ListingCard } from '../components/ListingCard';
import { Banner, Button, Empty, Field, Loading, Row } from '../components/ui';
import { api, ApiError } from '../lib/api';
import { space, useColors } from '../lib/theme';
import type { ListingCard as Card } from '../lib/types';
import { useLoader } from '../lib/useLoader';

export default function Admin() {
  const c = useColors();
  const { data, setData, error, loading, refreshing, refresh, reload } = useLoader(() => api<Card[]>('/admin/listings/pending'));
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const moderate = async (id: string, action: 'approve' | 'reject') => {
    setBusy(id + action);
    setNotice(null);
    try {
      await api(`/admin/listings/${id}/moderate`, { body: { action, reason: reasons[id] || null } });
      setData((d) => (d ?? []).filter((x) => x.id !== id));
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : 'Failed');
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: c.bg }}
      data={data ?? []}
      keyExtractor={(i) => i.id}
      contentContainerStyle={{ padding: space.lg, gap: space.lg, maxWidth: 720, width: '100%', alignSelf: 'center' }}
      ListHeaderComponent={error || notice ? <Banner text={(error ?? notice)!} onRetry={error ? reload : undefined} /> : null}
      renderItem={({ item }) => (
        <View style={{ gap: space.sm }}>
          <ListingCard item={item} showStatus onPress={() => router.push(`/listing/${item.id}`)} />
          <Field label="Reason (required to reject)" value={reasons[item.id] ?? ''} onChangeText={(v) => setReasons({ ...reasons, [item.id]: v })} placeholder="e.g. Photos are blurry; add a clear photo of the room" />
          <Row gap={space.md}>
            <Button title="Reject" variant="danger" style={{ flex: 1 }} disabled={!reasons[item.id]} loading={busy === item.id + 'reject'} onPress={() => moderate(item.id, 'reject')} />
            <Button title="Approve" style={{ flex: 1 }} loading={busy === item.id + 'approve'} onPress={() => moderate(item.id, 'approve')} />
          </Row>
        </View>
      )}
      ListEmptyComponent={<Empty icon="checkmark-done-outline" title="All caught up" body="No listings waiting for review." />}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.primary} />}
    />
  );
}

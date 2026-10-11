import { router } from 'expo-router';
import { FlatList, Image, Pressable, RefreshControl, Text, View } from 'react-native';

import { Badge, Banner, Button, Card, Empty, Ionicons, Loading, Row } from '../../components/ui';
import { api, mediaUrl } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { ago } from '../../lib/format';
import { font, radius, space, useColors } from '../../lib/theme';
import type { Conversation, Visit } from '../../lib/types';
import { useLoader } from '../../lib/useLoader';

export default function Inbox() {
  const c = useColors();
  const { user } = useAuth();
  const { data, error, loading, refreshing, refresh, reload } = useLoader(
    async () => {
      if (!user) return { convs: [] as Conversation[], visits: [] as Visit[] };
      const [convs, visits] = await Promise.all([api<Conversation[]>('/conversations'), api<Visit[]>('/visits')]);
      return { convs, visits };
    },
    [user?.id],
  );

  if (!user)
    return (
      <View style={{ flex: 1, backgroundColor: c.bg }}>
        <Empty icon="chatbubbles-outline" title="Chat safely with owners" body="Your number stays private. Log in to see your messages." action={<Button title="Log in" onPress={() => router.push('/auth/login')} />} />
      </View>
    );
  if (loading) return <Loading />;
  const pendingVisits = (data?.visits ?? []).filter((v) => v.status === 'pending' && v.role === 'owner').length;

  return (
    <FlatList
      style={{ backgroundColor: c.bg }}
      data={data?.convs ?? []}
      keyExtractor={(i) => i.id}
      contentContainerStyle={{ padding: space.lg, gap: space.md, maxWidth: 720, width: '100%', alignSelf: 'center' }}
      ListHeaderComponent={
        <View style={{ gap: space.md }}>
          {error ? <Banner text={error} onRetry={reload} /> : null}
          <Card onPress={() => router.push('/visits')} accessibilityLabel={`Visit requests${pendingVisits ? `, ${pendingVisits} waiting for you` : ''}`}>
            <Row style={{ justifyContent: 'space-between' }}>
              <Row>
                <Ionicons name="calendar" size={22} color={c.primary} />
                <Text style={{ fontWeight: '700', color: c.text, fontSize: font.md }}>Visit requests</Text>
              </Row>
              <Row>
                {pendingVisits ? <Badge label={`${pendingVisits} to answer`} tone="warning" /> : <Text style={{ color: c.muted }}>{data?.visits.length ?? 0}</Text>}
                <Ionicons name="chevron-forward" size={18} color={c.subtle} />
              </Row>
            </Row>
          </Card>
        </View>
      }
      renderItem={({ item }) => (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Chat with ${item.other_party.full_name} about ${item.listing_title}${item.unread ? `, ${item.unread} unread` : ''}`}
          onPress={() => router.push(`/chat/${item.id}`)}
          style={({ pressed }) => ({ flexDirection: 'row', gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, opacity: pressed ? 0.9 : 1 })}
        >
          {item.listing_cover_url ? <Image source={{ uri: mediaUrl(item.listing_cover_url) }} style={{ width: 56, height: 56, borderRadius: radius.md }} /> : <View style={{ width: 56, height: 56, borderRadius: radius.md, backgroundColor: c.surfaceAlt }} />}
          <View style={{ flex: 1, gap: 2 }}>
            <Row style={{ justifyContent: 'space-between' }}>
              <Text numberOfLines={1} style={{ fontWeight: item.unread ? '800' : '600', color: c.text, flex: 1, fontSize: font.md }}>
                {item.other_party.full_name}
              </Text>
              <Text style={{ color: c.subtle, fontSize: font.xs }}>{ago(item.last_message_at)}</Text>
            </Row>
            <Text numberOfLines={1} style={{ color: c.muted, fontSize: font.sm }}>{item.listing_title}</Text>
            <Row style={{ justifyContent: 'space-between' }}>
              <Text numberOfLines={1} style={{ color: item.unread ? c.text : c.subtle, fontSize: font.sm, flex: 1, fontWeight: item.unread ? '700' : '400' }}>
                {item.last_message}
              </Text>
              {item.unread ? <Badge label={String(item.unread)} tone="primary" /> : null}
            </Row>
          </View>
        </Pressable>
      )}
      ListEmptyComponent={<Empty icon="chatbubbles-outline" title="No conversations yet" body="Message an owner from any listing — your phone number stays private." />}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.primary} />}
    />
  );
}

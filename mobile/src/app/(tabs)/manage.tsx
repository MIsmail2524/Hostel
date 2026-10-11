import { router } from 'expo-router';
import { FlatList, RefreshControl, View } from 'react-native';

import { ListingCard } from '../../components/ListingCard';
import { Banner, Button, Empty, Loading } from '../../components/ui';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { space, useColors } from '../../lib/theme';
import type { ListingCard as Card } from '../../lib/types';
import { useLoader } from '../../lib/useLoader';

export default function Manage() {
  const c = useColors();
  const { user } = useAuth();
  const { data, error, loading, refreshing, refresh, reload } = useLoader<Card[]>(() => (user ? api<Card[]>('/listings/mine') : Promise.resolve([])), [user?.id]);
  if (!user) return <Empty icon="home-outline" title="Log in to manage listings" action={<Button title="Log in" onPress={() => router.push('/auth/login')} />} />;
  if (loading) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: c.bg }}
      data={data ?? []}
      keyExtractor={(i) => i.id}
      contentContainerStyle={{ padding: space.lg, gap: space.lg, maxWidth: 720, width: '100%', alignSelf: 'center' }}
      ListHeaderComponent={
        <View style={{ gap: space.md }}>
          {error ? <Banner text={error} onRetry={reload} /> : null}
          {!user.contact_verified ? <Banner tone="warning" text="Verify your phone/email before publishing." onRetry={() => router.push('/auth/verify')} /> : null}
          <Button title="List a new space" icon="add-circle-outline" onPress={() => (user.contact_verified ? router.push('/listing/edit') : router.push('/auth/verify'))} />
        </View>
      }
      renderItem={({ item }) => <ListingCard item={item} showStatus onPress={() => router.push(`/manage/${item.id}`)} />}
      ListEmptyComponent={<Empty icon="home-outline" title="No listings yet" body="List a bed, room or hostel seat in a few minutes — and add a free 3D tour." />}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.primary} />}
    />
  );
}

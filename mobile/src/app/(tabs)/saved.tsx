import { router } from 'expo-router';
import { FlatList, RefreshControl, View } from 'react-native';

import { ListingCard } from '../../components/ListingCard';
import { Banner, Button, Empty, Loading } from '../../components/ui';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { space, useColors } from '../../lib/theme';
import type { ListingCard as Card } from '../../lib/types';
import { useLoader } from '../../lib/useLoader';

export default function Saved() {
  const c = useColors();
  const { user } = useAuth();
  const { data, error, loading, refreshing, refresh, reload } = useLoader<Card[]>(() => (user ? api<Card[]>('/me/favorites') : Promise.resolve([])), [user?.id]);

  if (!user)
    return (
      <View style={{ flex: 1, backgroundColor: c.bg }}>
        <Empty icon="heart-outline" title="Save places you like" body="Log in to keep a shortlist and compare later." action={<Button title="Log in" onPress={() => router.push('/auth/login')} />} />
      </View>
    );
  if (loading) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: c.bg }}
      data={data ?? []}
      keyExtractor={(i) => i.id}
      contentContainerStyle={{ padding: space.lg, gap: space.lg, maxWidth: 720, width: '100%', alignSelf: 'center' }}
      ListHeaderComponent={error ? <Banner text={error} onRetry={reload} /> : null}
      renderItem={({ item }) => <ListingCard item={item} onPress={() => router.push(`/listing/${item.id}`)} />}
      ListEmptyComponent={<Empty icon="heart-outline" title="Nothing saved yet" body="Tap the heart on any listing to save it here." action={<Button title="Explore places" variant="secondary" onPress={() => router.navigate('/')} />} />}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.primary} />}
    />
  );
}

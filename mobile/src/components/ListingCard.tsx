import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { mediaUrl } from '../lib/api';
import { GENDER_LABEL, pkr, SPACE_LABEL, STATUS_LABEL } from '../lib/format';
import { font, radius, space, useColors } from '../lib/theme';
import type { ListingCard as Card } from '../lib/types';
import { Badge, Ionicons } from './ui';

export function ListingCard({ item, onPress, showStatus }: { item: Card; onPress: () => void; showStatus?: boolean }) {
  const c = useColors();
  const a11y = `${item.title}. ${SPACE_LABEL[item.space_type]} for ${GENDER_LABEL[item.gender_policy]} in ${item.area}, ${item.city}. ${pkr(item.rent_monthly)} per month.${item.has_tour ? ' Has 3D tour.' : ''}${item.owner_verified ? ' Verified owner.' : ''}`;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={a11y}
      onPress={onPress}
      style={({ pressed }) => [styles.card, { backgroundColor: c.surface, borderColor: c.border, opacity: pressed ? 0.92 : 1 }]}
    >
      <View style={[styles.imageWrap, { backgroundColor: c.surfaceAlt }]}>
        {item.cover_url ? (
          <Image source={{ uri: mediaUrl(item.cover_url) }} style={styles.image} resizeMode="cover" accessibilityIgnoresInvertColors />
        ) : (
          <View style={[styles.image, { alignItems: 'center', justifyContent: 'center' }]}>
            <Ionicons name="image-outline" size={32} color={c.subtle} />
          </View>
        )}
        <View style={styles.overlayRow}>
          {item.has_tour ? <Badge label="3D tour" icon="cube" tone="primary" /> : null}
          {showStatus ? <Badge label={STATUS_LABEL[item.status] ?? item.status} tone={item.status === 'active' ? 'success' : item.status === 'rejected' ? 'danger' : 'warning'} /> : null}
        </View>
      </View>
      <View style={{ padding: space.md, gap: 4 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={{ fontSize: font.lg, fontWeight: '800', color: c.text }}>
            {pkr(item.rent_monthly)}
            <Text style={{ fontSize: font.sm, fontWeight: '500', color: c.muted }}> /month</Text>
          </Text>
          {item.rating ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
              <Ionicons name="star" size={14} color={c.warning} />
              <Text style={{ color: c.text, fontWeight: '700' }}>{item.rating.toFixed(1)}</Text>
              <Text style={{ color: c.muted }}>({item.review_count})</Text>
            </View>
          ) : null}
        </View>
        <Text numberOfLines={1} style={{ fontSize: font.md, fontWeight: '600', color: c.text }}>
          {item.title}
        </Text>
        <Text numberOfLines={1} style={{ color: c.muted, fontSize: font.sm }}>
          <Ionicons name="location-outline" size={13} /> {item.area}, {item.city}
        </Text>
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
          <Badge label={SPACE_LABEL[item.space_type]} />
          <Badge label={GENDER_LABEL[item.gender_policy]} />
          {item.bills_included ? <Badge label="Bills incl." tone="success" /> : null}
          {item.meals_included ? <Badge label="Meals" tone="success" /> : null}
          {item.owner_verified ? <Badge label="Verified" icon="shield-checkmark" tone="primary" /> : null}
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.lg, borderWidth: 1, overflow: 'hidden' },
  imageWrap: { aspectRatio: 16 / 9, width: '100%' },
  image: { width: '100%', height: '100%' },
  overlayRow: { position: 'absolute', top: space.sm, left: space.sm, flexDirection: 'row', gap: 6 },
});

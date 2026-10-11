import { router } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { FlatList, Modal, Pressable, RefreshControl, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ListingCard } from '../../components/ListingCard';
import { Banner, Button, Chip, Empty, Field, H2, Ionicons, Loading, Row } from '../../components/ui';
import { api, ApiError } from '../../lib/api';
import { AMENITY_LABEL, CITIES, GENDER_LABEL, SPACE_LABEL } from '../../lib/format';
import { BRAND, font, MIN_TOUCH, radius, space, useColors } from '../../lib/theme';
import type { GenderPolicy, ListingCard as Card, Page, SpaceType } from '../../lib/types';

interface Filters {
  city?: string;
  space_type: SpaceType[];
  gender?: GenderPolicy;
  min_rent?: string;
  max_rent?: string;
  has_tour: boolean;
  verified: boolean;
  meals: boolean;
  bills: boolean;
  amenities: string[];
  sort: 'newest' | 'price_asc' | 'price_desc';
}
const EMPTY: Filters = { space_type: [], has_tour: false, verified: false, meals: false, bills: false, amenities: [], sort: 'newest' };
const QUICK_AMENITIES = ['wifi', 'ac', 'ups', 'attached_bath', 'kitchen', 'laundry', 'parking', 'cctv', 'furnished'];

function activeCount(f: Filters) {
  return f.space_type.length + (f.gender ? 1 : 0) + (f.min_rent ? 1 : 0) + (f.max_rent ? 1 : 0) + Number(f.has_tour) + Number(f.verified) + Number(f.meals) + Number(f.bills) + f.amenities.length + (f.sort !== 'newest' ? 1 : 0);
}

export default function Explore() {
  const c = useColors();
  const [q, setQ] = useState('');
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [showFilters, setShowFilters] = useState(false);
  const [items, setItems] = useState<Card[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reqId = useRef(0);

  const load = useCallback(
    async (p = 1, mode: 'replace' | 'append' = 'replace') => {
      const id = ++reqId.current;
      setError(null);
      if (mode === 'replace' && p === 1) setLoading(true);
      try {
        const res = await api<Page<Card>>('/listings', {
          query: {
            q: q.trim() || undefined,
            city: filters.city,
            space_type: filters.space_type,
            gender: filters.gender,
            min_rent: filters.min_rent ? Number(filters.min_rent) : undefined,
            max_rent: filters.max_rent ? Number(filters.max_rent) : undefined,
            has_tour: filters.has_tour,
            verified: filters.verified,
            meals: filters.meals,
            bills: filters.bills,
            amenities: filters.amenities,
            sort: filters.sort,
            page: p,
            page_size: 20,
          },
        });
        if (id !== reqId.current) return; // a newer search superseded this one
        setItems((prev) => (mode === 'append' ? [...prev, ...res.items] : res.items));
        setTotal(res.total);
        setPage(p);
      } catch (e) {
        if (id === reqId.current) setError(e instanceof ApiError ? e.message : 'Could not load listings');
      } finally {
        if (id === reqId.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [q, filters],
  );

  // Debounced search-as-you-type
  useEffect(() => {
    const t = setTimeout(() => load(1), 300);
    return () => clearTimeout(t);
  }, [load]);

  const toggle = <K extends keyof Filters>(key: K, value: Filters[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const n = activeCount(filters);

  const header = (
    <View style={{ gap: space.md, paddingBottom: space.md }}>
      <View>
        <Text style={{ fontSize: font.xxl, fontWeight: '900', color: c.primary }}>{BRAND}</Text>
        <Text style={{ color: c.muted, fontSize: font.md }}>Beds, rooms & spaces — see them in 3D before you visit</Text>
      </View>
      <Row>
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', backgroundColor: c.surface, borderColor: c.border, borderWidth: 1.5, borderRadius: radius.md, paddingHorizontal: space.md }}>
          <Ionicons name="search" size={18} color={c.subtle} />
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="Search area, hostel or university"
            placeholderTextColor={c.subtle}
            accessibilityLabel="Search listings"
            returnKeyType="search"
            style={{ flex: 1, minHeight: MIN_TOUCH, color: c.text, fontSize: font.md, paddingHorizontal: space.sm }}
          />
          {q ? (
            <Pressable accessibilityRole="button" accessibilityLabel="Clear search" onPress={() => setQ('')} hitSlop={10}>
              <Ionicons name="close-circle" size={18} color={c.subtle} />
            </Pressable>
          ) : null}
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Filters${n ? `, ${n} active` : ''}`}
          onPress={() => {
            setDraft(filters);
            setShowFilters(true);
          }}
          style={{ minHeight: MIN_TOUCH + 4, minWidth: MIN_TOUCH + 4, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: n ? c.primary : c.surface, borderWidth: 1.5, borderColor: n ? c.primary : c.border }}
        >
          <Ionicons name="options" size={22} color={n ? c.primaryText : c.text} />
          {n ? <Text style={{ position: 'absolute', top: 2, right: 6, color: c.primaryText, fontSize: 11, fontWeight: '800' }}>{n}</Text> : null}
        </Pressable>
      </Row>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
        <Chip label="All cities" selected={!filters.city} onPress={() => setFilters((f) => ({ ...f, city: undefined }))} />
        {CITIES.map((city) => (
          <Chip key={city} label={city} selected={filters.city === city} onPress={() => setFilters((f) => ({ ...f, city: f.city === city ? undefined : city }))} />
        ))}
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
        <Chip label="3D tour" icon="cube-outline" selected={filters.has_tour} onPress={() => setFilters((f) => ({ ...f, has_tour: !f.has_tour }))} />
        <Chip label="Girls" selected={filters.gender === 'female'} onPress={() => setFilters((f) => ({ ...f, gender: f.gender === 'female' ? undefined : 'female' }))} />
        <Chip label="Boys" selected={filters.gender === 'male'} onPress={() => setFilters((f) => ({ ...f, gender: f.gender === 'male' ? undefined : 'male' }))} />
        <Chip label="Verified owner" icon="shield-checkmark-outline" selected={filters.verified} onPress={() => setFilters((f) => ({ ...f, verified: !f.verified }))} />
        <Chip label="Meals" selected={filters.meals} onPress={() => setFilters((f) => ({ ...f, meals: !f.meals }))} />
      </ScrollView>
      {error ? <Banner text={error} onRetry={() => load(1)} /> : null}
      {!loading && !error ? (
        <Text accessibilityLiveRegion="polite" style={{ color: c.muted, fontSize: font.sm }}>
          {total} {total === 1 ? 'place' : 'places'} found
        </Text>
      ) : null}
    </View>
  );

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: c.bg }}>
      <FlatList
        data={loading ? [] : items}
        keyExtractor={(i) => i.id}
        contentContainerStyle={{ padding: space.lg, gap: space.lg, maxWidth: 720, width: '100%', alignSelf: 'center' }}
        ListHeaderComponent={header}
        renderItem={({ item }) => <ListingCard item={item} onPress={() => router.push(`/listing/${item.id}`)} />}
        ListEmptyComponent={
          loading ? (
            <Loading label="Finding places…" />
          ) : error ? null : (
            <Empty
              icon="bed-outline"
              title="No places match"
              body="Try another area, widen your budget or clear some filters."
              action={n || q ? <Button title="Clear filters" variant="secondary" onPress={() => { setFilters(EMPTY); setQ(''); }} /> : undefined}
            />
          )
        }
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (!loading && items.length < total) load(page + 1, 'append');
        }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(1); }} tintColor={c.primary} />}
      />

      <Modal visible={showFilters} animationType="slide" onRequestClose={() => setShowFilters(false)} presentationStyle="pageSheet">
        <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }}>
          <Row style={{ justifyContent: 'space-between', padding: space.lg }}>
            <Text accessibilityRole="header" style={{ fontSize: font.xl, fontWeight: '800', color: c.text }}>Filters</Text>
            <Button title="Reset" variant="ghost" compact onPress={() => setDraft(EMPTY)} />
          </Row>
          <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.xl, paddingTop: 0 }}>
            <View style={{ gap: space.sm }}>
              <H2>Type of space</H2>
              <Row wrap>
                {(Object.keys(SPACE_LABEL) as SpaceType[]).map((t) => (
                  <Chip key={t} label={SPACE_LABEL[t]} selected={draft.space_type.includes(t)} onPress={() => toggle('space_type', draft.space_type.includes(t) ? draft.space_type.filter((x) => x !== t) : [...draft.space_type, t])} />
                ))}
              </Row>
            </View>
            <View style={{ gap: space.sm }}>
              <H2>Who can stay</H2>
              <Row wrap>
                {(Object.keys(GENDER_LABEL) as GenderPolicy[]).map((g) => (
                  <Chip key={g} label={GENDER_LABEL[g]} selected={draft.gender === g} onPress={() => toggle('gender', draft.gender === g ? undefined : g)} />
                ))}
              </Row>
            </View>
            <View style={{ gap: space.sm }}>
              <H2>Monthly rent (Rs)</H2>
              <Row gap={space.md}>
                <View style={{ flex: 1 }}>
                  <Field label="Min" keyboardType="number-pad" value={draft.min_rent ?? ''} onChangeText={(v) => toggle('min_rent', v.replace(/\D/g, ''))} placeholder="5,000" />
                </View>
                <View style={{ flex: 1 }}>
                  <Field label="Max" keyboardType="number-pad" value={draft.max_rent ?? ''} onChangeText={(v) => toggle('max_rent', v.replace(/\D/g, ''))} placeholder="50,000" />
                </View>
              </Row>
            </View>
            <View style={{ gap: space.sm }}>
              <H2>Must have</H2>
              <Row wrap>
                <Chip label="3D tour" icon="cube-outline" selected={draft.has_tour} onPress={() => toggle('has_tour', !draft.has_tour)} />
                <Chip label="Verified owner" selected={draft.verified} onPress={() => toggle('verified', !draft.verified)} />
                <Chip label="Meals included" selected={draft.meals} onPress={() => toggle('meals', !draft.meals)} />
                <Chip label="Bills included" selected={draft.bills} onPress={() => toggle('bills', !draft.bills)} />
                {QUICK_AMENITIES.map((a) => (
                  <Chip key={a} label={AMENITY_LABEL[a]} selected={draft.amenities.includes(a)} onPress={() => toggle('amenities', draft.amenities.includes(a) ? draft.amenities.filter((x) => x !== a) : [...draft.amenities, a])} />
                ))}
              </Row>
            </View>
            <View style={{ gap: space.sm }}>
              <H2>Sort by</H2>
              <Row wrap>
                <Chip label="Newest" selected={draft.sort === 'newest'} onPress={() => toggle('sort', 'newest')} />
                <Chip label="Price: low to high" selected={draft.sort === 'price_asc'} onPress={() => toggle('sort', 'price_asc')} />
                <Chip label="Price: high to low" selected={draft.sort === 'price_desc'} onPress={() => toggle('sort', 'price_desc')} />
              </Row>
            </View>
          </ScrollView>
          <Row style={{ padding: space.lg, borderTopWidth: 1, borderTopColor: c.border }} gap={space.md}>
            <Button title="Cancel" variant="secondary" style={{ flex: 1 }} onPress={() => setShowFilters(false)} />
            <Button
              title="Show results"
              style={{ flex: 2 }}
              onPress={() => {
                if (draft.min_rent && draft.max_rent && Number(draft.min_rent) > Number(draft.max_rent)) {
                  setDraft({ ...draft, min_rent: draft.max_rent, max_rent: draft.min_rent });
                  return;
                }
                setFilters({ ...draft, city: filters.city });
                setShowFilters(false);
              }}
            />
          </Row>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Image, Modal, Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Badge, Banner, Button, Card, Chip, Field, H2, IconButton, Ionicons, Loading, P, Row } from '../../components/ui';
import { api, ApiError, mediaUrl } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { AMENITY_LABEL, dateTime, GENDER_LABEL, pkr, shortDate, SPACE_HELP, SPACE_LABEL } from '../../lib/format';
import { font, radius, space, useColors } from '../../lib/theme';
import type { Conversation, Listing, Review } from '../../lib/types';
import { useRequireAuth } from '../../lib/useRequireAuth';

function slots() {
  const out: { label: string; at: Date }[] = [];
  const base = new Date();
  for (let d = 1; d <= 4; d++) {
    for (const h of [11, 17]) {
      const t = new Date(base);
      t.setDate(base.getDate() + d);
      t.setHours(h, 0, 0, 0);
      out.push({ label: dateTime(t.toISOString()), at: t });
    }
  }
  return out;
}

const REPORT_REASONS: [string, string][] = [
  ['scam', 'Scam or asks for advance money'],
  ['fake_photos', 'Photos don’t match the place'],
  ['wrong_info', 'Wrong price or details'],
  ['already_rented', 'Already rented'],
  ['inappropriate', 'Inappropriate content'],
  ['other', 'Something else'],
];

export default function ListingDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const c = useColors();
  const { width } = useWindowDimensions();
  const { user } = useAuth();
  const guard = useRequireAuth();
  const [listing, setListing] = useState<Listing | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [photoIdx, setPhotoIdx] = useState(0);
  const [sheet, setSheet] = useState<null | 'message' | 'visit' | 'report' | 'review'>(null);
  const [msg, setMsg] = useState('Assalam o Alaikum! Is this space still available?');
  const [slot, setSlot] = useState<Date | null>(null);
  const [note, setNote] = useState('');
  const [reason, setReason] = useState<string | null>(null);
  const [rating, setRating] = useState(0);
  const [reviewText, setReviewText] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; tone: 'success' | 'danger' } | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [l, r] = await Promise.all([api<Listing>(`/listings/${id}`), api<Review[]>(`/listings/${id}/reviews`)]);
      setListing(l);
      setReviews(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load this listing');
    }
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);

  if (error) return <SafeAreaView style={{ flex: 1, padding: space.lg, backgroundColor: c.bg }}><Banner text={error} onRetry={load} /></SafeAreaView>;
  if (!listing) return <Loading />;
  const l = listing;
  const isOwner = user?.id === l.owner.id;
  const imgW = Math.min(width, 720);

  const toggleFav = () =>
    guard(async () => {
      const next = !l.is_favorite;
      setListing({ ...l, is_favorite: next });
      try {
        await api(`/listings/${l.id}/favorite`, { method: next ? 'POST' : 'DELETE' });
      } catch {
        setListing({ ...l, is_favorite: !next });
      }
    }, false);

  const run = async (fn: () => Promise<void>, ok: string) => {
    setBusy(true);
    try {
      await fn();
      setSheet(null);
      setNotice({ text: ok, tone: 'success' });
    } catch (e) {
      setNotice({ text: e instanceof ApiError ? e.message : 'Something went wrong', tone: 'danger' });
      setSheet(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen
        options={{
          title: '',
          headerRight: () => (
            <Row gap={0}>
              <IconButton icon={l.is_favorite ? 'heart' : 'heart-outline'} color={l.is_favorite ? c.danger : c.text} label={l.is_favorite ? 'Remove from saved' : 'Save listing'} onPress={toggleFav} />
              {!isOwner ? <IconButton icon="flag-outline" label="Report listing" onPress={() => guard(() => setSheet('report'), false)} /> : null}
            </Row>
          ),
        }}
      />
      <ScrollView contentContainerStyle={{ paddingBottom: 120, maxWidth: 720, width: '100%', alignSelf: 'center' }}>
        {l.photos.length ? (
          <View>
            <ScrollView
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              onMomentumScrollEnd={(e) => setPhotoIdx(Math.round(e.nativeEvent.contentOffset.x / imgW))}
              onScroll={(e) => setPhotoIdx(Math.round(e.nativeEvent.contentOffset.x / imgW))}
              scrollEventThrottle={100}
            >
              {l.photos.map((p, i) => (
                <Image key={p.id} source={{ uri: mediaUrl(p.url) }} style={{ width: imgW, aspectRatio: 4 / 3 }} accessibilityLabel={`Photo ${i + 1} of ${l.photos.length}`} />
              ))}
            </ScrollView>
            <View style={{ position: 'absolute', bottom: 10, right: 10, backgroundColor: c.overlay, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill }}>
              <Text style={{ color: '#fff', fontWeight: '700' }}>
                {photoIdx + 1}/{l.photos.length}
              </Text>
            </View>
          </View>
        ) : null}

        <View style={{ padding: space.lg, gap: space.lg }}>
          {notice ? <Banner text={notice.text} tone={notice.tone} /> : null}
          {l.status !== 'active' ? <Banner tone="warning" text={l.status === 'rented' ? 'This place has been rented out.' : 'This listing is not public yet.'} /> : null}
          <View style={{ gap: space.sm }}>
            <Row wrap>
              <Badge label={SPACE_LABEL[l.space_type]} tone="primary" />
              <Badge label={GENDER_LABEL[l.gender_policy]} />
              {l.owner.is_verified_owner ? <Badge label="Verified owner" icon="shield-checkmark" tone="success" /> : null}
            </Row>
            <Text accessibilityRole="header" style={{ fontSize: font.xl, fontWeight: '800', color: c.text }}>{l.title}</Text>
            <Text style={{ color: c.muted, fontSize: font.md }}>
              <Ionicons name="location-outline" size={15} /> {l.area}, {l.city}
              {l.property_name ? ` · ${l.property_name}` : ''}
            </Text>
          </View>

          {l.tour && l.tour.status === 'ready' ? (
            <Card onPress={() => router.push({ pathname: '/tour/[id]', params: { id: l.tour!.id } })} accessibilityLabel="Open the 3D walkthrough" style={{ padding: 0, overflow: 'hidden', borderColor: c.primary, borderWidth: 2 }}>
              {l.tour.preview_url ? <Image source={{ uri: mediaUrl(l.tour.preview_url) }} style={{ width: '100%', aspectRatio: 2.4 }} /> : null}
              <Row style={{ padding: space.md, justifyContent: 'space-between' }}>
                <Row>
                  <Ionicons name="cube" size={24} color={c.primary} />
                  <View>
                    <Text style={{ fontWeight: '800', color: c.text, fontSize: font.md }}>Walk through in 3D</Text>
                    <Text style={{ color: c.muted, fontSize: font.sm }}>{l.tour.rooms} {l.tour.rooms === 1 ? 'room' : 'rooms'} · look around, walk & dollhouse view</Text>
                  </View>
                </Row>
                <Ionicons name="chevron-forward" size={22} color={c.primary} />
              </Row>
            </Card>
          ) : null}

          <Card>
            <Row style={{ justifyContent: 'space-between' }}>
              <Text style={{ fontSize: font.xl, fontWeight: '800', color: c.text }}>
                {pkr(l.rent_monthly)} <Text style={{ fontSize: font.sm, color: c.muted, fontWeight: '500' }}>/ month</Text>
              </Text>
              <Badge label={l.available_beds > 0 ? `${l.available_beds} available` : 'Full'} tone={l.available_beds > 0 ? 'success' : 'danger'} />
            </Row>
            <P muted>Security deposit: {l.deposit ? pkr(l.deposit) : 'None'}</P>
            <Row wrap>
              <Badge label={l.bills_included ? 'Bills included' : 'Bills extra'} tone={l.bills_included ? 'success' : 'neutral'} />
              <Badge label={l.meals_included ? 'Meals included' : 'No meals'} tone={l.meals_included ? 'success' : 'neutral'} />
              {l.available_from ? <Badge label={`From ${shortDate(l.available_from)}`} /> : null}
              <Badge label={`Capacity ${l.capacity}`} />
            </Row>
          </Card>

          <View style={{ gap: space.sm }}>
            <H2>About this space</H2>
            <P muted>{SPACE_HELP[l.space_type]}</P>
            {l.description ? <P>{l.description}</P> : null}
          </View>

          {l.amenities.length ? (
            <View style={{ gap: space.sm }}>
              <H2>Amenities</H2>
              <Row wrap>
                {l.amenities.map((a) => (
                  <Chip key={a} label={AMENITY_LABEL[a] ?? a} icon="checkmark" />
                ))}
              </Row>
            </View>
          ) : null}

          {l.rules ? (
            <View style={{ gap: space.sm }}>
              <H2>House rules</H2>
              <P>{l.rules}</P>
            </View>
          ) : null}

          <View style={{ gap: space.sm }}>
            <H2>Location</H2>
            {l.address_line ? (
              <Banner tone="success" icon="location" text={`${l.address_line}, ${l.area}, ${l.city}`} />
            ) : (
              <Banner tone="primary" icon="lock-closed" text={`${l.area}, ${l.city}. The exact address is shared after the owner accepts your visit — for everyone’s safety.`} />
            )}
          </View>

          <Card>
            <Row>
              <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: c.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ color: c.primary, fontWeight: '800', fontSize: font.lg }}>{l.owner.full_name[0]}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: '700', color: c.text, fontSize: font.md }}>{l.owner.full_name}</Text>
                <Text style={{ color: c.muted, fontSize: font.sm }}>Member since {new Date(l.owner.created_at).getFullYear()}</Text>
              </View>
              {l.owner.is_verified_owner ? <Badge label="Verified" icon="shield-checkmark" tone="success" /> : null}
            </Row>
            <P muted style={{ fontSize: font.sm }}>Never pay an advance before visiting. Keep chats in Kamra so we can help if something goes wrong.</P>
          </Card>

          <View style={{ gap: space.sm }}>
            <H2 right={!isOwner && user ? <Button title="Write review" variant="ghost" compact onPress={() => setSheet('review')} /> : undefined}>
              Reviews {l.rating ? `· ★ ${l.rating.toFixed(1)}` : ''}
            </H2>
            {reviews.length === 0 ? <P muted>No reviews yet. Reviews come from people who visited.</P> : null}
            {reviews.map((r) => (
              <Card key={r.id}>
                <Row style={{ justifyContent: 'space-between' }}>
                  <Text style={{ fontWeight: '700', color: c.text }}>{r.author_name}</Text>
                  <Text accessibilityLabel={`${r.rating} out of 5 stars`} style={{ color: c.warning }}>{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</Text>
                </Row>
                {r.body ? <P>{r.body}</P> : null}
                {r.owner_reply ? <P muted style={{ fontStyle: 'italic' }}>Owner: {r.owner_reply}</P> : null}
              </Card>
            ))}
          </View>
        </View>
      </ScrollView>

      {!isOwner && l.status === 'active' ? (
        <SafeAreaView edges={['bottom']} style={{ position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.border }}>
          <Row gap={space.md} style={{ padding: space.md, maxWidth: 720, width: '100%', alignSelf: 'center' }}>
            <Button title="Message" icon="chatbubble-outline" variant="secondary" style={{ flex: 1 }} onPress={() => guard(() => setSheet('message'))} />
            <Button title="Request visit" icon="calendar-outline" style={{ flex: 1 }} onPress={() => guard(() => setSheet('visit'))} />
          </Row>
        </SafeAreaView>
      ) : isOwner ? (
        <SafeAreaView edges={['bottom']} style={{ position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.border }}>
          <View style={{ padding: space.md, maxWidth: 720, width: '100%', alignSelf: 'center' }}>
            <Button title="Manage this listing" icon="settings-outline" onPress={() => router.push(`/manage/${l.id}`)} />
          </View>
        </SafeAreaView>
      ) : null}

      <Modal visible={sheet !== null} transparent animationType="slide" onRequestClose={() => setSheet(null)}>
        <Pressable style={{ flex: 1, backgroundColor: c.overlay }} onPress={() => setSheet(null)} accessibilityLabel="Close" />
        <SafeAreaView edges={['bottom']} style={{ backgroundColor: c.surface, borderTopLeftRadius: 20, borderTopRightRadius: 20 }}>
          <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.md, maxWidth: 720, width: '100%', alignSelf: 'center' }} keyboardShouldPersistTaps="handled">
            {sheet === 'message' ? (
              <>
                <H2>Message {l.owner.full_name.split(' ')[0]}</H2>
                <Field label="Your message" value={msg} onChangeText={setMsg} multiline maxLength={2000} style={{ minHeight: 100, textAlignVertical: 'top' }} />
                <Button
                  title="Send"
                  icon="send"
                  loading={busy}
                  disabled={!msg.trim()}
                  onPress={async () => {
                    setBusy(true);
                    try {
                      const conv = await api<Conversation>('/conversations', { body: { listing_id: l.id, message: msg.trim() } });
                      setSheet(null);
                      router.push(`/chat/${conv.id}`);
                    } catch (e) {
                      setNotice({ text: e instanceof ApiError ? e.message : 'Message not sent', tone: 'danger' });
                      setSheet(null);
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
              </>
            ) : sheet === 'visit' ? (
              <>
                <H2>Pick a time to visit</H2>
                <P muted>The owner will confirm. You’ll see the exact address once accepted.</P>
                <Row wrap>
                  {slots().map((s) => (
                    <Chip key={s.at.toISOString()} label={s.label} selected={slot?.getTime() === s.at.getTime()} onPress={() => setSlot(s.at)} />
                  ))}
                </Row>
                <Field label="Note (optional)" value={note} onChangeText={setNote} placeholder="e.g. I’m a student at UET, coming with my brother" maxLength={500} />
                <Button
                  title="Send request"
                  loading={busy}
                  disabled={!slot}
                  onPress={() => run(async () => void (await api('/visits', { body: { listing_id: l.id, proposed_at: slot!.toISOString(), note } })), 'Visit requested. We’ll notify you when the owner replies.')}
                />
              </>
            ) : sheet === 'report' ? (
              <>
                <H2>What’s wrong with this listing?</H2>
                {REPORT_REASONS.map(([k, label]) => (
                  <Chip key={k} label={label} selected={reason === k} onPress={() => setReason(k)} />
                ))}
                <Button
                  title="Submit report"
                  variant="danger"
                  loading={busy}
                  disabled={!reason}
                  onPress={() => run(async () => void (await api('/reports', { body: { target_type: 'listing', target_id: l.id, reason } })), 'Thanks — our team will review this listing.')}
                />
              </>
            ) : sheet === 'review' ? (
              <>
                <H2>Rate your visit</H2>
                <Row>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <Pressable key={n} accessibilityRole="button" accessibilityLabel={`${n} star${n > 1 ? 's' : ''}`} accessibilityState={{ selected: rating === n }} onPress={() => setRating(n)} hitSlop={6}>
                      <Ionicons name={n <= rating ? 'star' : 'star-outline'} size={36} color={c.warning} />
                    </Pressable>
                  ))}
                </Row>
                <Field label="Your review" value={reviewText} onChangeText={setReviewText} multiline maxLength={1000} style={{ minHeight: 90, textAlignVertical: 'top' }} />
                <Button
                  title="Post review"
                  loading={busy}
                  disabled={!rating}
                  onPress={() => run(async () => { await api(`/listings/${l.id}/reviews`, { body: { rating, body: reviewText } }); await load(); }, 'Thanks for your review!')}
                />
              </>
            ) : null}
            <Button title="Cancel" variant="ghost" onPress={() => setSheet(null)} />
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </View>
  );
}

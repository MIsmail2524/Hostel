import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';

import { Badge, Banner, Button, Card, H2, Ionicons, Loading, P, ProgressBar, Row, Screen } from '../../components/ui';
import { api, ApiError, appendFile, mediaUrl } from '../../lib/api';
import { confirm } from '../../lib/confirm';
import { pkr, STATUS_LABEL } from '../../lib/format';
import { font, radius, space, useColors } from '../../lib/theme';
import type { Listing, Photo } from '../../lib/types';
import { useLoader } from '../../lib/useLoader';

export default function ManageListing() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const c = useColors();
  const { data: l, setData, error, loading, reload } = useLoader(() => api<Listing>(`/listings/${id}`), [id]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ text: string; tone: 'success' | 'danger' } | null>(null);

  if (loading) return <Loading />;
  if (!l) return <Screen><Banner text={error ?? 'Not found'} onRetry={reload} /></Screen>;

  const act = async (key: string, fn: () => Promise<Listing | void>, ok?: string) => {
    setBusy(key);
    setNotice(null);
    try {
      const res = await fn();
      if (res) setData(res);
      if (ok) setNotice({ text: ok, tone: 'success' });
    } catch (e) {
      setNotice({ text: e instanceof ApiError ? e.message : 'Something went wrong', tone: 'danger' });
    } finally {
      setBusy(null);
    }
  };

  const addPhotos = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: true, selectionLimit: 20 - l.photos.length, quality: 0.85, exif: false });
    if (res.canceled || !res.assets.length) return;
    await act('photos', async () => {
      const form = new FormData();
      for (const a of res.assets) await appendFile(form, 'files', a);
      const added = await api<Photo[]>(`/listings/${l.id}/photos`, { form, timeoutMs: 180000 });
      setData({ ...l, photos: [...l.photos, ...added] });
    }, 'Photos added');
  };

  const status = (action: 'submit' | 'pause' | 'resume' | 'rented', ok: string) => act(action, () => api<Listing>(`/listings/${l.id}/status`, { body: { action } }), ok);
  const tone = l.status === 'active' ? 'success' : l.status === 'rejected' ? 'danger' : 'warning';
  const checklist = [
    { done: true, label: 'Details & price' },
    { done: l.photos.length > 0, label: 'At least 1 photo (5+ recommended)' },
    { done: l.tour?.status === 'ready', label: '3D tour (optional, gets ~3× more enquiries)', optional: true },
  ];

  return (
    <Screen style={{ maxWidth: 720, width: '100%', alignSelf: 'center' }}>
      <View style={{ gap: space.xs }}>
        <Row style={{ justifyContent: 'space-between' }}>
          <Badge label={STATUS_LABEL[l.status] ?? l.status} tone={tone} />
          <Text style={{ color: c.muted }}>{l.views} views</Text>
        </Row>
        <Text accessibilityRole="header" style={{ fontSize: font.xl, fontWeight: '800', color: c.text }}>{l.title}</Text>
        <P muted>{pkr(l.rent_monthly)}/month · {l.area}, {l.city}</P>
      </View>
      {notice ? <Banner text={notice.text} tone={notice.tone} /> : null}
      {l.status === 'rejected' && l.rejection_reason ? <Banner tone="danger" text={`Needs changes: ${l.rejection_reason}`} /> : null}
      {l.status === 'pending_review' ? <Banner tone="primary" text="Our team is checking your listing. It usually goes live within a few hours." /> : null}

      <Card>
        <H2>Checklist</H2>
        {checklist.map((i) => (
          <Row key={i.label}>
            <Ionicons name={i.done ? 'checkmark-circle' : i.optional ? 'ellipse-outline' : 'alert-circle'} size={20} color={i.done ? c.success : i.optional ? c.subtle : c.warning} />
            <P style={{ flex: 1 }}>{i.label}</P>
          </Row>
        ))}
        {l.status === 'draft' || l.status === 'rejected' ? (
          <Button title="Submit for review" icon="paper-plane-outline" loading={busy === 'submit'} disabled={!l.photos.length} onPress={() => status('submit', 'Submitted! We’ll notify you when it’s live.')} />
        ) : null}
      </Card>

      <Card>
        <H2 right={<Text style={{ color: c.muted }}>{l.photos.length}/20</Text>}>Photos</H2>
        <Row wrap gap={space.sm}>
          {l.photos.map((p, i) => (
            <View key={p.id}>
              <Image source={{ uri: mediaUrl(p.thumb_url) }} style={{ width: 96, height: 72, borderRadius: radius.sm }} accessibilityLabel={`Photo ${i + 1}${i === 0 ? ', cover photo' : ''}`} />
              {i === 0 ? <View style={{ position: 'absolute', left: 4, top: 4 }}><Badge label="Cover" tone="primary" /></View> : null}
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Delete photo ${i + 1}`}
                hitSlop={8}
                onPress={async () => {
                  if (await confirm('Delete photo?', 'This cannot be undone.', 'Delete', true))
                    act('del' + p.id, async () => {
                      await api(`/listings/${l.id}/photos/${p.id}`, { method: 'DELETE' });
                      setData({ ...l, photos: l.photos.filter((x) => x.id !== p.id) });
                    });
                }}
                style={{ position: 'absolute', right: -6, top: -6, backgroundColor: c.surface, borderRadius: 14 }}
              >
                <Ionicons name="close-circle" size={26} color={c.danger} />
              </Pressable>
            </View>
          ))}
        </Row>
        <Button title="Add photos" icon="images-outline" variant="secondary" loading={busy === 'photos'} disabled={l.photos.length >= 20} onPress={addPhotos} />
        <P muted style={{ fontSize: font.sm }}>Tip: bright daytime photos of the bed, cupboard, bathroom and building entrance work best. Location data is removed automatically.</P>
      </Card>

      <Card>
        <H2>3D walkthrough</H2>
        {l.tour ? (
          <>
            <Row style={{ justifyContent: 'space-between' }}>
              <Badge label={l.tour.status === 'ready' ? `Ready · ${l.tour.rooms} room(s)` : l.tour.status} tone={l.tour.status === 'ready' ? 'success' : l.tour.status === 'failed' ? 'danger' : 'warning'} />
            </Row>
            {l.tour.status === 'processing' || l.tour.status === 'queued' ? <ProgressBar value={l.tour.progress} /> : null}
            {l.tour.preview_url ? <Image source={{ uri: mediaUrl(l.tour.preview_url) }} style={{ width: '100%', aspectRatio: 2.4, borderRadius: radius.md }} /> : null}
          </>
        ) : (
          <P muted>Turn your phone photos or a short video into a walk-through 3D tour. Takes about 3 minutes to capture.</P>
        )}
        <Button title={l.tour ? 'Open 3D tour builder' : 'Create 3D tour'} icon="cube-outline" onPress={() => router.push({ pathname: '/tour/builder', params: { listingId: l.id } })} />
      </Card>

      <Card>
        <H2>Availability</H2>
        <Row style={{ justifyContent: 'space-between' }}>
          <P>Beds available now</P>
          <Row>
            <Button title="−" variant="secondary" compact disabled={l.available_beds <= 0} onPress={() => act('avail', () => api<Listing>(`/listings/${l.id}/availability`, { method: 'PATCH', body: { available_beds: l.available_beds - 1 } }))} />
            <Text accessibilityLiveRegion="polite" style={{ fontSize: font.lg, fontWeight: '800', color: c.text, minWidth: 30, textAlign: 'center' }}>{l.available_beds}</Text>
            <Button title="+" variant="secondary" compact disabled={l.available_beds >= l.capacity} onPress={() => act('avail', () => api<Listing>(`/listings/${l.id}/availability`, { method: 'PATCH', body: { available_beds: l.available_beds + 1 } }))} />
          </Row>
        </Row>
      </Card>

      <Row wrap gap={space.sm}>
        <Button title="Edit details" icon="create-outline" variant="secondary" onPress={() => router.push({ pathname: '/listing/edit', params: { id: l.id } })} />
        <Button title="Preview" icon="eye-outline" variant="secondary" onPress={() => router.push(`/listing/${l.id}`)} />
        {l.status === 'active' ? <Button title="Pause" icon="pause-outline" variant="secondary" loading={busy === 'pause'} onPress={() => status('pause', 'Listing paused — hidden from search.')} /> : null}
        {l.status === 'paused' ? <Button title="Resume" icon="play-outline" variant="secondary" loading={busy === 'resume'} onPress={() => status('resume', 'Listing is live again.')} /> : null}
        {l.status === 'active' || l.status === 'paused' ? <Button title="Mark as rented" icon="key-outline" variant="secondary" loading={busy === 'rented'} onPress={() => status('rented', 'Marked as rented. Congratulations!')} /> : null}
      </Row>
      <Button
        title="Delete listing"
        icon="trash-outline"
        variant="ghost"
        onPress={async () => {
          if (await confirm('Delete this listing?', 'Photos, 3D tour and chats about it will be removed permanently.', 'Delete', true))
            act('delete', async () => {
              await api(`/listings/${l.id}`, { method: 'DELETE' });
              router.back();
            });
        }}
      />
    </Screen>
  );
}

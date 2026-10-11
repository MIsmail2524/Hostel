import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Image, Platform, Pressable, Text, View } from 'react-native';

import { Badge, Banner, Button, Card, Chip, Field, H2, Ionicons, Loading, P, ProgressBar, Row, Screen } from '../../components/ui';
import { api, ApiError, appendFile, mediaUrl } from '../../lib/api';
import { confirm } from '../../lib/confirm';
import { font, space, useColors } from '../../lib/theme';
import type { Room, Tour } from '../../lib/types';

const SIZES = [
  { key: 'S', label: 'Small (10×11 ft)', w: 3.0, l: 3.4 },
  { key: 'M', label: 'Medium (12×14 ft)', w: 3.7, l: 4.3 },
  { key: 'L', label: 'Large (15×18 ft)', w: 4.5, l: 5.5 },
];
const ROOM_NAMES = ['Bedroom', 'Room', 'Washroom', 'Kitchen', 'Common area', 'Lounge', 'Balcony'];
const BATCH = 4;

export default function TourBuilder() {
  const { listingId } = useLocalSearchParams<{ listingId: string }>();
  const c = useColors();
  const [tour, setTour] = useState<Tour | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [upload, setUpload] = useState<{ room: string; done: number; total: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [newRoom, setNewRoom] = useState('');
  const [guideOpen, setGuideOpen] = useState(true);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async (id: string) => {
    const t = await api<Tour>(`/tours/${id}`);
    setTour(t);
    return t;
  }, []);

  useEffect(() => {
    api<Tour>(`/listings/${listingId}/tour`, { body: { engine: 'room360' } })
      .then((t) => {
        setTour(t);
        if (t.rooms.length) setGuideOpen(false);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not open the tour builder'));
    return () => {
      if (poll.current) clearInterval(poll.current);
    };
  }, [listingId]);

  // Visibility of system status: poll while the server is processing.
  useEffect(() => {
    if (!tour) return;
    const active = tour.status === 'queued' || tour.status === 'processing';
    if (active && !poll.current) {
      poll.current = setInterval(() => refresh(tour.id).catch(() => undefined), 2000);
    } else if (!active && poll.current) {
      clearInterval(poll.current);
      poll.current = null;
    }
  }, [tour, refresh]);

  if (error) return <Screen><Banner text={error} /></Screen>;
  if (!tour) return <Loading label="Opening tour builder…" />;
  const processing = tour.status === 'queued' || tour.status === 'processing';

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setNotice(null);
    try {
      await fn();
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : 'Something went wrong');
    } finally {
      setBusy(null);
    }
  };

  const addRoom = (name: string) =>
    run('add', async () => {
      await api<Room>(`/tours/${tour.id}/rooms`, { body: { name: name.trim(), width_m: 3.7, length_m: 4.3, height_m: 3.0 } });
      setNewRoom('');
      setGuideOpen(false);
      await refresh(tour.id);
    });

  const uploadAssets = async (room: Room, assets: ImagePicker.ImagePickerAsset[]) => {
    setUpload({ room: room.id, done: 0, total: assets.length });
    try {
      for (let i = 0; i < assets.length; i += BATCH) {
        const form = new FormData();
        for (const a of assets.slice(i, i + BATCH)) await appendFile(form, 'files', a);
        await api(`/tours/${tour.id}/rooms/${room.id}/inputs`, { form, timeoutMs: 600000 });
        setUpload({ room: room.id, done: Math.min(assets.length, i + BATCH), total: assets.length });
      }
      await refresh(tour.id);
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : 'Upload failed — check your connection and try again.');
      await refresh(tour.id).catch(() => undefined);
    } finally {
      setUpload(null);
    }
  };

  const pick = async (room: Room, kind: 'images' | 'videos', camera = false) => {
    if (camera) {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) return setNotice('Camera permission is needed. You can also choose photos from your gallery.');
      const res = await ImagePicker.launchCameraAsync({ mediaTypes: [kind], quality: 0.9, videoMaxDuration: 120, exif: false });
      if (!res.canceled) await uploadAssets(room, res.assets);
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: [kind], allowsMultipleSelection: kind === 'images', selectionLimit: 40, quality: 0.9, exif: false });
    if (!res.canceled && res.assets.length) await uploadAssets(room, res.assets);
  };

  const process = () =>
    run('process', async () => {
      setTour(await api<Tour>(`/tours/${tour.id}/process`, { method: 'POST' }));
    });

  const preview = () =>
    run('preview', async () => {
      const r = await api<{ path: string }>(`/tours/${tour.id}/preview-link`, { method: 'POST' });
      router.push({ pathname: '/tour/[id]', params: { id: tour.id, preview: r.path } });
    });

  const allHaveMedia = tour.rooms.length > 0 && tour.rooms.every((r) => r.input_count > 0);

  return (
    <Screen style={{ maxWidth: 720, width: '100%', alignSelf: 'center' }}>
      <Card style={{ backgroundColor: c.primarySoft, borderColor: c.primary }}>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: guideOpen }} onPress={() => setGuideOpen(!guideOpen)}>
          <Row style={{ justifyContent: 'space-between' }}>
            <Row>
              <Ionicons name="bulb-outline" size={20} color={c.primary} />
              <Text style={{ fontWeight: '800', color: c.text, fontSize: font.md }}>How to capture a room (2 min)</Text>
            </Row>
            <Ionicons name={guideOpen ? 'chevron-up' : 'chevron-down'} size={20} color={c.primary} />
          </Row>
        </Pressable>
        {guideOpen ? (
          <View style={{ gap: 6 }}>
            <P>1. Turn on the lights and open the curtains.</P>
            <P>2. Stand in the <Text style={{ fontWeight: '800' }}>centre</Text> of the room, phone at chest height.</P>
            <P>3. <Text style={{ fontWeight: '800' }}>Photos:</Text> turn on the spot and take a photo every step (~30°) — 12 or more, each overlapping the last by about a third. Then a few tilted up and down.</P>
            <P>4. <Text style={{ fontWeight: '800' }}>Or video:</Text> record one slow full turn (~30 s), then one looking slightly up and one slightly down.</P>
            <P muted>Don’t walk while capturing — just rotate. Keep people out of the frame.</P>
          </View>
        ) : null}
      </Card>

      {notice ? <Banner text={notice} /> : null}

      {processing ? (
        <Card>
          <Row>
            <Ionicons name="cube-outline" size={22} color={c.primary} />
            <Text style={{ fontWeight: '800', color: c.text, fontSize: font.md, flex: 1 }}>Building your 3D tour…</Text>
            <Text style={{ color: c.muted }}>{Math.round(tour.progress * 100)}%</Text>
          </Row>
          <ProgressBar value={tour.progress} />
          <P muted accessibilityLiveRegion="polite">{tour.message ?? 'Waiting in queue'} — you can leave this screen, we’ll keep working.</P>
        </Card>
      ) : tour.status === 'ready' ? (
        <Banner tone="success" text={tour.message ?? 'Your 3D tour is ready'} />
      ) : tour.status === 'failed' ? (
        <Banner tone="danger" text={tour.message ?? 'Processing failed. See tips under each room.'} />
      ) : null}

      <H2>Rooms ({tour.rooms.length})</H2>
      {tour.rooms.map((room) => {
        const size = SIZES.find((s) => Math.abs(s.w - room.width_m) < 0.05 && Math.abs(s.l - room.length_m) < 0.05)?.key;
        const uploading = upload?.room === room.id;
        return (
          <Card key={room.id}>
            <Row style={{ justifyContent: 'space-between' }}>
              <Text style={{ fontWeight: '800', fontSize: font.lg, color: c.text }}>{room.name}</Text>
              <Badge
                label={room.status === 'ready' ? '3D ready' : room.status === 'failed' ? 'Failed' : room.status === 'processing' ? 'Processing' : room.input_count ? `${room.input_count} ${room.input_kind === 'video' ? 'video' : 'photos'}` : 'No media yet'}
                tone={room.status === 'ready' ? 'success' : room.status === 'failed' ? 'danger' : room.input_count ? 'primary' : 'warning'}
              />
            </Row>
            {room.preview_url ? <Image source={{ uri: mediaUrl(room.preview_url) }} style={{ width: '100%', aspectRatio: 2, borderRadius: 10 }} accessibilityLabel={`${room.name} panorama preview`} /> : null}
            {room.status === 'failed' ? <Banner tone="danger" text={room.error_message ?? 'Could not build this room'} /> : null}
            {room.hints.map((h) => (
              <Row key={h} style={{ alignItems: 'flex-start' }}>
                <Ionicons name="information-circle-outline" size={18} color={c.warning} />
                <P muted style={{ flex: 1, fontSize: font.sm }}>{h}</P>
              </Row>
            ))}
            <Text style={{ color: c.muted, fontSize: font.sm, fontWeight: '600' }}>Room size</Text>
            <Row wrap>
              {SIZES.map((s) => (
                <Chip
                  key={s.key}
                  label={s.label}
                  selected={size === s.key}
                  onPress={() => run('size' + room.id, async () => { await api(`/tours/${tour.id}/rooms/${room.id}`, { method: 'PATCH', body: { width_m: s.w, length_m: s.l } }); await refresh(tour.id); })}
                />
              ))}
            </Row>
            {uploading ? (
              <View style={{ gap: 6 }}>
                <P muted accessibilityLiveRegion="polite">Uploading {upload!.done}/{upload!.total}…</P>
                <ProgressBar value={upload!.total ? upload!.done / upload!.total : 0} />
              </View>
            ) : !processing ? (
              <Row wrap gap={space.sm}>
                {room.input_kind !== 'video' ? (
                  <>
                    {Platform.OS !== 'web' ? <Button compact title="Take photos" icon="camera-outline" onPress={() => pick(room, 'images', true)} /> : null}
                    <Button compact title={room.input_count ? 'Add photos' : 'Choose photos'} icon="images-outline" variant={Platform.OS === 'web' ? 'primary' : 'secondary'} onPress={() => pick(room, 'images')} />
                  </>
                ) : null}
                {room.input_count === 0 ? (
                  <>
                    {Platform.OS !== 'web' ? <Button compact title="Record video" icon="videocam-outline" variant="secondary" onPress={() => pick(room, 'videos', true)} /> : null}
                    <Button compact title="Choose video" icon="film-outline" variant="secondary" onPress={() => pick(room, 'videos')} />
                  </>
                ) : (
                  <Button compact title="Clear media" icon="refresh-outline" variant="ghost" onPress={async () => { if (await confirm('Clear media?', `Remove all photos/videos for ${room.name}?`, 'Clear', true)) run('clear', async () => { await api(`/tours/${tour.id}/rooms/${room.id}/inputs`, { method: 'DELETE' }); await refresh(tour.id); }); }} />
                )}
                <Button compact title="Remove room" icon="trash-outline" variant="ghost" onPress={async () => { if (await confirm('Remove room?', `${room.name} and its media will be deleted.`, 'Remove', true)) run('del', async () => { await api(`/tours/${tour.id}/rooms/${room.id}`, { method: 'DELETE' }); await refresh(tour.id); }); }} />
              </Row>
            ) : null}
          </Card>
        );
      })}

      {!processing && tour.rooms.length < 12 ? (
        <Card>
          <H2>Add a room</H2>
          <Row wrap>
            {ROOM_NAMES.filter((n) => !tour.rooms.some((r) => r.name === n)).map((n) => (
              <Chip key={n} label={`+ ${n}`} onPress={() => addRoom(n)} />
            ))}
          </Row>
          <Row>
            <View style={{ flex: 1 }}>
              <Field label="Or a custom name" value={newRoom} onChangeText={setNewRoom} maxLength={40} placeholder="e.g. Room 3" onSubmitEditing={() => newRoom.trim() && addRoom(newRoom)} />
            </View>
          </Row>
          <Button title="Add room" variant="secondary" disabled={!newRoom.trim()} loading={busy === 'add'} onPress={() => addRoom(newRoom)} />
        </Card>
      ) : null}

      {!processing ? (
        <Button
          title={tour.status === 'ready' || tour.status === 'failed' ? 'Rebuild 3D tour' : 'Build 3D tour'}
          icon="sparkles-outline"
          disabled={!allHaveMedia || !!upload}
          loading={busy === 'process'}
          onPress={process}
          accessibilityHint="Starts processing your photos and videos on our servers"
        />
      ) : null}
      {!allHaveMedia && tour.rooms.length ? <P muted style={{ textAlign: 'center' }}>Add photos or a video to every room to build the tour.</P> : null}
      {tour.rooms.some((r) => r.status === 'ready') ? <Button title="Preview 3D tour" icon="eye-outline" variant="secondary" loading={busy === 'preview'} onPress={preview} /> : null}
    </Screen>
  );
}

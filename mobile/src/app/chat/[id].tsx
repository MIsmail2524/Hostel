import { Stack, useLocalSearchParams, router } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Banner, Ionicons, Loading } from '../../components/ui';
import { api, ApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { ago } from '../../lib/format';
import { font, MIN_TOUCH, radius, space, useColors } from '../../lib/theme';
import type { Conversation, Message } from '../../lib/types';

const POLL_MS = 5000;

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const c = useColors();
  const { user } = useAuth();
  const [conv, setConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const listRef = useRef<FlatList<Message>>(null);

  const load = useCallback(async () => {
    try {
      const [cv, ms] = await Promise.all([api<Conversation>(`/conversations/${id}`), api<Message[]>(`/conversations/${id}/messages`)]);
      setConv(cv);
      setMessages(ms);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load messages');
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS); // MVP: polling; production → WebSocket/push
    return () => clearInterval(t);
  }, [load]);

  const send = async () => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    const optimistic: Message = { id: `tmp-${Date.now()}`, sender_id: user!.id, body, created_at: new Date().toISOString(), read_at: null };
    setMessages((m) => [...(m ?? []), optimistic]);
    setText('');
    try {
      const saved = await api<Message>(`/conversations/${id}/messages`, { body: { body } });
      setMessages((m) => (m ?? []).map((x) => (x.id === optimistic.id ? saved : x)));
    } catch (e) {
      setMessages((m) => (m ?? []).filter((x) => x.id !== optimistic.id));
      setText(body); // never lose what the user typed
      setError(e instanceof ApiError ? e.message : 'Message not sent');
    } finally {
      setSending(false);
    }
  };

  if (!messages && !error) return <Loading />;
  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: c.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      <Stack.Screen options={{ title: conv?.other_party.full_name ?? 'Chat' }} />
      {conv ? (
        <Pressable accessibilityRole="link" onPress={() => router.push(`/listing/${conv.listing_id}`)} style={{ padding: space.md, backgroundColor: c.surface, borderBottomWidth: 1, borderBottomColor: c.border }}>
          <Text numberOfLines={1} style={{ color: c.primary, fontWeight: '700' }}>
            <Ionicons name="home-outline" size={14} /> {conv.listing_title}
          </Text>
        </Pressable>
      ) : null}
      {error ? <View style={{ padding: space.md }}><Banner text={error} onRetry={load} /></View> : null}
      <FlatList
        ref={listRef}
        data={messages ?? []}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: space.lg, gap: space.sm, maxWidth: 720, width: '100%', alignSelf: 'center' }}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
        ListHeaderComponent={<Banner tone="primary" icon="shield-checkmark" text="For your safety, never send advance money before visiting. Report anything suspicious." />}
        renderItem={({ item }) => {
          const mine = item.sender_id === user?.id;
          return (
            <View style={{ alignSelf: mine ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
              <View style={{ backgroundColor: mine ? c.primary : c.surface, borderWidth: mine ? 0 : 1, borderColor: c.border, paddingHorizontal: space.md, paddingVertical: space.sm, borderRadius: radius.lg, borderBottomRightRadius: mine ? 4 : radius.lg, borderBottomLeftRadius: mine ? radius.lg : 4 }}>
                <Text style={{ color: mine ? c.primaryText : c.text, fontSize: font.md }}>{item.body}</Text>
              </View>
              <Text style={{ color: c.subtle, fontSize: font.xs, alignSelf: mine ? 'flex-end' : 'flex-start', marginTop: 2 }}>
                {item.id.startsWith('tmp-') ? 'Sending…' : ago(item.created_at)}
                {mine && item.read_at ? ' · Seen' : ''}
              </Text>
            </View>
          );
        }}
      />
      <SafeAreaView edges={['bottom']} style={{ backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.border }}>
        <View style={{ flexDirection: 'row', gap: space.sm, padding: space.sm, alignItems: 'flex-end', maxWidth: 720, width: '100%', alignSelf: 'center' }}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Write a message"
            placeholderTextColor={c.subtle}
            accessibilityLabel="Message"
            multiline
            maxLength={2000}
            style={{ flex: 1, minHeight: MIN_TOUCH, maxHeight: 120, borderWidth: 1.5, borderColor: c.border, borderRadius: radius.lg, paddingHorizontal: space.md, paddingVertical: 10, color: c.text, fontSize: font.md, backgroundColor: c.bg }}
            onSubmitEditing={send}
            blurOnSubmit={false}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Send message"
            accessibilityState={{ disabled: !text.trim() }}
            onPress={send}
            style={{ width: MIN_TOUCH + 4, height: MIN_TOUCH + 4, borderRadius: 24, backgroundColor: text.trim() ? c.primary : c.surfaceAlt, alignItems: 'center', justifyContent: 'center' }}
          >
            <Ionicons name="send" size={20} color={text.trim() ? c.primaryText : c.subtle} />
          </Pressable>
        </View>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

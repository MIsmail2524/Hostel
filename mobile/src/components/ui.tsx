import Ionicons from '@expo/vector-icons/Ionicons';
import { forwardRef, type ComponentProps, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { font, MIN_TOUCH, radius, space, useColors } from '../lib/theme';

export type IconName = ComponentProps<typeof Ionicons>['name'];

export function Screen({ children, scroll = true, style, edges }: { children: ReactNode; scroll?: boolean; style?: StyleProp<ViewStyle>; edges?: ('top' | 'bottom')[] }) {
  const c = useColors();
  const inner = scroll ? (
    <ScrollView contentContainerStyle={[{ padding: space.lg, paddingBottom: space.xxl * 2, gap: space.lg }, style]} keyboardShouldPersistTaps="handled">
      {children}
    </ScrollView>
  ) : (
    <View style={[{ flex: 1 }, style]}>{children}</View>
  );
  return (
    <SafeAreaView edges={edges ?? []} style={{ flex: 1, backgroundColor: c.bg }}>
      {inner}
    </SafeAreaView>
  );
}

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export function Button({
  title,
  onPress,
  variant = 'primary',
  loading,
  disabled,
  icon,
  style,
  accessibilityHint,
  compact,
}: {
  title: string;
  onPress?: () => void;
  variant?: BtnVariant;
  loading?: boolean;
  disabled?: boolean;
  icon?: IconName;
  style?: StyleProp<ViewStyle>;
  accessibilityHint?: string;
  compact?: boolean;
}) {
  const c = useColors();
  const bg = { primary: c.primary, secondary: c.surfaceAlt, ghost: 'transparent', danger: c.danger }[variant];
  const fg = { primary: c.primaryText, secondary: c.text, ghost: c.primary, danger: '#fff' }[variant];
  const off = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: !!off, busy: !!loading }}
      onPress={off ? undefined : onPress}
      style={({ pressed }) => [
        styles.btn,
        compact && { paddingHorizontal: space.md, minHeight: 40 },
        { backgroundColor: bg, opacity: off ? 0.55 : pressed ? 0.85 : 1, borderColor: variant === 'secondary' ? c.border : 'transparent' },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={18} color={fg} /> : null}
      <Text style={[styles.btnText, { color: fg }]}>{title}</Text>
    </Pressable>
  );
}

export const Field = forwardRef<TextInput, TextInputProps & { label: string; error?: string; hint?: string; right?: ReactNode }>(function Field(
  { label, error, hint, right, style, ...props },
  ref,
) {
  const c = useColors();
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ color: c.text, fontWeight: '600', fontSize: font.sm }} nativeID={`lbl-${label}`}>
        {label}
      </Text>
      <View style={[styles.input, { borderColor: error ? c.danger : c.border, backgroundColor: c.surface }]}>
        <TextInput
          ref={ref}
          placeholderTextColor={c.subtle}
          accessibilityLabel={label}
          accessibilityLabelledBy={`lbl-${label}`}
          style={[{ flex: 1, color: c.text, fontSize: font.md, paddingVertical: 10, minHeight: MIN_TOUCH }, style]}
          {...props}
        />
        {right}
      </View>
      {error ? (
        <Text accessibilityLiveRegion="polite" style={{ color: c.danger, fontSize: font.sm }}>
          {error}
        </Text>
      ) : hint ? (
        <Text style={{ color: c.subtle, fontSize: font.xs }}>{hint}</Text>
      ) : null}
    </View>
  );
});

export function Chip({ label, selected, onPress, icon }: { label: string; selected?: boolean; onPress?: () => void; icon?: IconName }) {
  const c = useColors();
  return (
    <Pressable
      accessibilityRole={onPress ? 'checkbox' : 'text'}
      accessibilityState={onPress ? { checked: !!selected } : undefined}
      accessibilityLabel={label}
      onPress={onPress}
      hitSlop={6}
      style={[styles.chip, { backgroundColor: selected ? c.primary : c.surface, borderColor: selected ? c.primary : c.border }]}
    >
      {icon ? <Ionicons name={icon} size={14} color={selected ? c.primaryText : c.muted} /> : null}
      <Text style={{ color: selected ? c.primaryText : c.text, fontSize: font.sm, fontWeight: selected ? '700' : '500' }}>{label}</Text>
    </Pressable>
  );
}

export function Badge({ label, tone = 'neutral', icon }: { label: string; tone?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger'; icon?: IconName }) {
  const c = useColors();
  const map = {
    neutral: [c.surfaceAlt, c.muted],
    primary: [c.primarySoft, c.primary],
    success: [c.successSoft, c.success],
    warning: [c.warningSoft, c.warning],
    danger: [c.dangerSoft, c.danger],
  } as const;
  const [bg, fg] = map[tone];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      {icon ? <Ionicons name={icon} size={12} color={fg} /> : null}
      <Text style={{ color: fg, fontSize: font.xs, fontWeight: '700' }}>{label}</Text>
    </View>
  );
}

export function Card({ children, style, onPress, accessibilityLabel }: { children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; accessibilityLabel?: string }) {
  const c = useColors();
  const base = [styles.card, { backgroundColor: c.surface, borderColor: c.border }, style];
  if (!onPress) return <View style={base}>{children}</View>;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={accessibilityLabel} onPress={onPress} style={({ pressed }) => [base, pressed && { opacity: 0.9 }]}>
      {children}
    </Pressable>
  );
}

export function H1({ children }: { children: ReactNode }) {
  const c = useColors();
  return (
    <Text accessibilityRole="header" style={{ fontSize: font.xxl, fontWeight: '800', color: c.text }}>
      {children}
    </Text>
  );
}

export function H2({ children, right }: { children: ReactNode; right?: ReactNode }) {
  const c = useColors();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
      <Text accessibilityRole="header" style={{ fontSize: font.lg, fontWeight: '700', color: c.text }}>
        {children}
      </Text>
      {right}
    </View>
  );
}

export function P({ children, muted, style, numberOfLines, accessibilityLiveRegion }: { children: ReactNode; muted?: boolean; style?: object; numberOfLines?: number; accessibilityLiveRegion?: 'none' | 'polite' | 'assertive' }) {
  const c = useColors();
  return (
    <Text numberOfLines={numberOfLines} accessibilityLiveRegion={accessibilityLiveRegion} style={[{ fontSize: font.md, lineHeight: 22, color: muted ? c.muted : c.text }, style]}>
      {children}
    </Text>
  );
}

export function Banner({ text, tone = 'danger', onRetry, icon }: { text: string; tone?: 'danger' | 'warning' | 'success' | 'primary'; onRetry?: () => void; icon?: IconName }) {
  const c = useColors();
  const map = { danger: [c.dangerSoft, c.danger, 'alert-circle'], warning: [c.warningSoft, c.warning, 'warning'], success: [c.successSoft, c.success, 'checkmark-circle'], primary: [c.primarySoft, c.primary, 'information-circle'] } as const;
  const [bg, fg, ic] = map[tone];
  return (
    <View accessibilityRole="alert" style={[styles.banner, { backgroundColor: bg }]}>
      <Ionicons name={icon ?? (ic as IconName)} size={20} color={fg} />
      <Text style={{ color: fg, flex: 1, fontSize: font.sm, fontWeight: '600' }}>{text}</Text>
      {onRetry ? (
        <Pressable accessibilityRole="button" onPress={onRetry} hitSlop={10}>
          <Text style={{ color: fg, fontWeight: '800' }}>Retry</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function Empty({ icon, title, body, action }: { icon: IconName; title: string; body?: string; action?: ReactNode }) {
  const c = useColors();
  return (
    <View style={{ alignItems: 'center', padding: space.xxl, gap: space.md }}>
      <View style={{ backgroundColor: c.primarySoft, borderRadius: 40, padding: 18 }}>
        <Ionicons name={icon} size={34} color={c.primary} />
      </View>
      <Text style={{ fontSize: font.lg, fontWeight: '700', color: c.text, textAlign: 'center' }}>{title}</Text>
      {body ? <Text style={{ color: c.muted, textAlign: 'center', fontSize: font.md, lineHeight: 22 }}>{body}</Text> : null}
      {action}
    </View>
  );
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  const c = useColors();
  return (
    <View accessibilityLabel={label} accessibilityRole="progressbar" style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.xxl, gap: space.md }}>
      <ActivityIndicator size="large" color={c.primary} />
      <Text style={{ color: c.muted }}>{label}</Text>
    </View>
  );
}

export function Row({ children, gap = space.sm, wrap, style }: { children: ReactNode; gap?: number; wrap?: boolean; style?: StyleProp<ViewStyle> }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap, flexWrap: wrap ? 'wrap' : 'nowrap' }, style]}>{children}</View>;
}

export function ProgressBar({ value }: { value: number }) {
  const c = useColors();
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <View accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: pct }} style={{ height: 8, borderRadius: 8, backgroundColor: c.surfaceAlt, overflow: 'hidden' }}>
      <View style={{ width: `${pct}%`, height: '100%', backgroundColor: c.primary }} />
    </View>
  );
}

export function IconButton({ icon, label, onPress, color }: { icon: IconName; label: string; onPress: () => void; color?: string }) {
  const c = useColors();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} hitSlop={8} style={({ pressed }) => [styles.iconBtn, { opacity: pressed ? 0.6 : 1 }]}>
      <Ionicons name={icon} size={24} color={color ?? c.text} />
    </Pressable>
  );
}

export { Ionicons };

const styles = StyleSheet.create({
  btn: { minHeight: MIN_TOUCH + 4, borderRadius: radius.md, paddingHorizontal: space.lg, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm, borderWidth: 1 },
  btnText: { fontSize: font.md, fontWeight: '700' },
  input: { borderWidth: 1.5, borderRadius: radius.md, paddingHorizontal: space.md, flexDirection: 'row', alignItems: 'center' },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, minHeight: 38, borderRadius: radius.pill, borderWidth: 1 },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill, alignSelf: 'flex-start' },
  card: { borderRadius: radius.lg, borderWidth: 1, padding: space.lg, gap: space.sm },
  banner: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md, borderRadius: radius.md },
  iconBtn: { minWidth: MIN_TOUCH, minHeight: MIN_TOUCH, alignItems: 'center', justifyContent: 'center' },
});

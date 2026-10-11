import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Switch, Text, View } from 'react-native';

import { Banner, Button, Chip, Field, H2, Loading, P, ProgressBar, Row, Screen } from '../../components/ui';
import { api, ApiError } from '../../lib/api';
import { AMENITY_LABEL, CITIES, GENDER_LABEL, SPACE_HELP, SPACE_LABEL } from '../../lib/format';
import { font, space, useColors } from '../../lib/theme';
import type { GenderPolicy, Listing, SpaceType } from '../../lib/types';

interface Form {
  title: string;
  description: string;
  space_type: SpaceType | null;
  gender_policy: GenderPolicy | null;
  property_name: string;
  rent_monthly: string;
  deposit: string;
  bills_included: boolean;
  meals_included: boolean;
  capacity: string;
  available_beds: string;
  amenities: string[];
  rules: string;
  city: string;
  area: string;
  address_line: string;
}

const BLANK: Form = {
  title: '', description: '', space_type: null, gender_policy: null, property_name: '', rent_monthly: '', deposit: '', bills_included: false,
  meals_included: false, capacity: '1', available_beds: '1', amenities: [], rules: '', city: '', area: '', address_line: '',
};
const STEPS = ['Type', 'Location', 'Price', 'Details'];

export default function EditListing() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const c = useColors();
  const [f, setF] = useState<Form>(BLANK);
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(!!id);

  useEffect(() => {
    if (!id) return;
    api<Listing>(`/listings/${id}`)
      .then((l) =>
        setF({
          title: l.title, description: l.description, space_type: l.space_type, gender_policy: l.gender_policy, property_name: l.property_name ?? '',
          rent_monthly: String(l.rent_monthly), deposit: String(l.deposit), bills_included: l.bills_included, meals_included: l.meals_included,
          capacity: String(l.capacity), available_beds: String(l.available_beds), amenities: l.amenities, rules: l.rules, city: l.city, area: l.area,
          address_line: l.address_line ?? '',
        }),
      )
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not load listing'))
      .finally(() => setLoading(false));
  }, [id]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => {
    setF((p) => ({ ...p, [k]: v }));
    setErrors((e) => ({ ...e, [k]: '' }));
  };

  const validate = (s: number) => {
    const e: Record<string, string> = {};
    if (s === 0) {
      if (!f.space_type) e.space_type = 'Choose what you are renting out';
      if (!f.gender_policy) e.gender_policy = 'Choose who can stay';
      if (f.title.trim().length < 8) e.title = 'Write a short title (at least 8 characters)';
    }
    if (s === 1) {
      if (f.city.trim().length < 2) e.city = 'Choose a city';
      if (f.area.trim().length < 2) e.area = 'Enter the area or neighbourhood';
      if (f.address_line.trim().length < 5) e.address_line = 'Enter the street address';
    }
    if (s === 2) {
      const rent = Number(f.rent_monthly);
      if (!rent || rent < 1000) e.rent_monthly = 'Enter the monthly rent (at least Rs 1,000)';
      const cap = Number(f.capacity), avail = Number(f.available_beds);
      if (!cap || cap < 1) e.capacity = 'At least 1';
      if (avail > cap) e.available_beds = 'Cannot be more than capacity';
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const save = async () => {
    for (let s = 0; s < 3; s++) if (!validate(s)) return setStep(s);
    setBusy(true);
    setError(null);
    const body = {
      ...f,
      property_name: f.property_name.trim() || null,
      rent_monthly: Number(f.rent_monthly),
      deposit: Number(f.deposit || 0),
      capacity: Number(f.capacity),
      available_beds: Number(f.available_beds),
    };
    try {
      const l = id ? await api<Listing>(`/listings/${id}`, { method: 'PUT', body }) : await api<Listing>('/listings', { body });
      router.replace(`/manage/${l.id}`);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        setErrors(e.fields);
      } else setError('Could not save');
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Loading />;
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Stack.Screen options={{ title: id ? 'Edit listing' : 'New listing' }} />
      <Screen style={{ maxWidth: 640, width: '100%', alignSelf: 'center' }}>
        <View style={{ gap: space.sm }}>
          <Text style={{ color: c.muted, fontWeight: '600' }} accessibilityLiveRegion="polite">
            Step {step + 1} of {STEPS.length} · {STEPS[step]}
          </Text>
          <ProgressBar value={(step + 1) / STEPS.length} />
        </View>
        {error ? <Banner text={error} /> : null}
        {id ? <Banner tone="warning" text="Changes to a live listing are re-checked by our team before they go public (usually within a few hours)." /> : null}

        {step === 0 ? (
          <>
            <View style={{ gap: space.sm }}>
              <H2>What are you renting out?</H2>
              {(Object.keys(SPACE_LABEL) as SpaceType[]).map((t) => (
                <Chip key={t} label={`${SPACE_LABEL[t]} — ${SPACE_HELP[t]}`} selected={f.space_type === t} onPress={() => set('space_type', t)} />
              ))}
              {errors.space_type ? <Text style={{ color: c.danger }}>{errors.space_type}</Text> : null}
            </View>
            <View style={{ gap: space.sm }}>
              <H2>Who can stay?</H2>
              <Row wrap>
                {(Object.keys(GENDER_LABEL) as GenderPolicy[]).map((g) => (
                  <Chip key={g} label={GENDER_LABEL[g]} selected={f.gender_policy === g} onPress={() => set('gender_policy', g)} />
                ))}
              </Row>
              {errors.gender_policy ? <Text style={{ color: c.danger }}>{errors.gender_policy}</Text> : null}
            </View>
            <Field label="Title" value={f.title} onChangeText={(v) => set('title', v)} maxLength={100} placeholder="e.g. Bed in 3-seater room near UET" error={errors.title} hint={`${f.title.length}/100`} />
            <Field label="Hostel / building name (optional)" value={f.property_name} onChangeText={(v) => set('property_name', v)} maxLength={100} />
            <Field label="Description" value={f.description} onChangeText={(v) => set('description', v)} multiline maxLength={4000} style={{ minHeight: 110, textAlignVertical: 'top' }} placeholder="What makes it a good place to live? Nearby universities, transport, food…" error={errors.description} />
          </>
        ) : step === 1 ? (
          <>
            <View style={{ gap: space.sm }}>
              <H2>City</H2>
              <Row wrap>
                {CITIES.map((city) => (
                  <Chip key={city} label={city} selected={f.city === city} onPress={() => set('city', city)} />
                ))}
              </Row>
              {errors.city ? <Text style={{ color: c.danger }}>{errors.city}</Text> : null}
            </View>
            <Field label="Area / neighbourhood" value={f.area} onChangeText={(v) => set('area', v)} placeholder="e.g. Johar Town, Block R1" error={errors.area} hint="Shown publicly" />
            <Field label="Street address" value={f.address_line} onChangeText={(v) => set('address_line', v)} placeholder="House / flat number and street" error={errors.address_line} hint="Private — only shared with people whose visit you accept" />
          </>
        ) : step === 2 ? (
          <>
            <Field label="Monthly rent (Rs)" keyboardType="number-pad" value={f.rent_monthly} onChangeText={(v) => set('rent_monthly', v.replace(/\D/g, ''))} error={errors.rent_monthly} placeholder="15000" />
            <Field label="Security deposit (Rs)" keyboardType="number-pad" value={f.deposit} onChangeText={(v) => set('deposit', v.replace(/\D/g, ''))} placeholder="0" error={errors.deposit} />
            <Row gap={space.md}>
              <View style={{ flex: 1 }}>
                <Field label="Total beds / capacity" keyboardType="number-pad" value={f.capacity} onChangeText={(v) => set('capacity', v.replace(/\D/g, ''))} error={errors.capacity} />
              </View>
              <View style={{ flex: 1 }}>
                <Field label="Available now" keyboardType="number-pad" value={f.available_beds} onChangeText={(v) => set('available_beds', v.replace(/\D/g, ''))} error={errors.available_beds} />
              </View>
            </Row>
            <Row style={{ justifyContent: 'space-between' }}>
              <Text style={{ color: c.text, fontSize: font.md }}>Bills (electricity, gas, internet) included</Text>
              <Switch value={f.bills_included} onValueChange={(v) => set('bills_included', v)} accessibilityLabel="Bills included" trackColor={{ true: c.primary }} />
            </Row>
            <Row style={{ justifyContent: 'space-between' }}>
              <Text style={{ color: c.text, fontSize: font.md }}>Meals included</Text>
              <Switch value={f.meals_included} onValueChange={(v) => set('meals_included', v)} accessibilityLabel="Meals included" trackColor={{ true: c.primary }} />
            </Row>
          </>
        ) : (
          <>
            <View style={{ gap: space.sm }}>
              <H2>Amenities</H2>
              <P muted>Select everything available to the tenant.</P>
              <Row wrap>
                {Object.entries(AMENITY_LABEL).map(([k, label]) => (
                  <Chip key={k} label={label} selected={f.amenities.includes(k)} onPress={() => set('amenities', f.amenities.includes(k) ? f.amenities.filter((x) => x !== k) : [...f.amenities, k])} />
                ))}
              </Row>
            </View>
            <Field label="House rules (optional)" value={f.rules} onChangeText={(v) => set('rules', v)} multiline maxLength={2000} style={{ minHeight: 90, textAlignVertical: 'top' }} placeholder="Timings, guests, smoking, cooking…" />
          </>
        )}

        <Row gap={space.md}>
          {step > 0 ? <Button title="Back" variant="secondary" style={{ flex: 1 }} onPress={() => setStep(step - 1)} /> : null}
          {step < STEPS.length - 1 ? (
            <Button title="Next" style={{ flex: 2 }} onPress={() => validate(step) && setStep(step + 1)} />
          ) : (
            <Button title={id ? 'Save changes' : 'Save & continue'} style={{ flex: 2 }} loading={busy} onPress={save} />
          )}
        </Row>
      </Screen>
    </KeyboardAvoidingView>
  );
}

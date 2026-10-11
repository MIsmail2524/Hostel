import type { GenderPolicy, SpaceType } from './types';

export const SPACE_LABEL: Record<SpaceType, string> = {
  bed_space: 'Bed space',
  shared_room: 'Shared room',
  private_room: 'Private room',
  portion: 'Portion',
  hostel_seat: 'Hostel seat',
};

export const SPACE_HELP: Record<SpaceType, string> = {
  bed_space: 'One bed in a room shared with others',
  shared_room: 'A whole room shared by 2–4 people',
  private_room: 'A room for one person/couple in a flat or house',
  portion: 'A separate portion (room + kitchen/bath)',
  hostel_seat: 'A seat in a managed hostel',
};

export const GENDER_LABEL: Record<GenderPolicy, string> = {
  male: 'Boys / men',
  female: 'Girls / women',
  family: 'Family',
  any: 'Anyone',
};

export const AMENITY_LABEL: Record<string, string> = {
  wifi: 'Wi-Fi', ac: 'AC', ups: 'UPS backup', generator: 'Generator', solar: 'Solar', geyser: 'Geyser', attached_bath: 'Attached bath',
  kitchen: 'Kitchen', laundry: 'Laundry', meals: 'Meals', parking: 'Parking', cctv: 'CCTV', security_guard: 'Security guard',
  furnished: 'Furnished', study_table: 'Study table', cupboard: 'Cupboard', fridge: 'Fridge', lift: 'Lift', prayer_area: 'Prayer area',
  gym: 'Gym', water_filter: 'Water filter', gas: 'Gas', balcony: 'Balcony',
};

export const CITIES = ['Lahore', 'Karachi', 'Islamabad', 'Rawalpindi', 'Faisalabad', 'Multan', 'Peshawar', 'Quetta'];

export function pkr(n: number) {
  return `Rs ${n.toLocaleString('en-PK')}`;
}

export function shortDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-PK', { day: 'numeric', month: 'short' });
}

export function dateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString('en-PK', { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
}

export function ago(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return shortDate(iso);
}

export const STATUS_LABEL: Record<string, string> = {
  draft: 'Draft',
  pending_review: 'In review',
  active: 'Live',
  paused: 'Paused',
  rented: 'Rented out',
  rejected: 'Needs changes',
};

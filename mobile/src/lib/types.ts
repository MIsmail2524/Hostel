export type SpaceType = 'bed_space' | 'shared_room' | 'private_room' | 'portion' | 'hostel_seat';
export type GenderPolicy = 'male' | 'female' | 'family' | 'any';

export interface User {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  is_owner: boolean;
  is_admin: boolean;
  contact_verified: boolean;
  is_verified_owner: boolean;
  gender: string | null;
  bio: string | null;
  created_at: string;
}

export interface PublicUser {
  id: string;
  full_name: string;
  is_verified_owner: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
}

export interface ListingCard {
  id: string;
  title: string;
  space_type: SpaceType;
  gender_policy: GenderPolicy;
  rent_monthly: number;
  bills_included: boolean;
  meals_included: boolean;
  available_beds: number;
  city: string;
  area: string;
  cover_url: string | null;
  has_tour: boolean;
  owner_verified: boolean;
  rating: number | null;
  review_count: number;
  status: string;
  created_at: string;
}

export interface Photo {
  id: string;
  url: string;
  thumb_url: string;
  width: number;
  height: number;
}

export interface TourBrief {
  id: string;
  status: string;
  progress: number;
  rooms: number;
  preview_url: string | null;
}

export interface Listing extends ListingCard {
  description: string;
  property_name: string | null;
  deposit: number;
  capacity: number;
  amenities: string[];
  rules: string;
  approx_lat: number | null;
  approx_lng: number | null;
  available_from: string | null;
  photos: Photo[];
  tour: TourBrief | null;
  owner: PublicUser;
  is_favorite: boolean;
  views: number;
  rejection_reason: string | null;
  address_line: string | null;
  lat: number | null;
  lng: number | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Room {
  id: string;
  name: string;
  position: number;
  input_kind: 'photos' | 'video' | null;
  input_count: number;
  width_m: number;
  length_m: number;
  height_m: number;
  status: 'draft' | 'processing' | 'ready' | 'failed';
  error_code: string | null;
  error_message: string | null;
  hints: string[];
  quality: Record<string, number | string | string[]>;
  preview_url: string | null;
  yaw_offset_deg: number;
}

export interface Tour {
  id: string;
  listing_id: string;
  engine: string;
  status: 'draft' | 'queued' | 'processing' | 'ready' | 'failed';
  progress: number;
  message: string | null;
  rooms: Room[];
  updated_at: string;
}

export interface Conversation {
  id: string;
  listing_id: string;
  listing_title: string;
  listing_cover_url: string | null;
  other_party: PublicUser;
  role: 'seeker' | 'owner';
  last_message: string | null;
  last_message_at: string;
  unread: number;
}

export interface Message {
  id: string;
  sender_id: string;
  body: string;
  created_at: string;
  read_at: string | null;
}

export interface Visit {
  id: string;
  listing_id: string;
  listing_title: string;
  seeker: PublicUser;
  proposed_at: string;
  note: string;
  status: 'pending' | 'accepted' | 'declined' | 'cancelled';
  role: 'seeker' | 'owner';
  address_line: string | null;
  created_at: string;
}

export interface Review {
  id: string;
  rating: number;
  body: string;
  owner_reply: string | null;
  author_name: string;
  created_at: string;
}

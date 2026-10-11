import { useLocalSearchParams } from 'expo-router';

import { TourView } from '../../components/TourView';

export default function TourScreen() {
  const { id, preview } = useLocalSearchParams<{ id: string; preview?: string }>();
  // Only allow viewer paths on our own API origin (no open redirect via params).
  const path = preview && preview.startsWith('/viewer/?') ? preview : `/viewer/?tour=${encodeURIComponent(id)}`;
  return <TourView path={path} />;
}

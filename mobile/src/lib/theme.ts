import { useColorScheme } from 'react-native';

export const BRAND = 'Kamra';

const light = {
  bg: '#f8fafc',
  surface: '#ffffff',
  surfaceAlt: '#f1f5f9',
  text: '#0f172a',
  muted: '#475569', // 7.5:1 on white (WCAG AAA for body text)
  subtle: '#64748b',
  border: '#e2e8f0',
  primary: '#0f766e', // 5.4:1 on white
  primaryText: '#ffffff',
  primarySoft: '#ccfbf1',
  danger: '#b91c1c',
  dangerSoft: '#fee2e2',
  warning: '#b45309',
  warningSoft: '#fef3c7',
  success: '#15803d',
  successSoft: '#dcfce7',
  overlay: 'rgba(15,23,42,0.5)',
};

const dark: typeof light = {
  bg: '#0b1220',
  surface: '#111a2e',
  surfaceAlt: '#1a2540',
  text: '#f1f5f9',
  muted: '#cbd5e1',
  subtle: '#94a3b8',
  border: '#22304d',
  primary: '#2dd4bf',
  primaryText: '#042f2e',
  primarySoft: '#134e4a',
  danger: '#f87171',
  dangerSoft: '#450a0a',
  warning: '#fbbf24',
  warningSoft: '#451a03',
  success: '#4ade80',
  successSoft: '#052e16',
  overlay: 'rgba(0,0,0,0.6)',
};

export type Colors = typeof light;

export function useColors(): Colors {
  return useColorScheme() === 'dark' ? dark : light;
}

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 };
export const font = { xs: 12, sm: 14, md: 16, lg: 18, xl: 22, xxl: 28 };
export const MIN_TOUCH = 44; // Apple HIG / WCAG 2.5.5 target size

import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Native: Keychain (iOS) / Keystore-backed EncryptedSharedPreferences (Android).
// Web: sessionStorage — cleared when the tab closes, limiting token exposure (no httpOnly cookies on RN-web).
export async function getSecure(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    try {
      return globalThis.sessionStorage?.getItem(key) ?? null;
    } catch {
      return null;
    }
  }
  return SecureStore.getItemAsync(key);
}

export async function setSecure(key: string, value: string | null): Promise<void> {
  if (Platform.OS === 'web') {
    try {
      if (value === null) globalThis.sessionStorage?.removeItem(key);
      else globalThis.sessionStorage?.setItem(key, value);
    } catch {
      /* storage unavailable (private mode) — session stays in memory */
    }
    return;
  }
  if (value === null) await SecureStore.deleteItemAsync(key);
  else await SecureStore.setItemAsync(key, value, { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
}

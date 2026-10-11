import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from '../lib/auth';
import { useColors } from '../lib/theme';

function Nav() {
  const c = useColors();
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: c.surface },
        headerTintColor: c.text,
        headerTitleStyle: { fontWeight: '700' },
        contentStyle: { backgroundColor: c.bg },
        headerBackButtonDisplayMode: 'minimal',
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="auth/login" options={{ title: 'Log in', presentation: 'modal' }} />
      <Stack.Screen name="auth/register" options={{ title: 'Create account', presentation: 'modal' }} />
      <Stack.Screen name="auth/verify" options={{ title: 'Verify your number' }} />
      <Stack.Screen name="auth/forgot" options={{ title: 'Reset password' }} />
      <Stack.Screen name="listing/[id]" options={{ title: '' }} />
      <Stack.Screen name="listing/edit" options={{ title: 'Listing details' }} />
      <Stack.Screen name="manage/[id]" options={{ title: 'Manage listing' }} />
      <Stack.Screen name="tour/[id]" options={{ title: '3D tour', headerStyle: { backgroundColor: '#0b1220' }, headerTintColor: '#fff' }} />
      <Stack.Screen name="tour/builder" options={{ title: '3D tour builder' }} />
      <Stack.Screen name="chat/[id]" options={{ title: 'Chat' }} />
      <Stack.Screen name="visits" options={{ title: 'Visit requests' }} />
      <Stack.Screen name="admin" options={{ title: 'Moderation' }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="auto" />
        <Nav />
      </AuthProvider>
    </SafeAreaProvider>
  );
}

import { useState } from 'react';
import { View } from 'react-native';
import { WebView } from 'react-native-webview';

import { API_URL } from '../lib/api';
import { Banner, Loading } from './ui';

/** Native: hosts the self-contained three.js viewer in a sandboxed WebView. */
export function TourView({ path }: { path: string }) {
  const [error, setError] = useState<string | null>(null);
  const url = `${API_URL}${path}`;
  return (
    <View style={{ flex: 1, backgroundColor: '#0b1220' }}>
      {error ? <Banner text={error} /> : null}
      <WebView
        source={{ uri: url }}
        originWhitelist={[API_URL]}
        javaScriptEnabled
        domStorageEnabled
        allowsInlineMediaPlayback
        setSupportMultipleWindows={false}
        allowFileAccess={false}
        allowUniversalAccessFromFileURLs={false}
        mixedContentMode="never"
        startInLoadingState
        renderLoading={() => <Loading label="Opening 3D tour…" />}
        onShouldStartLoadWithRequest={(req) => req.url.startsWith(API_URL)}
        onMessage={(e) => {
          try {
            const msg = JSON.parse(e.nativeEvent.data);
            if (msg.type === 'error') setError(msg.message);
          } catch {
            /* ignore */
          }
        }}
        onError={() => setError('The 3D tour could not be loaded. Check your connection.')}
        style={{ flex: 1, backgroundColor: '#0b1220' }}
      />
    </View>
  );
}

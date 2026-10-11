import { createElement } from 'react';
import { View } from 'react-native';

import { API_URL } from '../lib/api';

/** Web: embeds the viewer in a sandboxed iframe (same viewer as the native WebView). */
export function TourView({ path }: { path: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: '#0b1220' }}>
      {createElement('iframe', {
        src: `${API_URL}${path}`,
        title: '3D tour',
        allow: 'fullscreen',
        allowFullScreen: true,
        sandbox: 'allow-scripts allow-same-origin allow-popups-to-escape-sandbox',
        referrerPolicy: 'no-referrer',
        style: { border: 0, width: '100%', height: '100%', flex: 1, backgroundColor: '#0b1220' },
      })}
    </View>
  );
}

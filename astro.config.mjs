import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://toknet.info',
  base: '/',
  output: 'static',
  build: {
    format: 'directory',
  },
  integrations: [
    sitemap(),
  ],
  vite: {
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor': ['astro'],
          },
        },
      },
    },
  },
});

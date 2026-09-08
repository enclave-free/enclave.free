import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const brand =
    process.env.VITE_DEMO_BRAND ??
    loadEnv(mode, process.cwd(), 'VITE_').VITE_DEMO_BRAND ??
    '';
  if (brand && brand !== 'wlc')
    throw new Error('VITE_DEMO_BRAND must be empty or wlc');
  return {
    plugins: [
      react(),
      tailwindcss(),
      {
        name: 'temporary-px-demo-brand',
        transformIndexHtml(html) {
          return brand === 'wlc'
            ? html
                .replace(
                  '<html lang="en">',
                  '<html lang="en" data-demo-brand="wlc">'
                )
                .replace('<title>Enclave</title>', '<title>PX</title>')
            : html;
        },
      },
    ],
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      fileParallelism: false,
    },
    server: {
      // Localization contract tests read the backend's accepted locale codes as
      // raw source so frontend/backend drift fails without importing node:fs.
      fs: {
        allow: ['..'],
      },
      host: '0.0.0.0',
      port: 5173,
      allowedHosts: [
        'localhost',
        '127.0.0.1',
        '.trycloudflare.com', // Allow Cloudflare Tunnel domains
      ],
      watch: {
        usePolling: true,
      },
      hmr: {
        host: 'localhost',
        port: 5173,
      },
      proxy: {
        '/api': {
          target: 'http://backend:18000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
});

import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			'/api': {
				target: process.env.VITE_BACKEND_URL ?? 'http://localhost:8000',
				changeOrigin: true,
				autoRewrite: true
			}
		}
	},
	ssr: {
		noExternal: ['bits-ui', 'mode-watcher']
	}
});

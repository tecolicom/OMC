import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://tecolicom.github.io',
  base: '/OMC',
  trailingSlash: 'always',
  vite: { plugins: [tailwindcss()] },
});

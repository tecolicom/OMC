import type { ImageMetadata } from 'astro';
const mods = import.meta.glob<{ default: ImageMetadata }>('../assets/photos/*.jpg', { eager: true });
const byName = new Map<string, ImageMetadata>();
for (const [path, mod] of Object.entries(mods)) {
  byName.set(path.split('/').pop()!, mod.default);
}
export function getPhoto(filename: string): ImageMetadata | undefined { return byName.get(filename); }
export function hasPhoto(filename: string): boolean { return byName.has(filename); }

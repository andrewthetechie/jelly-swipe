# Frontend Production Tasks

Two tasks that must be completed before the React frontend can replace the vanilla app in production. Both are learning exercises — read the linked resources before writing any code.

---

## Task 1: Self-host Google Fonts

### Why

`frontend/index.html` currently loads fonts from Google's CDN:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Newsreader:...&display=swap"
  rel="stylesheet"
/>
```

The production backend has a Content-Security-Policy header that blocks all external font sources (`font-src 'self'`). These tags will silently fail in production — fonts will not load, and we will not relax the CSP to allow them. The fonts must be bundled into the Vite build instead.

### How

Use the `@fontsource` npm packages. They install fonts locally so you can import them like any other module — no Vite plugin needed.

**Read first:**

- [Fontsource: Getting Started](https://fontsource.org/docs/getting-started/install)

**Steps:**

1. Install the font packages for the four fonts in `index.html`:

   ```bash
   npm install @fontsource-variable/newsreader
   npm install @fontsource-variable/orbitron
   npm install @fontsource-variable/raleway
   npm install @fontsource-variable/sour-gummy
   ```

2. Import them in `frontend/index.tsx` (before the app renders):

   ```ts
   import "@fontsource-variable/newsreader";
   import "@fontsource-variable/orbitron";
   import "@fontsource-variable/raleway";
   import "@fontsource-variable/sour-gummy";
   ```

3. Remove the three `<link>` tags from `frontend/index.html`.

4. Your existing `font-family` CSS rules stay the same — the font names don't change.

### Verify

```bash
npm run build
grep -r "fonts.googleapis.com" dist/
# should print nothing
npm run preview
# open the app and confirm fonts render correctly
```

---

## Task 2: Add PWA Support

### Why

The old vanilla app was installable as a Progressive Web App — users could add it to their phone's home screen and it behaved like a native app. That behavior is required from the first production release of the React app (it's listed in the First Usable Checkpoint in `001-frontend-modernization-guide.md`).

A Vite app gets PWA support from a single plugin that generates the manifest and service worker automatically from your config.

### How

**Read first:**

- [vite-plugin-pwa: Getting Started](https://vite-pwa-org.netlify.app/guide/)
- [MDN: Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest)

**Steps:**

1. Install the plugin:

   ```bash
   npm install -D vite-plugin-pwa
   ```

2. Add it to `vite.config.js`:

   ```js
   import { VitePWA } from "vite-plugin-pwa";

   export default defineConfig({
     plugins: [
       react(),
       VitePWA({
         registerType: "autoUpdate",
         manifest: {
           name: "Jelly-Swipe",
           short_name: "Jelly-Swipe",
           description: "Tinder-style swiping for Jellyfin",
           theme_color: "#111111",
           background_color: "#111111",
           display: "standalone",
           icons: [
             { src: "icon-192.png", sizes: "192x192", type: "image/png" },
             { src: "icon-512.png", sizes: "512x512", type: "image/png" },
           ],
         },
       }),
     ],
   });
   ```

3. Add the icons to `frontend/public/`. Vite copies everything in `public/` to the dist root unchanged. Copy the existing icons from the old static assets:

   ```bash
   cp jellyswipe/static/icon-192.png frontend/public/icon-192.png
   cp jellyswipe/static/icon-512.png frontend/public/icon-512.png
   ```

4. The plugin auto-registers the service worker. You do not need to write `sw.js` by hand.

### Verify

```bash
npm run build
ls dist/sw.js          # should exist
ls dist/manifest.webmanifest  # should exist
grep "manifest" dist/index.html  # should show a <link rel="manifest"> tag
npm run preview
```

Open Chrome DevTools → Application → Manifest while running `npm run preview`. Confirm the manifest loads with no errors. If you have a phone on the same network, visit the preview URL and confirm "Add to Home Screen" is offered.

### Coordinate at cutover

Once this task is merged, the old backend routes for `/manifest.json` and `/sw.js` in `jellyswipe/routers/static.py` should be removed — the Vite build will serve those files from its output instead. Flag this to the maintainer when opening your PR.

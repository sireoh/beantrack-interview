# BeanTrack frontend

SvelteKit (Svelte 5) + TypeScript + Tailwind CSS 4 + daisyUI 5, icons from `lucide-svelte`.
It is a single-page app (`ssr = false`, `adapter-static` with an `index.html` fallback) that talks
to the FastAPI backend in `../backend` with the session cookie.

## Run it

Needs Node 20+. From `frontend/`:

```bash
npm install
```

```bash
cp .env.example .env
```

```bash
npm run dev
```

The dev server listens on all interfaces (`0.0.0.0:5173`) and proxies `/api` to the backend
(`API_PROXY_TARGET`, default `http://127.0.0.1:8000`). The browser only ever talks to the dev
server, so the site works from your phone at `http://<your-LAN-IP>:5173` and the session cookie is
first-party. Keep `PUBLIC_API_URL` **empty** for this; if it's set, the browser calls that URL
directly, which a phone can't reach when it says `127.0.0.1`.

Discord sends you back to one fixed redirect URI, so pick the address you'll use for login and set
the backend's `.env` to it (and register the same redirect URI in the Discord developer portal).
To log in from both laptop and phone, use the LAN IP on both:

```
DISCORD_REDIRECT_URI=http://<LAN-IP>:5173/api/auth/callback   # through the Vite proxy
FRONTEND_URL=http://<LAN-IP>:5173/
COOKIE_SECURE=false                                            # plain http locally
```

Windows may ask to allow Node through the firewall the first time; allow it on private networks.

Other scripts: `npm run check` (svelte-check + TypeScript), `npm run build` (static site in
`build/`), `npm run preview`.

## Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `API_PROXY_TARGET` | Backend the dev/preview server forwards `/api` to (default `http://127.0.0.1:8000`) |
| `PUBLIC_API_URL` | Leave empty (calls go through the proxy). Only set it when the API lives on another origin in production |
| `PUBLIC_DAISYUI_THEME` | Last-resort theme, only used if the browser reports no light/dark preference. Order: the account's saved theme (when logged in) > the theme cached in `localStorage` > `prefers-color-scheme` > this > `dark` |

## Structure

```
src/
├── app.html                  # applies the saved/default theme before first paint
├── app.css                   # Tailwind + daisyUI (all themes enabled)
├── lib/
│   ├── api/
│   │   ├── types.ts          # API shapes, mirroring backend/app/schemas
│   │   └── client.ts         # typed fetch wrapper (credentials: 'include', ApiError, 401 hook)
│   ├── status.ts             # WatchStatus enum + STATUS_COLORS (theme variables) + labels
│   ├── config.ts             # PUBLIC_* env, login URL, IMDb links
│   ├── list-edit.ts          # shared edit logic: episodes, +/- (delta), jump (set_to), status, episode search
│   ├── list-view.ts          # filter / sort helpers for the list tables
│   ├── stores/               # user, searchMode, searchResults, tvList, movieList, episodes,
│   │                         # myCorrections, theme, toasts
│   └── components/           # Navbar, SearchBar, SearchFilter, SearchTVCard/SearchMovieCard,
│                             # TVListTable, MovieListTable, EpisodeEditDropdown, EditMobileModal,
│                             # StatusPicker, ThemeController, LandingPage, TvTitleEditor,
│                             # CustomDisplaySettings, MyCorrections, AdminCorrections
│                             # (+ small shared pieces)
└── routes/                   # /, /login, /search, /tvlist, /movielist
```

- **Stores own the data.** `tvList` / `movieList` are fetched once (`ensureTvList()`), then patched
  with the server's response after every add, progress or status change, so pages never refetch on
  navigation. `episodes` caches each show's episode list the first time its edit menu opens.
- **Edit logic is written once.** `EpisodeEditDropdown` (desktop) and `EditMobileModal`
  (mobile/tablet) both render `TvEditPanel`, which calls `$lib/list-edit`.
- **Breakpoints:** "desktop" is Tailwind's `lg` (≥1024px). Below that the list pages use the slim
  table, the status dropdown and the edit modal.

## Notes on the API

- `current_episode` is a 0-based index into `GET /api/tvlist/{imdb}/episodes`. The Progress column
  shows `current_episode + 1 / episodes_count` once an episode has been chosen, and `0 / N` before.
- Progress changes use `PATCH /api/tvlist/{imdb}/progress`; status changes use
  `PATCH /api/tvlist/{imdb}/status` and `PATCH /api/movielist/{imdb}/status`.
- `GET /api/search` requires login, so search bars are hidden when logged out and `/search` shows
  the login landing page.
- Search results are added with the status picked next to the search box on `/search`
  (`addStatus` store, saved in `localStorage`). Adding or setting a show as Completed moves its
  progress to the last episode (done by the backend).
- Delete (with confirmation) is in every row's edit menu/modal: `DELETE /api/tvlist/{imdb}`,
  `DELETE /api/movielist/{imdb}`.
- `/settings`: export/import via `/api/auth/profile/export` and `/import`; the admin section
  (only rendered when `user.role === 'admin'`, and enforced by the backend) uses
  `/api/admin/backup`, `/api/admin/backups` and `/api/admin/restore`.
- **Titles and images** (`TvTitleEditor`, inside every TV row's edit menu/modal) are two separate
  things:
  - *Rename for me*: a personal override, `PUT /api/tvlist/{imdb}/override` (returns the entry) and
    `DELETE` to reset (204; the row falls back to `show.catalog_title` / `show.catalog_image`). It
    applies at once, only for that user. `entry.override` holds it and `entry.override_active` says
    whether it is applied to `show.title` / `show.image`.
  - *Suggest a fix*: a catalogue correction, `POST /api/corrections`. It never changes the list on
    screen (for the submitter too) until an admin approves it. Only one correction per show can be
    pending; submitting again replaces it, both fields included, so the form starts from the
    pending one. The `myCorrections` store (`GET /api/corrections/mine`) tells the form whether one
    is pending.
- `/settings` also has: *Custom titles & images* (`PUT /api/settings/custom-display`; the current
  value comes with `/api/auth/me` as `custom_display_enabled`; changing it drops the cached TV list),
  *My submissions* (`GET /api/corrections/mine`) and, for admins, *Admin · Catalogue corrections*
  (`GET /api/admin/corrections?status=pending`, `PATCH /api/admin/corrections/{id}/approve` and
  `/reject`; 409 means it was already reviewed, so the queue is reloaded).
- User-supplied titles and image URLs are only rendered as text and `src`, never `{@html}`.

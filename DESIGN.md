# Sravanam — Design Doc

**Status:** Draft v0.1 — for review (no code yet)
**Owner:** Jaswanth Krishna Padarthi
**Host:** `abhi` (Debian 12, aarch64, 4 cores, 7.6 GB RAM, 67 GB free) — project home `~/sravanam`
**Working name:** *Sravanam* (శ్రవణం — "the act of attentive listening")

---

## 0. TL;DR

A **free** Flutter app (iOS + Android) for listening to Telugu pravachanam — Chaganti's
Ramayanam, Mahabharatam, and a growing catalogue. The content is freely sourced
(YouTube originals, linked openly). The **₹10/month subscription is a *sustainer pass***:
it funds server maintenance and service availability — it does **not** gate content.
The differentiator is a **"request any book/discourse" loop**: users ask, we add it.

Because we are **not selling the content**, there is **no DRM**. Downloads are clean,
authenticated, app-private MP3s. This removes the single biggest engineering and
app-store-review risk from the project.

---

## 1. Product model

| Element | Decision |
|---|---|
| Content access | **Free.** Anyone can listen without paying. |
| Paywall | **None.** Everything is reachable. |
| ₹10/month | **Sustainer pass** — "server maintenance & availability" framing. Voluntary. |
| Free-source transparency | Users who want the originals get the **YouTube links** we used. Open about it. |
| Signature feature | **Request a book/discourse** → lands in a queue → admin adds → appears in-app. |
| Billing route | **Razorpay autopay** (UPI AutoPay / card e-mandate), not store IAP initially. |
| Hosting | Homelab (`abhi`) first; migrate to CDN when traffic grows. |

**Why this is the right model (recorded reasoning):**
- Selling third-party copyrighted sermons = real legal/commercial exposure. A *service*
  sustainer sidesteps that; the content stays freely attributable to its source.
- No content paywall → no DRM → no store-review friction → weeks of work deleted.
- "Request anything" turns a passive library into a living, growing shrine — the reason
  someone comes back and the reason someone tips ₹10.

---

## 2. Users & core loops

**Primary persona:** Telugu-speaking listener, 25–65, mobile-first, often listening
during commute / chores / sleep. Wants uninterrupted, ad-free, offline-capable playback.

**Core loops**
1. **Listen:** open app → browse catalogue → play → resume where left off.
2. **Go offline:** download a discourse → listen without network.
3. **Sustain:** hit the (gentle, non-blocking) sustainer prompt → ₹10/mo autopay.
4. **Request:** "please add X" → we add → notification → they listen.

---

## 3. Architecture

```
        ┌───────────────────────┐
        │   Flutter app         │  iOS + Android (single codebase)
        │  browse/play/offline  │
        └───────────┬───────────┘
                    │ HTTPS (JSON API)  +  signed media URLs
        ┌───────────▼───────────┐
        │  FastAPI  (:8110)     │  auth, catalogue, progress,
        │  + Postgres (:5433)   │  billing webhooks, requests
        └───────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │  Media store (nginx)  │  read-only MP3 tree  ~/pravachanam + new ingests
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │  Razorpay (autopay)   │  ₹10/mo  →  webhooks → subscription state
        └───────────────────────┘
```

**Delivery path today:** app → Tailscale/NPM (bharat) → `abhi:8110` API and media.
**Delivery path later:** media moves behind a CDN (Cloudflare R2/Bunny) with signed
URLs; API stays on homelab or migrates to a small VPS.

---

## 4. Components

### 4.1 Flutter app
- **State:** Riverpod (or Bloc) — pick one, stay consistent.
- **Audio:** `just_audio` + `audio_service` (background playback, lock-screen controls,
  notification shade) + `audio_session`. This trio is the standard, battle-tested stack.
- **Offline:** `dio` downloader → writes MP3 to **app-private storage**
  (`getApplicationSupportDirectory()`), never a shared/Downloads folder.
- **Local DB:** `drift` (SQLite) for catalogue cache, progress, download index.
- **Screens (v1):** Home/Catalogue → Series → Player → Downloads → Account → Request.
- **No video.** Audio-only keeps it simple and small.

### 4.2 Backend — FastAPI + Postgres
- Python 3.11 (host) inside a slim container.
- SQLAlchemy 2.x + Alembic migrations; Pydantic v2 schemas.
- JWT access + refresh tokens; Argon2 password hashing.
- APScheduler (or systemd timers) for: subscription-state reconciliation, download
  entitlement expiry sweeps, request-queue digests.
- Admin surface for v1 = **CLI + SQL** (no admin UI yet).

### 4.3 Media store
- nginx (alpine) container, read-only bind mount of the MP3 tree.
- Internal-only; the API issues **short-lived signed URLs** (HMAC + expiry) so the
  media port is never publicly scrapable.
- Optional later: HLS segmentation for adaptive/seekable streaming.

### 4.4 Payments — Razorpay autopay
- Razorpay **Subscriptions API**: create a Plan (₹10/month, monthly interval) →
  create a Subscription → hand the app a `subscription_id` → Razorpay Checkout
  completes the mandate (UPI AutoPay or card e-mandate).
- **Webhooks** are the source of truth: `subscription.activated`, `subscription.charged`,
  `subscription.halted`, `subscription.cancelled`, `payment.failed`.
- Verify `X-Razorpay-Signature` = HMAC-SHA256(webhook_body, webhook_secret) **before**
  trusting any payload. Store raw payloads for audit.
- ₹10/mo is small; expect Razorpay's per-transaction fee to eat a chunk — **model the
  net take explicitly** before optimising anything else.

---

## 5. Data model (v1)

```
users(id, name, email, phone, password_hash, created_at, is_admin)
devices(id, user_id, platform, app_version, push_token, last_seen_at)
subscriptions(id, user_id, razorpay_subscription_id, razorpay_plan_id, status,
              current_start, current_end, created_at, updated_at)
payments(id, subscription_id, razorpay_payment_id, amount_paise, status, created_at)
webhook_events(id, event_type, razorpay_event_id, payload_json, received_at)
speakers(id, name, bio, image_url)
series(id, title, speaker_id, category, description, cover_url, sort_order)
items(id, series_id, title, index_no, duration_s, file_path, size_bytes, published_at)
progress(user_id, item_id, position_s, updated_at)          PK(user_id,item_id)
downloads(user_id, item_id, granted_at, expires_at)          audit + entitlement
requests(id, user_id, title, notes, status, created_at, resolved_item_id)
```

`requests.status`: `open → accepted → added | declined`.
`subscriptions.status` mirrors Razorpay: `created|active|charged|halted|cancelled|expired`.

---

## 6. API surface (v1)

```
POST /auth/register            POST /auth/login          POST /auth/refresh
GET  /me

GET  /catalog/series           GET  /catalog/series/{id}
GET  /catalog/items/{id}

GET  /media/{item_id}/stream        -> 302 to short-lived signed media URL
GET  /media/{item_id}/download      -> signed URL (no paywall; audited)

POST /progress                 GET  /progress

POST /billing/subscribe        -> {razorpay_subscription_id, checkout payload}
POST /billing/webhook          -> Razorpay -> us (signature-verified)
GET  /billing/status
POST /billing/cancel

POST /requests                 GET  /requests/mine
# admin
POST /admin/requests/{id}/resolve
POST /admin/ingest/notify
```

---

## 7. Subscription & money flow

1. App shows a **soft, dismissible** sustainer card (never a blocking wall).
2. User taps *Support* → `POST /billing/subscribe` → Razorpay Subscription created.
3. Razorpay Checkout handles the UPI AutoPay / card mandate.
4. Webhooks drive local state; `GET /billing/status` is what the app trusts on launch.
5. Sustainer gets: a thank-you state in Account + (optionally) early access to newly
   added requested items. **No content is ever withheld from non-payers.**

> **Policy note:** because this is a *service/sustainer* pass rather than a
> digital-content gate, external payment (Razorpay) is a far safer store-policy
> lane than selling content would be. Store IAP remains an option if policies tighten.

---

## 8. Content pipeline (how the catalogue fills)

Reuses the proven `telugu-pravachanam-audio` workflow — this is a solved road:

1. **Acquire:** yt-dlp from the official channel/playlist → bestaudio → MP3.
2. **Verify:** per-file duration vs source playlist (±3 s gate); count ≠ integrity.
3. **Fix:** mono-in-stereo defect scan → dominant-channel conversion → `_mono/`.
4. **Organise:** `Series/` (e.g. `Sampoorna_Ramayanam/`) → `Kanda/` or `Parva/` folders
   where the user's ear-confirmed boundaries are known.
5. **Ingest:** a small `sravanam-ingest` CLI reads the tree, extracts tags/duration
   (ffprobe), and upserts `speakers/series/items` rows. **Idempotent** — safe to re-run.
6. **Publish:** item becomes visible; subscribers who *requested* it get a ping.

---

## 9. Playback & offline downloads

- **Streaming:** signed URL → `just_audio` streams directly. Range requests supported
  (nginx does this natively) so seeking is instant.
- **Offline:** download the same signed URL into app-private storage.
- **Protection posture (deliberately light):**
  - Files live in the **app sandbox** — invisible to file managers and other apps.
  - URLs are **signed + expiring**; no permanent public links exist.
  - Downloads are **audited** and can be revoked server-side on request.
  - **No DRM fortress.** We explicitly accept that a determined user on a rooted device
    can capture audio — *and that's fine*, because the content is freely available
    anyway. Protecting it was never the point.
- **Revocation semantics:** if a sustainer lapses, existing downloads are **not** deleted
  (that would be hostile and pointless). Downloads simply stop refreshing.

---

## 10. Request-a-book loop

```
App: "Request a discourse" (title + speaker + optional link/notes)
  -> POST /requests  -> status=open
Admin: reviews queue  -> accepted -> added (links resolved_item_id) | declined
  -> on 'added': push/notification (or in-app badge) to the requester
```
This is the emotional centre of the product: it makes the library feel *theirs*.

---

## 11. Streaming & delivery

| Stage | Setup |
|---|---|
| **Today (homelab)** | nginx media container on `abhi`; API on `abhi:8110`; reachable over Tailscale; public entry via NPM on `bharat` (subdomain → tailnet host). |
| **Growth** | Media → object storage + CDN (signed URLs). API → small VPS or stays home. |
| **Decision trigger** | Move when egress bandwidth or latency degrades the listening experience, or when >N concurrent listeners. Record N when we learn it. |

---

## 12. Deployment on abhi

- **Compose project:** `~/sravanam/compose.yml` (project convention: Compose only,
  never `docker run`).
- **Services:** `api` (FastAPI), `db` (Postgres 16), `media` (nginx), `worker`
  (scheduler) — 4 containers, all ARM-native images.
- **Ports (free on abhi):** API `8110`, Postgres `5433` (localhost only), media `8111`.
  Taken already: 22, 53, 4000, 5900, 7848, 8080, 8081, 9030, 9115, 9848, 20241.
- **Secrets:** `.env` next to compose, never committed. Razorpay keys, JWT secret,
  webhook secret, DB password → generated locally, stored per house convention.
- **Backups:** nightly `pg_dump` → rotated; media tree is re-derivable from sources.
- **Observability:** optional scrape endpoint for existing Prometheus on `bharat`.

---

## 13. v1 scope fence (ship this, nothing more)

**IN:**
- Catalogue browse (series → items), audio playback, background/lock-screen controls.
- Resume progress across devices.
- Offline download of an item (app-private).
- Soft sustainer prompt + Razorpay autopay subscription + webhook-driven status.
- Request-a-discourse form + admin CLI to resolve.
- Email/password auth.

**OUT (deliberately deferred):**
- Social features, comments, sharing cards.
- Recommendations / playlists / favourites.
- Web/PWA client, desktop client.
- Admin web UI (CLI + SQL is enough at this scale).
- Multi-speaker analytics, ratings, transcripts, subtitles.
- Store IAP (only if policy forces it).
- HLS adaptive streaming (plain MP3 + range requests is fine at first).

---

## 14. Roadmap after v1

1. Phone-OTP login (Indian users expect it) once SMS costs are justified.
2. Push notifications: "your request was added", new-series alerts.
3. Playlists, favourites, sleep timer, playback speed.
4. HLS + CDN migration.
5. Store IAP alongside Razorpay if policy/practice demands it.
6. Transcripts/search inside audio (the Daily Dharma corpus work overlaps here).

---

## 15. Open questions (need decisions before/during build)

1. **Public hostname** for API + media — which subdomain, and does it route through
   NPM on `bharat` → tailnet `abhi`, or `tailscale serve` directly on abhi?
2. **Auth method for v1** — email/password (cheap now) vs phone-OTP (expected in India
   but costs per SMS). Chosen: email/password first.
3. **Catalogue source of truth** — is the DB authoritative, or does it mirror a
   filesystem convention and get re-ingested?
4. **Razorpay account status** — KYC/business details needed to enable autopay?
5. **Push provider** — FCM only (Android) vs FCM + APNs (needs Apple Developer account,
   ₹/$ annual).
6. **App store accounts** — Google Play ($25 one-off) + Apple Developer ($99/yr) exist?
   This gates real distribution regardless of billing choice.
7. **Sustainer perks** — does ₹10/mo buy anything at all beyond goodwill? (Suggest:
   a "Supporter" badge + early access to newly added requests.)

---

## 16. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Third-party content rights | **High** | Sustainer (service) framing, not content sales; openly link sources; be ready to remove on request from a rights-holder. |
| Play/Apple policy on external payments | Medium | It's a service/sustainer tier, not digital-content gating; revisit if rejected. |
| Homelab bandwidth/latency | Medium | Signed URLs + CDN migration path pre-designed. |
| ₹10/mo economics | Medium | Model net-of-fees early; it may be a goodwill tier, not a revenue engine — accept that. |
| Tailscale-only reachability | Medium | Public entry via NPM/reverse proxy; no reliance on users installing Tailscale. |
| Single-point host (abhi, SD card) | Medium | Nightly DB dumps off-host; media re-derivable; consider SSD. |
| Password/OAuth secrets leakage | High | Secrets in `.env`, never logged; Argon2; signature-verified webhooks. |

---

## 17. Immediate next steps

1. **Review this doc** — approve or change the model, the port map, the v1 fence.
2. Scaffold `~/sravanam` on abhi: `compose.yml`, `api/`, `media/`, `.env.example`,
   `README.md`, `docs/`.
3. Stand up Postgres + FastAPI skeleton with `/health` and migrations.
4. Ingest the existing 12 GB pravachanam tree into the catalogue tables.
5. Flutter shell: connect → browse → play. Then offline. Then billing. Then requests.

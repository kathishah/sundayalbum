# 2026-04-10 — Public Website Plan for www.sundayalbum.com

## Background

Sunday Album has two working entry points — `dev.sundayalbum.com` (staging) and
`app.sundayalbum.com` (production) — both behind email OTP login. The apex domain
`sundayalbum.com` and `www.sundayalbum.com` are not configured.

This plan adds a public marketing website at `www.sundayalbum.com` to serve as the
front door: explaining what Sunday Album does, showing how it works, and linking
visitors to the web app and Mac app download.

---

## Inspiration / Competitive Landscape

Reviewed before designing:

| Site | Model | Key takeaway |
|------|-------|--------------|
| **Photomyne** (photomyne.com) | Mobile app, subscription | Closest competitor — multi-photo scanning, AI enhance. Strong social proof, feature grid, animated demo. |
| **Google PhotoScan** (google.com/photos/scan) | Mobile app, free | Extremely minimal product page — headline, 3 features, download CTA. Proves less is more. |
| **Remini** (remini.ai) | Web + mobile, freemium | Best-in-class before/after slider UI. Stats-heavy hero. |
| **PhotoScanRestore** (photoscanrestore.com) | Web-first, freemium | Closest web-first model. 3-step workflow, guides section, comparison positioning. |
| **Pic Scanner Gold** (picscannergold.com) | iOS app, one-time purchase | Same "album page → individual photos" use case. Long-scroll feature page. |
| **Heirloom** (heirloom.cloud) | Mail-in service | Clean 3-step "how it works", FAQ-as-SEO pattern. |

Common patterns: before/after visuals, 3-step workflow, emotional framing, free-trial CTA.

Sunday Album's differentiators: album pages (not single photos), AI glare removal via
OpenAI diffusion inpainting, full automated pipeline (page detect → split → orient →
glare → color), web + native Mac, no subscription.

---

## Site Structure

The public site lives inside the existing Next.js app (`web/`). New routes are added
under a `(public)` route group with its own layout (marketing nav + footer). The
existing `(app)` and `(auth)` route groups are unchanged.

```
web/src/app/
  layout.tsx              (root — unchanged)
  (public)/
    layout.tsx            (marketing nav + footer)
    page.tsx              (home — replaces current redirect-to-login)
    pricing/page.tsx
    download/page.tsx
    about/page.tsx
  (auth)/
    login/page.tsx        (unchanged)
  (app)/
    layout.tsx            (unchanged — auth guard)
    library/page.tsx
    jobs/[jobId]/page.tsx
    settings/page.tsx
```

### Route behavior

| Route | Before | After |
|-------|--------|-------|
| `/` | Server redirect to `/login` | Marketing home page |
| `/pricing` | 404 | Pricing breakdown |
| `/download` | 404 | Mac app download + web app link |
| `/about` | 404 | Story / contact |
| `/login` | Login page | Unchanged |
| `/library` | Auth-guarded app | Unchanged |

Authenticated users who visit `/` see the marketing page with a "Go to Library" CTA
instead of "Get Started".

---

## Home Page Sections

### 1. Hero

Headline: "Your print photos, your album pages, digitized beautifully."
Subhead: Snap a photo of a single print or an entire album page. Sunday Album finds
every photo, removes glare, restores faded colors, and delivers clean digital photos
— automatically.

- Primary CTA: "Try it free" → `app.sundayalbum.com`
- Secondary CTA: "Download for Mac" → `/download`

### 2. How It Works

Static image section initially (video to be added later once produced). Shows a
3-step visual flow using actual pipeline images:

1. **Snap** — Take a photo of your album page with any phone.
2. **Process** — Sunday Album detects each photo, removes glare, restores colors.
3. **Download** — Get clean, individual digital photos.

Each step is illustrated with a real pipeline image (see Before/After assets below).
Once the "How It Works" video is produced, replace or supplement this section with an
embedded video player and poster image.

### 3. Before / After Showcase

Interactive slider component using real pipeline output from two test images.

**Pair A — Single print** (`dinner_print_contrast_bg`):

| Role | File |
|------|------|
| Before (source) | `test-images/dinner_print_contrast_bg.HEIC` |
| Loaded | `debug/dinner_print_contrast_bg_01_loaded.jpg` |
| Page detected | `debug/dinner_print_contrast_bg_02_page_detected.jpg` |
| Page warped | `debug/dinner_print_contrast_bg_03_page_warped.jpg` |
| Raw crop | `debug/dinner_print_contrast_bg_05_photo_01_raw.jpg` |
| Deglared | `debug/dinner_print_contrast_bg_07_photo_01_deglared.jpg` |
| Color restored | `debug/dinner_print_contrast_bg_13_photo_01_restored.jpg` |
| Final output | `output/SundayAlbum_dinner_print_contrast_bg_Photo01.jpg` |

Slider: loaded image (before) ↔ final output (after).

**Pair B — Three photos on one album page** (`IMG_three_pics_normal`):

| Role | File |
|------|------|
| Before (source) | `test-images/IMG_three_pics_normal.HEIC` |
| Loaded | `debug/IMG_three_pics_normal_01_loaded.jpg` |
| Page detected | `debug/IMG_three_pics_normal_02_page_detected.jpg` |
| Page warped | `debug/IMG_three_pics_normal_03_page_warped.jpg` |
| Photo boundaries | `debug/IMG_three_pics_normal_04_photo_boundaries.jpg` |
| Raw crops | `debug/IMG_three_pics_normal_05_photo_0{1,2,3}_raw.jpg` |
| Deglared | `debug/IMG_three_pics_normal_07_photo_0{1,2,3}_deglared.jpg` |
| Color restored | `debug/IMG_three_pics_normal_13_photo_0{1,2,3}_restored.jpg` |
| Final outputs (3) | `output/SundayAlbum_IMG_three_pics_normal_Photo0{1,2,3}.jpg` |

Slider: loaded album page (before) ↔ grid of 3 final output photos (after).
This pair demonstrates multi-photo detection — the "album page in, individual photos
out" value prop.

### 4. Feature Grid

4–6 cards, each with an icon, title, and one-line description:

| Feature | Description |
|---------|-------------|
| Multi-photo detection | Finds every photo on the album page — 1, 2, 3, or more. |
| AI glare removal | Diffusion-based inpainting removes sleeve and print glare. |
| Color restoration | Reverses yellowing and fading; restores natural tones. |
| Auto-orientation | Detects and corrects rotation using AI scene understanding. |
| Perspective correction | Straightens keystoned shots taken at an angle. |
| Web + Mac | Process in the browser or download the free Mac app. |

### 5. Pipeline Visualization

Animated (or static with hover) diagram of the processing pipeline at a high level:

```
Snap → Page Detect → Split Photos → Remove Glare → Restore Color → Done
```

Each node expands on hover/tap to show a one-sentence explanation. Uses existing
`sa-reveal` / `sa-slide` animation tokens.

### 6. Pricing Summary

Two-card layout linking to `/pricing` for details:

**Mac App — Free**
Full pipeline, runs locally, no account needed.

**Web App — Free (20 pages/day)**
Email login, process in the browser. Bring your own API keys to remove the limit.

### 7. Final CTA

"Give your memories a second life."
Primary CTA: "Get started free" → `app.sundayalbum.com`
Secondary CTA: "Download for Mac" → `/download`

---

## Pricing Page (`/pricing`)

Expanded version of the home page pricing summary.

### Mac App — Free, Unlimited

- Full 10-step processing pipeline, identical to the web version
- Runs entirely on your Mac — no internet required for processing
- No account, no login, no subscription
- API keys stored in macOS Keychain (Anthropic for orientation, OpenAI for glare removal)
- Drag-and-drop or file picker input; export to Photos.app or Finder

### Web App — Free Tier (Rate-Limited)

- **20 album pages per day** (resets at midnight UTC)
- Email-based login — no password, just a 6-digit code
- 7-day sessions; re-authenticate with a new code after expiry
- Live progress via WebSocket as each step completes
- Download individual photos or the full set

### Bring Your Own Keys (BYOK)

- Supply your own Anthropic and OpenAI API keys in Settings
- Removes the 20-page daily limit entirely
- Your keys are stored encrypted in DynamoDB; never logged or shared
- You pay OpenAI/Anthropic directly at their rates

### FAQ

**What counts as one "page"?**
One uploaded image = one page. If your album page has 3 photos, that's 1 page and
produces 3 output photos.

**Why is it free?**
The Mac app runs locally — there's no server cost. The web app uses AI APIs (Anthropic
and OpenAI) that cost money per call, so the free tier is rate-limited to keep costs
sustainable.

**What does BYOK mean?**
"Bring Your Own Keys." You create accounts at anthropic.com and openai.com, generate
API keys, and paste them into Sunday Album's Settings page. The AI calls then bill
directly to your accounts instead of ours, so there's no reason for a daily limit.

**Is there a paid plan?**
Not currently. The free tier with BYOK covers all features. If demand grows, a paid
tier may be added to cover API costs without requiring BYOK.

---

## Design System

The public pages reuse the existing "Warm Archival" design system:

- **Colors:** `sa-amber` (50–700) and `sa-stone` (50–950) scales, plus semantic
  `sa-card` / `sa-surface` / `sa-border-card` tokens — defined in
  `web/tailwind.config.ts` and `web/src/app/globals.css`
- **Typography:** Fraunces (display/headings), DM Sans (body), JetBrains Mono (code) —
  loaded via `next/font/google` in `web/src/app/layout.tsx`
- **Dark / light / system:** Already implemented. `darkMode: 'class'` in Tailwind;
  `ThemeProvider` component; inline `<script>` reads `localStorage('sa_theme')` with
  system preference fallback. Public pages inherit from the root layout automatically.
- **Animations:** `framer-motion` (already a dependency) for scroll-reveal on sections.
  Tailwind animation tokens: `sa-standard` (200ms), `sa-slide` (350ms), `sa-reveal`
  (600ms).
- **Layout:** Responsive, mobile-first. Max-width container for content sections.
- **Components:** Before/after slider — new shared component in `web/src/components/`.
  Marketing nav and footer — new components in the `(public)` layout.
- **SEO:** `generateMetadata` on each public page (title, description, OpenGraph image).

---

## DNS / Routing

### Current state

| Domain | Target | Where configured |
|--------|--------|------------------|
| `dev.sundayalbum.com` | App Runner `sundayalbum-web-dev` | CNAME in Namecheap |
| `app.sundayalbum.com` | App Runner `sundayalbum-web-prod` | CNAME in Namecheap |
| `sundayalbum.com` | Not configured | — |
| `www.sundayalbum.com` | Not configured | — |

Domain registered on Namecheap. NS records point to Route 53 (zone
`Z0420309YMJDXBAU344P`).

### Plan

1. **`www.sundayalbum.com`** — Add CNAME in Namecheap pointing to the prod App Runner
   domain (same target as `app.sundayalbum.com`).

2. **`sundayalbum.com` (apex)** — Namecheap does not support CNAME on apex domains.
   Since NS records already delegate to Route 53, add a Route 53 ALIAS record for the
   apex pointing to the prod App Runner service. Both `sundayalbum.com` and
   `www.sundayalbum.com` resolve directly without a redirect hop.

3. **App Runner custom domain** — Associate `www.sundayalbum.com` and `sundayalbum.com`
   as custom domains on the `sundayalbum-web-prod` App Runner service (ACM certificate
   validation required, same process used for `app.sundayalbum.com`).

### After DNS is configured

| Domain | Target | Where configured |
|--------|--------|------------------|
| `dev.sundayalbum.com` | App Runner `sundayalbum-web-dev` | CNAME in Namecheap |
| `app.sundayalbum.com` | App Runner `sundayalbum-web-prod` | CNAME in Namecheap |
| `www.sundayalbum.com` | App Runner `sundayalbum-web-prod` | CNAME in Namecheap |
| `sundayalbum.com` | App Runner `sundayalbum-web-prod` | ALIAS in Route 53 |

The same Next.js app serves all domains. No hostname-based routing needed — routes are
path-separated (`/` = marketing, `/library` = app). Update `docs/SYSTEM_ARCHITECTURE.md`
domain table once DNS is live.

---

## Video Script — "How It Works" (~45 seconds)

Target: a short product video suitable for the home page and social media. To be
produced using a genAI video generation service (e.g. Runway, Pika, Kling) with the
screenplay below as the creative brief.

---

### SUNDAY ALBUM — "How It Works" (0:45)

**SCENE 1 — THE PROBLEM (0:00 – 0:05)**

*Visual:* Close-up of a weathered photo album on a wooden table. Pages with yellowed
photos under plastic sleeves. Warm, soft lighting. A hand slowly turns a page.

*Voiceover:* "Your family's best moments are stuck in albums — fading behind plastic,
gathering dust."

---

**SCENE 2 — THE SNAP (0:05 – 0:12)**

*Visual:* A hand holds an iPhone above an open album page showing 3 photos (visible
glare patches, yellowed tones). The phone camera viewfinder frames the page. A shutter
animation fires. Cut to the Sunday Album web interface — the image uploads with a
progress indicator.

*Voiceover:* "Just snap a photo of the album page. That's it — one photo, any phone."

---

**SCENE 3 — THE PIPELINE (0:12 – 0:30)**

*Visual:* Quick animated sequence showing the processing steps. Each step is a clean
transition:

(a) The album page photo appears on screen. A dashed outline traces around the page
boundary — the page is detected and perspective-corrected. The image straightens.

(b) Colored outlines appear around each individual photo within the page. Text overlay:
"3 photos found." The photos separate and float apart into their own frames.

(c) One photo zooms in. A bright glare patch is highlighted with a subtle pulse, then
wipes away cleanly via a left-to-right split-screen transition. Text: "AI glare
removal."

(d) The same photo's colors shift — yellowed skin tones warm into natural hues, faded
blues deepen, washed-out greens recover. Text: "Color restored."

(e) A slightly tilted photo straightens with a smooth rotation animation. Text:
"Auto-oriented."

*Voiceover:* "Sunday Album finds each photo on the page, removes glare, restores faded
colors, and straightens everything — automatically."

---

**SCENE 4 — THE RESULT (0:30 – 0:38)**

*Visual:* Three clean, vivid individual photos appear in a row, gently fading in one
after another. Camera pulls back to show the original album page on the left and the
three restored photos on the right. The contrast is dramatic — yellowed and glare-
covered vs. clean and vibrant.

*Voiceover:* "From one snap to perfectly restored individual photos — ready to share,
print, or save forever."

---

**SCENE 5 — CTA (0:38 – 0:45)**

*Visual:* Sunday Album logo centered on a warm amber background. Below: "Try it free at
sundayalbum.com" in DM Sans. A Mac app icon appears alongside with "Free for Mac."
Gentle fade to black.

*Voiceover:* "Try Sunday Album free. No account needed for Mac — just download and go."

---

### Production Notes

- **Style:** Warm, nostalgic but modern. "Family memory meets clean tech product."
- **Color palette:** Amber / warm tones for the album scenes; clean white / stone for
  the UI and pipeline scenes. Matches the `sa-amber` / `sa-stone` design tokens.
- **Transitions:** Smooth cross-dissolves for album scenes; crisp cuts for UI / pipeline
  animation scenes.
- **Music:** Gentle acoustic guitar or piano. Builds slightly during the pipeline
  sequence (Scene 3), resolves warmly at the end.
- **Typography in video:** Fraunces for titles, DM Sans for body text — matching the
  website.
- **Total runtime target:** 42–48 seconds.
- **Aspect ratios:** Produce in 16:9 (website embed) and 9:16 (social/vertical) if the
  generation tool supports it.

---

## Files to Create / Modify (Implementation Phase)

This journal entry is the design document. When implementation begins:

| Action | File |
|--------|------|
| New | `web/src/app/(public)/layout.tsx` — marketing nav + footer |
| New | `web/src/app/(public)/page.tsx` — home page |
| New | `web/src/app/(public)/pricing/page.tsx` |
| New | `web/src/app/(public)/download/page.tsx` |
| New | `web/src/app/(public)/about/page.tsx` |
| New | `web/src/components/BeforeAfterSlider.tsx` |
| New | `web/src/components/MarketingNav.tsx` |
| New | `web/src/components/MarketingFooter.tsx` |
| Modify | `web/src/app/page.tsx` — remove redirect, render `(public)` home or redirect logic |
| Modify | `docs/SYSTEM_ARCHITECTURE.md` — update domain table after DNS setup |
| DNS | Namecheap: add CNAME for `www` |
| DNS | Route 53: add ALIAS for apex `sundayalbum.com` |
| DNS | App Runner: associate `www.sundayalbum.com` + `sundayalbum.com` custom domains |

# Kamra — UX & HCI Design

## 1. Principles applied (Nielsen's 10 heuristics → concrete decisions)

| Heuristic | Where it shows up in Kamra |
|---|---|
| **1. Visibility of system status** | Live result count ("5 places found"); upload progress "Uploading 8/24"; 3D build progress bar with stage text ("Bedroom: Aligning 20 views"); "Sending…/Seen" in chat; tour status badges (No media → 12 photos → Processing → 3D ready); viewer loading bar with low-res-first progressive textures |
| **2. Match with the real world** | Local vocabulary: *bed space, hostel seat, portion, bills included, meals*; PKR formatting ("Rs 15,000 /month"); PK phone format accepted as typed (`0300-1234567`); room sizes offered in feet ("12×14 ft") |
| **3. User control & freedom** | Every sheet/modal has Cancel; "Do this later" on verification; pause/resume listing; clear media / remove room; failed message text restored to the input; filters are drafted and only applied on "Show results" |
| **4. Consistency & standards** | One component library (`components/ui.tsx`); platform navigation (tabs + stack, back gestures); primary action always bottom/right and filled; destructive actions red + confirmation |
| **5. Error prevention** | Step-by-step listing wizard with per-step validation; numeric keypads for money; "available ≤ capacity" check; capture guide shown *before* the first room; Build button disabled until every room has media; confirmation for destructive actions; quick-pick visit slots instead of free-form date entry |
| **6. Recognition rather than recall** | Chips for cities, types, amenities, room names; visit time slots; filter badge shows number of active filters; checklist on Manage screen |
| **7. Flexibility & efficiency** | Search-as-you-type (debounced 300 ms); quick filter chips on Explore *and* full filter sheet; keyboard (WASD/arrows) + mouse + touch + joystick in the viewer; dollhouse to jump between rooms |
| **8. Aesthetic & minimalist design** | Cards show only price, title, area and 3–5 badges; details progressive-disclosed on the detail screen; collapsible capture guide |
| **9. Help users recognise, diagnose, recover from errors** | Server errors are human sentences with the field ("Rent monthly: Input should be ≥ 1000"); reconstruction failures come with actionable hints ("Overlap each photo by about a third", "Switch on the lights"); Retry on every error banner |
| **10. Help & documentation** | Capture guide; viewer help card on first open (and "?" button); safety tips in chat & owner card; hints under fields ("Private — only shared with people whose visit you accept") |

## 2. Trust & safety UX (the core value vs WhatsApp groups)

* Phone numbers are **never shown**; conversation happens in-app.
* Exact address disclosed **only after** the owner accepts a visit — explained inline with a lock icon so it doesn't look like missing data.
* "Never pay an advance before visiting" reminder in chat and on the owner card.
* Report flow in 2 taps with concrete reasons ("Asks for advance money", "Photos don't match").
* Verified owner and verified contact badges; reviews only from people who actually visited.

## 3. Accessibility (WCAG 2.2 AA)

* Colour contrast: primary `#0f766e` on white = 5.4:1; body text `#0f172a`; muted `#475569` = 7.5:1. Dark theme tokens defined in `lib/theme.ts` and follow the OS setting.
* Touch targets ≥ 44×44 pt (`MIN_TOUCH`), `hitSlop` on small icons.
* Every interactive element has `accessibilityRole` + `accessibilityLabel`; listing cards read as one sentence ("Bed in 3-seater room. Bed space for Boys in Johar Town, Lahore. Rs 14,000 per month. Has 3D tour. Verified owner.").
* Live regions for result counts, upload/processing progress and errors.
* Forms: visible labels (not placeholder-only), errors announced and shown below the field, correct `autoComplete`/`textContentType` for password managers and SMS one-time-code autofill.
* Viewer: keyboard navigable, `aria` labels on controls, focus-visible outlines, `prefers-reduced-motion` respected (no fades/glides), help dialog is a proper modal with focus management.
* Text scales with the OS font size (no fixed-height text containers).

## 4. Key flows

**Seeker — find & visit (≤ 6 taps)**: Explore → (quick chips) → listing → *Walk through in 3D* → Request visit → pick slot → Send.

**Owner — publish with 3D (≈ 10 min)**: Profile → Start listing → wizard (4 steps) → Manage → Add photos → Create 3D tour → add rooms via chips → capture (camera/gallery/video) → Build → Preview → Submit for review.

**3D viewer**: drag to look · tap floor to walk · rings to change room · Dollhouse overview · pinch/scroll to zoom · joystick on touch devices.

## 5. Performance as UX

* Thumbnails (480 px) in lists, full photos (1920 px) on detail.
* Viewer loads 2K panoramas first, then upgrades to 4K on capable devices; `deviceMemory ≤ 2 GB` stays at 2K and lower pixel ratio.
* Optimistic UI for favourites and chat messages, with rollback on failure.

## 6. Localisation (roadmap)

Strings are centralised per screen and formatting goes through `lib/format.ts`; adding Urdu requires i18n extraction plus RTL testing (`I18nManager.forceRTL`).

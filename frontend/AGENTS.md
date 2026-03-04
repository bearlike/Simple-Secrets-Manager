# AGENTS (Frontend)

## Scope

This folder contains the SSM Admin Console (Vite + React).

## Commands

- Install deps: `npm install`
- Dev server: `npm run dev`
- Lint: `npm run lint`
- Production build: `npm run build`
- Preview build: `npm run preview`

## Backend integration

- API base URL is controlled by `VITE_API_BASE_URL`.
- Default API base is `/api`.
- Auth header expected by backend: `Authorization: Bearer <token>`.

## KISS/DRY Reuse Policy (Frontend)

- Keep frontend implementation intentionally simple: prefer straightforward composition over new abstractions.
- DRY first: before adding code, check whether the same UI behavior already exists in `src/components` and reuse it.
- Reuse order is mandatory: existing local component -> existing shadcn primitive/pattern already in repo -> package component already installed -> new component as last resort.
- If a feature can be built by composing existing shadcn components (`Dialog`, `DropdownMenu`, `Tabs`, `Select`, `Button`, etc.), do that instead of creating a new custom primitive.
- Avoid frontend sprawl: do not add new reusable components unless the same pattern is needed in multiple places or materially improves maintainability.
- When a new component is unavoidable, keep API and internal logic minimal, colocate it near usage, and avoid speculative/generalized props.
- Prefer extending existing components with `className`, small props, and composition rather than forking or duplicating markup.
- We are not a frontend-heavy project: optimize for low ownership and low maintenance by maximizing out-of-the-box component reuse.

### Planning/Research order for new UI work (do this first)

1. Check official shadcn docs + registry for a native primitive/pattern that matches the need (`ui.shadcn.com` docs + registry JSON).
2. Check `src/components/ui` for that primitive already present before adding anything.
3. If missing, add the official shadcn registry primitive (and only required companion deps/files) before designing custom UI.
4. Compose feature UI from those primitives first; only build a new custom component when composition is clearly insufficient.
5. Keep implementation minimal and local: small props, no speculative APIs, no duplicate wrappers around existing shadcn behavior.

## Session lessons (frontend)

- Forked config grouping can be implemented without backend contract changes by combining read-time calls:
  - child effective secrets (`include_parent=true`)
  - child direct secrets (`include_parent=false`)
  - parent effective secrets (`include_parent=true`)
- Fork diff display rule: if a child has a direct key with the same value as parent effective, classify it as `Inherited` in UI (no effective divergence).
- Current UI kit in this repo does not include accordion/collapsible primitives by default; section toggles should be built with existing shadcn-styled `Button` + lucide chevrons unless a shared primitive is intentionally introduced.
- If parent comparison data cannot be loaded, degrade gracefully in UI (show a small note and keep table usable) instead of blocking the entire secrets view.
- Prefer the native shadcn `SidebarProvider` + `Sidebar` + `SidebarInset` + `SidebarTrigger` stack for app navigation; avoid custom `Dialog`-as-drawer rewiring because it tends to cause brittle styling and transparency regressions.
- For any new component request, research should start with official shadcn registry primitives and their required companion files/dependencies before considering external UI libraries or custom implementations.
- For responsive top bars, keep only core actions always visible on small viewports (navigation trigger, breadcrumb context, account menu) and move secondary actions (export/settings/repo links/config switching) into a native shadcn `DropdownMenu` overflow.
- Keep theme mode controls out of crowded top bars on mobile-first layouts; place them in stable navigation surfaces (for example sidebar footer) to reduce header collisions and keep interaction targets accessible.
- For dense tables on compact widths, prioritize search/input width by switching secondary action buttons to icon-only with `Tooltip` labels and use the same row action definition to render desktop icon actions plus mobile `DropdownMenu` actions without duplicating behavior logic.
- For project-wide secret mutations (like icon recompute), invalidate shared query prefixes (for example `['secrets', projectSlug]` and `['compare-secret', projectSlug]`) so all config views refresh consistently.

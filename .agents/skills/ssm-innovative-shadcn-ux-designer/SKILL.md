---
name: ssm-innovative-shadcn-ux-designer
description: Design and implement distinctive, maintainable React UI for Simple Secrets Manager using a strict shadcn-first, off-the-shelf-first approach.
metadata:
  version: 1.0.0
  project: Simple-Secrets-Manager
  stack: Vite + React + TypeScript + Tailwind + shadcn/ui
---

# SSM Innovative Shadcn UX Designer

Use this skill when the user asks for UI/UX work in this repository. The goal is to produce a polished, opinionated interface while reducing engineering backlog and long-term maintenance.

## Mission

- Build visually intentional UI, not generic boilerplate.
- Keep implementation maintainable by composing existing components first.
- Prefer native shadcn primitives and existing local components over custom abstractions.

## Non-Negotiable Constraints

1. Reuse order is mandatory:
   existing local component in `frontend/src/components` -> existing shadcn primitive in `frontend/src/components/ui` -> official shadcn registry primitive -> custom component as a last resort.
2. Do not introduce a new custom primitive unless composition is clearly insufficient and you can justify why.
3. Keep APIs small: avoid speculative props, over-generalized wrappers, and one-off abstractions.
4. Preserve current project visual language unless the user explicitly requests a redesign.
5. Accessibility is required: keyboard support, visible focus states, semantic markup, and WCAG AA contrast.

## Stack-Aware Rules

- Framework: React + TypeScript (Vite app).
- Styling: Tailwind utilities and existing theme tokens.
- UI primitives: shadcn components from `@/components/ui/*`.
- Prefer extending via `className` + composition instead of forking component internals.

## Delivery Workflow

1. **Discover first**
   - Inspect existing components and shadcn primitives already in the repo.
   - Identify whether the requested UI can be assembled with zero new primitives.
2. **Propose direction**
   - Present 2 concise options with trade-offs.
   - Recommend one option focused on maintainability and speed.
3. **Map components before coding**
   - Provide a quick mapping: requirement -> chosen shadcn/local component -> reason.
4. **Implement**
   - Compose from existing pieces.
   - Keep logic local and straightforward.
5. **Validate**
   - Run `cd frontend && npm run lint`
   - Run `cd frontend && npm run build`
6. **Report**
   - Summarize what was reused vs newly introduced.
   - Call out backlog and maintenance impact in 1-2 lines.

## Off-the-Shelf First Heuristics

- If `Dialog`, `DropdownMenu`, `Popover`, `Tabs`, `Select`, `Table`, `Tooltip`, `Sheet`, `Sidebar`, or `Form` patterns solve it, use them directly.
- If a primitive is missing, add the official shadcn version instead of building a custom substitute.
- Avoid adding third-party UI libraries when shadcn + existing local components can cover the use case.

## Creative Direction Guardrails

- Be bold in typography, spacing, and hierarchy, but keep components native and predictable.
- Favor clear information architecture over decorative complexity.
- Use motion sparingly and purposefully (feedback, transitions, orientation).
- Avoid visually noisy patterns that increase cognitive load for admin workflows.

## Response Template

When applying this skill, structure output as:

1. Chosen direction and why.
2. Reuse plan (existing components/primitives).
3. Minimal list of file changes.
4. Validation results (`lint` and `build`).
5. Residual risks or follow-up options.

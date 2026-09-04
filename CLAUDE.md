# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Power Routine — "projeto integrador" (academic capstone). A static, single-page fitness demo app.
No build step, no package manager, no dependencies to install, no test suite. Everything is
plain HTML/CSS/vanilla JS served straight from the repo root.

UI text, identifiers, and comments are in **Brazilian Portuguese** (`<html lang="pt-BR">`). Keep new
user-facing strings and DOM ids in Portuguese to match.

## Running it

```bash
xdg-open index.html                 # open directly; file:// works, there are no module imports
python3 -m http.server 8000         # or serve the root and hit http://localhost:8000
```

There is nothing to build, lint, or test. Verify changes by loading the page and walking the flow:
login → form → dashboard tabs → "Gerar plano".

## Architecture

Three files at the repo root:

- `index.html` — **all three screens exist in the DOM at once**, as sibling `<section class="view">`
  elements (`#view-login`, `#view-form`, `#view-dash`). Nothing is ever created or removed.
- `app.js` — the entire application. Loaded with a plain `<script>` at the end of `<body>`; listeners
  are registered at the top level, so every element it queries must already exist in `index.html`.
- `styles.css` — dark theme driven by CSS custom properties on `:root` (`--green` accent, `--bg`,
  `--surface`, `--border`, `--text`, `--muted`, `--r` radius, `--t` transition). Use these variables
  rather than hardcoding colors.

### Navigation is CSS-class visibility, not routing

Two independent toggle mechanisms, both by adding/removing `.active`:

1. **Screens** — `goTo(viewId)` strips `.active` from every `.view` and sets it on the target.
   `.view { display: none }` / `.view.active { display: … }` in `styles.css` does the showing.
2. **Dashboard tabs** — `.nav-item[data-tab]` buttons in the sidebar map to `.tab-content` panels by
   id; the click handler mirrors the same strip-then-set pattern.

Adding a screen or tab means: add the markup with the right class, add the CSS rule, and wire the
id — there is no route table.

### State

A single module-level `state` object (`nome`, `idade`, `peso`, `altura`, `objetivo`) holds everything.
It is populated only on `#infoForm` submit and is **in-memory only** — no `localStorage`, no backend,
so a refresh resets the app to the login screen.

Login (`#loginForm`) is cosmetic: it checks that email and password are non-empty and then calls
`goTo("view-form")`. There is no authentication, no user record, and email/senha never reach `state`.

### Rendering

`preencherDashboard()` is the one render function: it recomputes IMC and pushes `state` into ~12
hardcoded element ids via `innerText`. The same values are duplicated across the "Início" and
"Progresso" tabs under different id prefixes (`d-*` / `info-*` on Início, `p-*` on Progresso), so a
new field usually needs to be written in both places here.

`gerarPlano()` picks a fixed meal plan from a three-branch `if` on `state.objetivo` (`"Emagrecer"`,
`"Ganhar massa"`, else) and replaces `#plano-output` with a template literal. These strings must match
the `<option value>`s of `#objetivo` in `index.html` exactly.

Helpers: `calcularIMC(peso, altura)` expects **altura in cm** and returns a 1-decimal string;
`classificarIMC` buckets it into Baixo / Normal / Sobrepeso / Alto. `showToast(msg)` is the only
user feedback channel (form validation errors and success messages) — a 2s `.show` class on `#toast`.

### External assets

Font Awesome and the Outfit font are loaded from CDNs in `<head>`; icons are `<i class="fa-solid …">`.
Local images live in `img/`. The page degrades but still works offline (icons and font just fall back).

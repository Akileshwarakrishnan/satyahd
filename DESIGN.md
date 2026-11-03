# Flim | The search engine for creative people design system

> Extracted by [Inspo](https://github.com/Nutlope/inspo) (open source, MIT, powered by Together AI). Reference material for *intentional* design decisions: adapt, don't copy.

> Save this as `DESIGN.md` in your project and re-reference it as you build; re-fetch anytime at https://inspomcp.dev/d/flim-ai/DESIGN.md

- **Source:** https://flim.ai/
- **Captured:** 2026-05-27
- **Mode:** light
- **Macrostructure:** Specimen
- **Stack:** Webflow, Cloudflare

## Tone

Movie & Video Database - Flim is the leading image research website, delivering handpicked HD stills and Video Cuts. AI search engine helps you to quickly find the ideal visual for your creative needs.  ·  minimalism, swiss, monochrome, ai, developer-tools, creator, media, hero-with-cta, logo-cloud, sticky-nav

## Colors

| Hex | Role (heuristic) |
|---|---|
| `#fc3404` | support |
| `#fca997` | support |
| `#1c744c` | accent |
| `#4ca078` | support |
| `#acd4c4` | muted |

## Typography

Detected typefaces: **Arial**, **PP Neue Montreal Mono**

| Role | Family | Size | Weight | Line-height | Letter-spacing |
|---|---|---|---|---|---|
| h1 | Arial | 38px | 700 | 1.16 | 0 |
| h2 | PP Neue Montreal Mono | 12px | 400 | 1 | 0.72px |
| body | Arial | 16px | 400 | 1 | 0 |
| button | Arial | 14px | 500 | 1.71 | 0 |

## Spacing scale

`6px` · `8px` · `24px` · `30px` · `32px` · `52px` · `58px` · `68px` · `100px` · `128px` · `160px` · `180px`

Base step looks like **4px**.

## Border radius

`0px` · `2px` · `4px` · `8px` · `25px` · `50px` · `64px`

## Container

Max content width: **440px**

## CSS variables exposed by the source

```css
:root {
  --primary--black-transparent-10: #1414141a;
  --primary--dark-grey-grid: #414149;
  --primary--white: white;
  --primary--white-transparent-10: #ffffff1a;
  --primary--black: #141414;
  --_typography---heading--h1--letter-spacing: -.02em;
  --_typography---ui--sans--s--line-height: 110%;
  --_theme---accent-section-foreground: white;
  --_theme---tag-background: #737373;
  --sci-fi--teal-50: #e2fdf9;
  --psychological--red: #a30805;
  --_typography---body--l--font-weight: 500;
  --_typography---heading--jumbo--font-family: Swizzy,Arial,sans-serif;
  --sci-fi--teal-300: #85e0d3;
  --_typography---body--s--font-size: min(24px,max(13px,calc(13px + 11*( (min(100vw,100vh*(16/9)) - 320px)/1600 ))));
  --giallo--pink: #ec24c8;
  --_typography---heading--h1--font-family: Swizzy,Arial,sans-serif;
  --_theme---brand-2: #30a81d;
  --psychological--darker-blue: #060317;
  --samba--yellow: #fecc33;
  --sci-fi--teal: #0ec0b1;
  --giallo--light-pink: #f7a1e7;
  --_typography---ui--mono--s--font-family: "PP Neue Montreal Mono",Arial,sans-serif;
  --_typography---heading--big--font-size: min(280px,max(80px,calc(80px + 200*( (min(100vw,100vh*(16/9)) - 320px)/1600 ))));
  --_typography---body--l--letter-spacing: -.02em;
  --_typography---ui--mono--xs--font-weight: 400;
  --_theme---nav-secondary: #141414;
  --_typography---heading--h3--letter-spacing: -.02em;
  --_typography---ui--sans--xs--font-size: .875rem;
  --_theme---pattern-background: whitesmoke;
  --_typography---ui--mono--m--line-height: 100%;
  --_theme---brand-4: #fecc33;
  --giallo--red: #af0035;
  --_typography---heading--big--line-height: 110%;
  --_typography---heading--jumbo--font-size: min(380px,max(164px,calc(164px + 216*( (min(100vw,100vh*(16/9)) - 320px)/1600 ))));
  --_typography---heading--h3--font-weight: 500;
  --_theme---tag-foreground: white;
  --_typography---ui--sans--s--font-size: min(18px,max(13px,calc(13px + 5*( (min(100vw,100vh*(16/9)) - 320px)/1600 ))));
  --_typography---ui--mono--xs--font-size: .5625rem;
  --giallo--blue: #0440e2;
  --_typography---ui--sans--xs--letter-spacing: 0em;
  --vh: 9px;
  --giallo--red-400: #ca8297;
  --noir--grey-500: #737373;
  --_typography---heading--h1--font-size: min(160px,max(49px,calc(49px + 111*( (min(100vw,100vh*(16/9)) - 390px)/1530 ))));
  --_theme---accent-section-background: #141414;
  --psychological--dark-blue: #200736;
  --_typography---heading--jumbo--font-weight: 500;
  --_typography---ui--mono--xs--font-family: "PP Neue Montreal Mono",Arial,sans-serif;
  --sci-fi--brown: #461e1b;
  --_typography---ui--sans--xs--font-weight: 500;
  --_typography---heading--h3--line-height: 86%;
  --_typography---body--m--line-height: 100%;
  --_theme---foreground: #141414;
  --_typography---heading--big--font-family: Swizzy,Arial,sans-serif;
  --samba--orange: #ff8400;
  --giallo--dark-red: #540019;
  --_typography---heading--h3--font-family: Swizzy,Arial,sans-serif;
  --_typography---ui--mono--s--font-size: .75rem;
  --_theme---neutral-4: #d9d9d9;
}
```

## Components present

- hero with cta
- logo cloud
- sticky nav

## Notes for the agent

- **Adapt, don't copy.** The type ramp is a *starting point*. Scale it to your project's base size; preserve the *ratio*, not the literal pixels.
- **Color roles are heuristic** (luminance + dominance). Verify against the source URL before committing tokens.
- **Spacing** assumes a constant base step; round detected values to your project's scale (4 / 8 / 16) when implementing.
- **CSS variables** dumped above (when present) are the source's *actual* tokens - those are higher signal than guesses.
- This page's macrostructure is **Specimen**.

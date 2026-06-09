# DESIGN.md

This project should feel like a calm, dependable utility — not a flashy AI demo.

## Design goals

- Clean at first glance
- Fast to scan
- Comfortable on laptop and desktop
- Useful immediately on a LAN page
- No loud gradients, novelty shapes, or generic dashboard clutter

## Visual language

- Palette: neutral slate/gray base, restrained blue accent
- Background: soft off-white with a subtle radial wash
- Surfaces: lightly translucent white cards with thin borders
- Shadows: one gentle elevation style, reused everywhere
- Radius: consistent rounded corners, nothing overly bubbly

## Typography

- Use Inter for UI
- Use monospace for raw content areas
- Strong hierarchy:
  - large page title
  - compact metadata chips
  - clear section titles
- Avoid all-caps marketing language

## Spacing and layout

- Prefer generous padding inside cards
- Use one main content column for reading
- Use a two-column layout only for supporting panels
- Keep line lengths readable
- Leave whitespace between chunks so the eye can rest

## Component rules

- Cards should feel like tools, not ads
- Buttons should be obvious but subtle
- Metadata should be compact and quiet
- Content display should always be the hero
- Raw data must be readable before it is decorative

## Artifact renderers

- Text/logs: monospace, high contrast, preserve whitespace
- JSON: pretty-printed and easy to copy
- Markdown: rendered cleanly with safe defaults
- Images: centered, not stretched, with optional caption
- Reports: sanitized, white-surface presentation

## Do

- Use honest spacing
- Use clear labels
- Keep controls predictable
- Favor legibility over decoration
- Make expiry and sharing obvious

## Don't

- Don't use AI-demo card stacks
- Don't use random color accents everywhere
- Don't use heavy glassmorphism
- Don't bury the actual data under marketing copy
- Don't make the page feel like a template marketplace theme

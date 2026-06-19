# Drop-in illustrations

Save AI-generated PNGs here with these **exact filenames** and they appear
automatically (no code change). Until a file exists, the UI falls back to the
built-in mascot / emoji.

| File                | Where it shows           | Recommended size      | Fallback           |
|---------------------|--------------------------|-----------------------|--------------------|
| `hero.png`          | Dashboard hero           | 1024×1024 (square)    | Senty SVG mascot   |
| `empty-state.png`   | "No sweeps yet" panel    | 768×768 (square)      | 🛰️ emoji           |
| `complete.png`      | "Sweep complete!" card   | 768×768 (square)      | (nothing)          |

## Requirements (important for clean integration)
- **Transparent background** (PNG with alpha). Ask for it explicitly.
- **Flat vector style — solid fills, NO gradients**, not photorealistic, no baked-in shadows.
  This matches the rest of the UI (think getillustrations.com / flat solid color).
- **No text** in the image (the UI adds its own).
- **Subject centered** with a little padding so nothing is clipped when scaled down.
- Keep file size reasonable (< ~400 KB; downscale/compress if needed).

## Brand palette to request (use as flat solid fills)
- Primary indigo `#4F46E5` / lighter `#6366F1`
- Light indigo tint `#EEF1FF`
- Amber accent `#F59E0B`
- Emerald accent `#10B981`
- Soft pink (sparingly) `#FBCFE8`
- Slate neutrals for outlines `#3730A3` / `#C7D2FE`

## Prompts you can paste into ChatGPT image generation

**hero.png**
> Flat vector illustration, solid colors, NO gradients, transparent background,
> no text. A friendly cute shield "guardian" mascot next to a giant key and a
> security certificate, with a small radar discovering hidden keys floating
> around. Clean modern flat style (getillustrations.com vibe). Indigo #4F46E5
> and #6366F1 as the main colors, amber #F59E0B and emerald #10B981 accents,
> soft pink #FBCFE8 sparingly. Rounded, friendly, centered with padding. 1024x1024.

**empty-state.png**
> Flat vector illustration, solid colors, NO gradients, transparent background,
> no text. A cute radar dish or satellite scanning empty space ("nothing found
> yet"), indigo #4F46E5 and #6366F1 with light indigo #EEF1FF. Minimal, friendly,
> centered. 768x768.

**complete.png**
> Flat vector illustration, solid colors, NO gradients, transparent background,
> no text. A cheerful shield mascot with a green check mark and a little confetti,
> signaling success. Emerald #10B981 and indigo #4F46E5. Rounded, friendly,
> centered. 768x768.

After saving a file here, just reload the page (`npm run dev` picks it up).

# FarmTwin AI visual design system

## Direction

FarmTwin uses **Block & Bloom**: a warm agricultural SaaS interface paired with original, crisp geometric mini-illustrations. It borrows the visual idea of tiled farm boards without copying any game, brand, texture pack, or character design.

## Palette

- Forest: `#153D2D` — navigation and deepest text
- Meadow: `#285943` — primary actions
- Moss: `#78A25E` — active crops and success states
- Sage: `#DCE9CE` — soft surfaces and icon fields
- Cream: `#F7F5EE` — page background
- Wheat: `#F4E8C9` — warm highlights
- Barn red: `#B9574E` — alerts and structural accents
- Sky: `#8BB7CB` — water/weather cues
- Soil: `#9B8265` — storage/earth details

## Components

Cards use a warm-white surface, a quiet one-pixel border, and a short soft shadow. Status pills communicate data provenance or workflow state. Primary actions use Meadow; destructive or alert actions use Barn red. Major interactions have visible hover/focus states and remain text-labeled.

## Icon system

`frontend/src/components/PixelIcons.tsx` contains original inline SVG mini-icons. They use a two-tone palette, block geometry, and `shapeRendering="crispEdges"` so they remain legible from 20px cards to the farm map. `ProductAvatar`, `FacilityIcon`, and `PixelIcon` are reusable across the dashboard, map, detail panels, and later modules.

## Map language

The farm map is a database-backed board: plots remain clickable records, but are rendered as tiled parcels with crop avatars, paths, water, and building markers. The map is illustrative, while plot identity and details continue to come from the API.

## Accessibility

The palette maintains dark green text on cream/white surfaces, status labels supplement color, buttons remain keyboard-focusable, and decorative SVGs use `aria-hidden`. Playful elements never replace the operational label or synthetic-data badge.

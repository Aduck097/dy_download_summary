# Web Console UI Map

## Design Intent

The UI should feel like a product, not an internal admin table dump.

Reference direction:

- Apple-like calm
- editorial spacing
- premium but not flashy

## Key Screens

### Dashboard

Top area:

- product title
- current machine status
- quick action button

Main cards:

- active runs
- recent finals
- failures needing attention

### Project List

Each project row card should show:

- slug
- source
- latest stage
- latest updated time
- quick open

### Project Detail

Hero:

- title
- source url
- recommended route
- run actions

Stage timeline:

- 10 stage cards
- status pill
- duration
- key file chips

Artifact section:

- JSON cards
- media cards
- compare report card

### Config

Form sections:

- providers
- model parameters
- local tool paths
- default scene settings

## Components

- `PageShell`
- `SectionHeader`
- `StatusPill`
- `StageCard`
- `ArtifactCard`
- `JsonPreview`
- `MediaPreview`
- `ConfigField`
- `MaskedSecretInput`
- `PrimaryActionBar`

## Design Tokens

### Background

- page: warm white
- card: white
- elevated card: white with light shadow

### Border

- use soft gray borders
- prefer 1px subtle separators over heavy boxes

### Radius

- large radius on cards
- medium radius on controls

### Type Scale

- hero: large and airy
- section: medium bold
- metadata: small and quiet

### Shadows

- one very soft shadow family only

## Anti-Patterns

- no dense admin tables as the main UI
- no neon or dark dashboard aesthetic
- no giant sidebar taking visual focus
- no overuse of badges and colors

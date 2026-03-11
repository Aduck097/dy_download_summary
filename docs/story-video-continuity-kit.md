# Story Video Continuity Kit

This kit defines the minimum continuity data that a remake pipeline should carry between `rewrite`, `storyboard`, and final rendering.

It is designed for the current project pipeline:

`STT -> summary -> rewrite -> TTS -> continuity kit -> director storyboard -> route A / route B -> final mux`

## Why This Exists

Fixing continuity requires more than a single character image.

The pipeline needs to preserve four layers at the same time:

1. Character continuity
2. Scene continuity
3. Shot-to-shot continuity
4. Narrative continuity

The three JSON artifacts in this kit cover those layers explicitly.

## Files

### `character_bible.json`

Use this to lock down identity and styling.

It should answer:

- Who is the protagonist?
- What do they look like?
- What are they wearing?
- What should never change?

Recommended usage:

- Reuse the same `character_id` across all scenes.
- Store one to three reference images per character.
- Keep wardrobe and age range stable inside one sequence.

### `scene_bible.json`

Use this to lock down repeatable locations and mood.

It should answer:

- Where does the story happen?
- What time of day is it?
- What is the lighting and palette?
- Which props must recur?

Recommended usage:

- Reuse the same `scene_id` when multiple shots belong to the same place.
- Keep each short remake inside one or two core locations.
- Treat `must_keep` as hard constraints for prompt building.

### `shot_continuity.json`

Use this to connect rewritten narration beats to directed shots.

It should answer:

- What beat does this shot serve?
- What exact visual state is inherited from the previous shot?
- What changes in this shot?
- What should the next shot inherit?

Recommended usage:

- Each shot should declare `prev_visual_state` and `next_visual_state`.
- Use `continuity_anchor` as the compact prompt-safe summary.
- Keep camera intent separate from image description.

## How To Fit It Into The Current Pipeline

### After `04_rewrite`

Generate:

- `04_rewrite/character_bible.json`
- `04_rewrite/scene_bible.json`

These become the stable references for the rest of the project.

### Before `06_storyboard`

Generate:

- `06_storyboard/shot_continuity.json`

This is the bridge between spoken rewrite beats and final shot prompts.

### Route A: Qwen Image + FFmpeg

Prompt builder should combine:

- `character_bible.identity_prompt`
- `scene_bible.location_prompt`
- `shot_continuity.continuity_anchor`
- `shot_continuity.camera_plan`

This reduces drift between still-image generations.

### Route B: Image-to-Video / Reference-to-Video

Model input should prefer:

- same character references
- same scene references
- previous keyframe or previous clip tail frame
- `shot_continuity.prev_visual_state`

This reduces clip-to-clip resets.

## Prompt Assembly Rules

Build prompts in layers instead of writing each shot from scratch.

1. Base identity
2. Base scene
3. Beat-specific action
4. Camera intent
5. Transition intent

Avoid restating the entire story in every prompt. Reuse the same stable fields and only vary the local action.

## Practical Constraints

- One short project should usually keep one protagonist and one wardrobe set.
- One conversation should usually stay in one location.
- Scene changes should be explicit, not accidental.
- The first shot of a new location should be an establishing shot.
- Dialogue-heavy shots should prioritize facial consistency over large action.

## Suggested Future Integration

The current repository can evolve toward this structure:

- `03_summary/summary.json`
- `04_rewrite/rewrite.json`
- `04_rewrite/character_bible.json`
- `04_rewrite/scene_bible.json`
- `05_tts/tts_manifest.json`
- `06_storyboard/shot_continuity.json`
- `06_storyboard/director_plan.json`
- `06_storyboard/scene_plan.json`

That keeps continuity data close to the stage that owns it.

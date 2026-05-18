# Two-Stage Composition Planner Design

## Summary

This design replaces the current direct `SceneSpec -> renderer` flow with a two-stage composition system:

1. Parse the prompt into a semantic `SceneSpec`.
2. Run a composition planner that generates and scores layout candidates.
3. Emit a `RenderPlan` with final boxes, scale, z-order, motion, and background policies.
4. Render strictly from the `RenderPlan`.

The goal is to improve composition quality for multi-region prompts, increase semantic expressiveness, and eliminate stray line artifacts by moving layout and motion decisions into an explicit planning layer.

## Goals

- Improve ratio, spacing, and visual balance when prompts contain multiple regions.
- Prefer expressive compositions over rigid region boxes.
- Infer visual hierarchy implicitly from subject type and prompt semantics.
- Treat named regions as soft constraints rather than absolute clipping boxes.
- Keep backgrounds minimal by default and prevent background artifacts from reading as noise.
- Make renderer behavior deterministic and easier to tune by separating planning from drawing.

## Non-Goals

- Do not replace procedural sprite rendering with image generation.
- Do not ask the LLM to generate final layout geometry.
- Do not introduce freeform background decoration that competes with the foreground.
- Do not pursue full physics, collision simulation, or frame-by-frame composition search.

## Current Problems

The current renderer uses hard-coded region bounds and renders each region independently. This creates several failure modes:

- Multi-region prompts can look mechanically partitioned, with weak coordination across regions.
- Subject size is derived locally from sprite logic instead of scene-level composition.
- Motion cues such as trails or arcs can appear disconnected from the subject and read as background artifacts.
- Background effects are decided inside the renderer rather than through a scene-level cleanliness policy.

## Proposed Architecture

The new pipeline will be:

`prompt -> SceneSpec -> CompositionPlanner -> RenderPlan -> PixelRenderer`

### SceneSpec responsibilities

`SceneSpec` remains the semantic contract from the parser:

- prompt
- palette
- animation
- regions
- subject type
- motion type
- raw content

It should continue to describe intent, not final geometry.

### CompositionPlanner responsibilities

The planner owns composition decisions:

- infer foreground hierarchy
- convert region names into soft anchor preferences
- generate candidate layouts for each scene
- score the candidates
- choose the best layout
- emit final draw instructions in a `RenderPlan`

### RenderPlan responsibilities

`RenderPlan` becomes the renderer input contract. Each drawable element should include:

- `element_id`
- `subject`
- `content`
- `anchor_region`
- `box`
- `scale`
- `z_order`
- `safe_margin`
- `trail_policy`
- `background_policy`
- `style_hints`

The renderer should no longer decide region placement from `RegionName` directly.

### Renderer responsibilities

The renderer becomes a pure executor:

- rasterize objects into the planner-provided box
- respect scale, margins, and z-order
- apply trail rendering only if allowed by `trail_policy`
- apply background rendering only if allowed by `background_policy`

The current `_REGION_BOUNDS` table should remain only as a planner seed or fallback anchor source, not as the final layout truth.

## Planner Design

The planner should be rule-based with candidate search and scene scoring.

### Hierarchy inference

The planner should infer importance even when the prompt does not state it explicitly.

Default hierarchy:

- `object` usually outranks `text`
- `object` usually outranks `progress_bar`
- `progress_bar` is supportive and should remain visually narrow and stable
- decorative or secondary objects should yield visual emphasis to the main subject

Additional semantic cues can raise importance:

- character-like entities
- single iconic props
- animated subjects with clear action verbs
- center-oriented entities

When two objects compete, the planner should prefer:

1. semantic centrality
2. stronger motion relevance
3. cleaner scene balance

### Soft region anchoring

Named regions become anchor preferences instead of hard boxes.

Examples:

- `top` prefers upper visual territory but may extend toward the center if needed
- `left` prefers left-weighted placement but may overlap toward center to preserve balance
- `center` has the strongest central pull but should still coexist with nearby anchored elements

The planner should preserve reading order and semantic intent while allowing limited box relaxation, overlap, and bleed across old region boundaries.

### Candidate generation

The planner should generate multiple candidate compositions from the same `SceneSpec`.

Candidate axes include:

- subject scale
- local margin
- anchor offset
- overlap allowance
- center-of-mass bias
- primary-subject emphasis
- progress-bar thickness and width
- motion cue visibility

At minimum, the candidate pool should cover:

- balanced composition
- primary-subject-forward composition
- flow-oriented composition

### Candidate scoring

The planner should score candidates using explicit scene metrics.

Positive signals:

- clear primary subject
- natural spacing
- stable visual center
- coherent reading order
- motion that supports subject identity

Negative signals:

- crowding
- dead empty space
- edge-hugging boxes
- progress bars that dominate the scene
- visually isolated motion marks
- long thin artifacts that can be mistaken for background noise

The background cleanliness penalty should be strong. If a candidate creates lines, arcs, or marks that are disconnected from a readable subject silhouette, it should score poorly.

### Planner output stability

The planner should remain deterministic for the same parsed input unless an explicit future option introduces variation. This keeps output behavior testable and prevents hard-to-debug drift.

## Background Policy

The default background policy should be minimal.

Rules:

- background elements should never compete with foreground composition
- no full-scene decorative lines by default
- point-like or very low-salience accents are acceptable
- palette-specific background motifs must be opt-in through planner policy, not renderer side effects

For the current retro scanline behavior, the planner should decide whether the scene can safely support it. The default answer should be no unless the composition explicitly has enough visual density and contrast to avoid reading the scanlines as stray defects.

## Trail Policy

Motion trails should become policy-controlled scene elements rather than automatic renderer behavior.

The planner should decide whether trails are:

- disabled
- shortened
- clipped to a safe area
- softened
- fully enabled

Trails should be rejected or reduced when:

- the subject is too small
- nearby whitespace is too large
- the trail lands in isolation
- the trail shape resembles background noise more than motion

## Sprite Pattern Policy

Internal sprite patterns may remain, but they must stay fully attached to the sprite silhouette. Pattern logic should never create detached strokes, floating points, or visually ambiguous fragments outside the subject body.

## Data Model Changes

The design requires introducing explicit planner-facing models.

Recommended additions:

- `LayoutAnchor`
- `RenderBox`
- `TrailPolicy`
- `BackgroundPolicy`
- `RenderElementPlan`
- `RenderPlan`

`SceneSpec` should remain semantic. The new models should absorb render-time geometry and policy decisions.

## Error Handling

If planning fails or no candidate reaches a valid score threshold:

- fall back to a conservative anchored layout
- disable optional trail effects
- disable decorative background effects
- keep primary-subject emphasis and safe spacing rules intact

Failure should degrade toward a clean, simple composition rather than an expressive but noisy one.

## Testing Strategy

### Planner unit tests

Add tests for:

- multi-region prompts produce coordinated layouts
- inferred hierarchy makes `object` dominate `progress_bar` when appropriate
- region softening does not destroy scene readability
- candidates with isolated line artifacts receive worse scores

### Render contract tests

Add tests for:

- renderer accepts `RenderPlan` instead of deriving layout directly from `RegionName`
- renderer respects provided boxes and z-order
- disabled trail policies produce no trail artifacts
- minimal background policy suppresses legacy scanline behavior

### Visual regression checks

Add lightweight regression coverage for representative prompts:

- top object + bottom progress bar
- left object + right object
- center object + text
- retro palette scene

Checks can start with simple structural signals instead of full image-diff infrastructure:

- alpha bounding box distribution
- connected-component count
- long-line detection
- foreground occupancy ratios

## Implementation Notes

The first implementation pass should favor clear boundaries over maximum feature count.

Suggested order:

1. introduce planner and `RenderPlan` models
2. refactor renderer to consume the new contract
3. preserve current visual motifs while moving layout decisions into the planner
4. move trail and background behavior behind explicit policies
5. add planner and render contract tests
6. update `README.md` to describe the new planning stage once implementation begins

## Trade-Offs

This design increases complexity compared with the current direct renderer path, but that complexity is focused in the right place: composition logic.

Benefits:

- better multi-region compositions
- fewer stray visual artifacts
- clearer separation of concerns
- more controlled future extensibility

Costs:

- more models and planner logic
- candidate scoring parameters will need tuning
- regression coverage becomes more important

## Recommendation

Implement the composition planner as a deterministic rule-based candidate search with scoring. Keep the parser semantic and the renderer execution-only. This gives the system more expressive composition behavior without handing unstable geometry decisions back to the LLM.

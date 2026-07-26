# Orrery W1 Focus And Relation Visibility Review

## Scope

This review closes W1-Fix A and W1-Fix B only. It does not claim completion of
search, minimap, reader synchronization, advanced lenses, or visual regression.

## Architecture Result

1. `spatialProjection` remains the only semantic focus authority. Camera movement
   continues to be presentation state and cannot impersonate chapter or character
   scope.
2. Chapter-rail intent is isolated in the pure `chapterRailFocusTarget()` helper.
   The component no longer branches into a scene identity for convenience.
3. Relation visibility is isolated in `model/relationLens.ts`. The backend profile
   remains the semantic contract; the frontend may filter or emphasize edges but
   cannot create or mutate formal relationships.
4. Both Pixi and SVG layers consume the same profile modes. Fixed `slice()` limits
   were removed from semantic relationships and character navigation.
5. The new control is a compact observational instrument. It writes no project
   files and introduces no API or workflow lifecycle.

## Failure And Compatibility Review

- Feature state is reset when the current project changes.
- A missing relation profile falls back deterministically by focus level.
- Solo mode preserves nodes and only exposes exact edges from one relation family.
- Focus history is bounded to 32 entries and does not record grammar-only changes.
- Existing book/chapter/scene calls remain source compatible.
- Character focus remains additive: the backend keeps whole-book context.

## Verification

- `npm run client:test`: 106 passed.
- `python -m unittest tests.test_narrative_projection_v3 -v`: 9 passed.
- Full Python suite: 628 passed, 1 skipped.
- `vue-tsc -p client/tsconfig.json --noEmit`: passed.
- `npm run client:build`: passed.
- Architecture Audit: 35 existing file debts, 224 existing function debts,
  0 cycles, and no new debt.
- Browser validation on `1+1=2`: character focus/back, relation lens, and
  scene-to-chapter rail transition passed.

## Remaining Risks

The semantic relationships are no longer discarded, but large works still need
search, minimap/beacons, explicit show-all labels, and repeatable visual regression.
Those remain W1-Fix C/D and W1-Exit work, not AO-8 plan visualization.

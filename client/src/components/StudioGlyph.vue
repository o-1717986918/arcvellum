<script setup lang="ts">
withDefaults(defineProps<{ kind?: "book" | "orbit" | "language" | "archive"; progress?: number | null }>(), { kind: "book", progress: null });
</script>

<template>
  <svg class="studio-glyph" :class="`studio-glyph-${kind}`" viewBox="0 0 96 96" fill="none" aria-hidden="true">
    <circle class="glyph-guide" cx="48" cy="48" r="39" />
    <path class="glyph-tick" d="M48 5v7M48 84v7M5 48h7M84 48h7" />
    <template v-if="kind === 'book'">
      <path class="glyph-paper" d="M28 25 47 31 68 23v45L48 75 28 69Z" />
      <path class="glyph-ink" d="M47 31v44M28 25v44l20 6 20-7V23l-21 8Z" />
      <path class="glyph-tick" d="m21 32 1 43 23 7 29-10V30M33 36l8 3m-8 5 8 3m12-8 9-3m-9 11 9-3m-9 11 9-3" />
      <path class="glyph-orbit" d="M13 57C28 24 72 14 84 30S65 72 31 75" />
      <circle class="glyph-brass" cx="80" cy="27" r="4" />
    </template>
    <template v-else-if="kind === 'orbit'">
      <ellipse class="glyph-tick" cx="48" cy="48" rx="36" ry="15" transform="rotate(-35 48 48)" />
      <ellipse class="glyph-ink" cx="48" cy="48" rx="18" ry="33" transform="rotate(-35 48 48)" />
      <circle class="glyph-paper" cx="48" cy="48" r="12" />
      <circle class="glyph-brass" cx="74" cy="23" r="4" />
      <path class="glyph-orbit" d="M39 48h18M48 39v18" />
    </template>
    <template v-else-if="kind === 'language'">
      <path class="glyph-tick" d="M18 28h60M18 48h60M18 68h60M28 18v60M48 18v60M68 18v60" />
      <path class="glyph-ink" d="M15 58c13 0 13-31 26-31s13 41 26 41 13-30 15-30" />
      <path class="glyph-orbit" d="M15 65c13 0 13-18 26-18s13 9 26 9 13-17 15-17" />
      <circle class="glyph-brass" cx="41" cy="27" r="4" />
    </template>
    <template v-else>
      <path class="glyph-tick" d="m22 36 26-14 26 14-26 15Zm0 12 26 15 26-15M22 60l26 15 26-15" />
      <path class="glyph-ink" d="M22 36v24l26 15 26-15V36M48 51v24" />
      <circle class="glyph-brass" cx="48" cy="22" r="4" />
      <path class="glyph-orbit" d="M14 64c4 12 48 22 68-6" />
    </template>
    <circle v-if="progress != null" class="glyph-progress" cx="48" cy="48" r="44" pathLength="100" :stroke-dasharray="`${Math.max(0, Math.min(100, progress))} 100`" transform="rotate(-90 48 48)" />
  </svg>
</template>

<style scoped>
.studio-glyph { display: block; width: 96px; height: 96px; color: var(--pa-green, #367d6a); flex: none; }
.glyph-guide { stroke: currentColor; stroke-width: .65; opacity: .2; stroke-dasharray: 1 4; }
.glyph-tick { stroke: currentColor; stroke-width: .8; opacity: .42; }
.glyph-ink { stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.glyph-paper { fill: var(--pa-green-soft, #e3eee8); fill-opacity: .8; }
.glyph-orbit { stroke: var(--pa-blue, #53658a); stroke-width: 1; stroke-linecap: round; }
.glyph-brass { fill: var(--pa-ochre, #ad8847); stroke: var(--pa-surface, #f7faf7); stroke-width: 2; }
.glyph-progress { stroke: currentColor; stroke-width: 2; stroke-linecap: round; transition: stroke-dasharray .7s ease; }
@media (prefers-reduced-motion: reduce) { .glyph-progress { transition: none; } }
</style>

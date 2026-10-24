<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ type: string }>();

const paths = computed(() => {
  switch (props.type) {
    case "image":
      return [
        { d: "M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z" },
        { d: "M4 15.5 9 11l4.5 4.5" },
        { d: "m15 14 1.8-1.8L20 15.4" },
        { cx: 14.6, cy: 8.6, r: 1.5 }
      ];
    case "video":
      return [
        { d: "M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z" },
        { d: "m10 9.2 5 2.8-5 2.8z" }
      ];
    case "audio":
      return [
        { d: "M9 17.5V6.2a1 1 0 0 1 .8-1l6-1.2a1 1 0 0 1 1.2 1v10.5" },
        { cx: 6.8, cy: 17.5, r: 2.2 },
        { cx: 14.8, cy: 15.5, r: 2.2 }
      ];
    case "document":
      return [
        { d: "M13.5 4H7A1.5 1.5 0 0 0 5.5 5.5v13A1.5 1.5 0 0 0 7 20h10a1.5 1.5 0 0 0 1.5-1.5V9z" },
        { d: "M13.5 4V9H18.5" },
        { d: "M9 13h6M9 16.5h6" }
      ];
    default:
      return [
        { d: "m12 3 8 4v10l-8 4-8-4V7z" },
        { d: "m4 7 8 4 8-4" },
        { d: "M12 11v10" }
      ];
  }
});
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-for="(p, i) in paths" :key="i">
      <path v-if="p.d" :d="p.d" />
      <circle v-else-if="p.cx" :cx="p.cx" :cy="p.cy" :r="p.r" />
    </template>
  </svg>
</template>

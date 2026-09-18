<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { Language } from "../types";

const props = defineProps<{ data: Record<string, unknown>; language: Language }>();
const { t } = useI18n();

const team = computed(() => {
  const value = props.data.team;
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const names = value as Record<string, unknown>;
    return typeof names[props.language] === "string" ? names[props.language] as string : "";
  }
  return "";
});

const formation = computed(() => typeof props.data.formation === "string" ? props.data.formation : "");
const players = computed(() => {
  const value = props.data.lineup ?? props.data.slots;
  if (!Array.isArray(value)) return [];
  return value.flatMap((slot) => {
    if (typeof slot === "string") return [slot];
    if (!slot || typeof slot !== "object") return [];
    const record = slot as Record<string, unknown>;
    if (record.hidden === true) return ["____"];
    const name = record.name ?? record.player;
    return typeof name === "string" ? [name] : [];
  });
});

const rows = computed(() => {
  const widths = formation.value.split("-").map(Number);
  if (!widths.length || widths.some((width) => !Number.isInteger(width) || width < 1 || width > 5)) return [];
  if (widths.reduce((total, width) => total + width, 0) !== 10 || players.value.length !== 11) return [];

  let offset = 1;
  const fromGoal = [players.value.slice(0, 1)];
  for (const width of widths) {
    fromGoal.push(players.value.slice(offset, offset + width));
    offset += width;
  }
  return fromGoal.reverse();
});

function isHidden(name: string) {
  return /^_+$/.test(name.trim());
}
</script>

<template>
  <figure class="lineup-figure">
    <figcaption class="lineup-caption">
      <span>{{ team || t("lineup.startingEleven") }}</span>
      <strong v-if="formation">{{ formation }}</strong>
    </figcaption>

    <div v-if="rows.length" class="lineup-pitch" role="group" :aria-label="t('lineup.pitchLabel', { team: team || t('lineup.startingEleven'), formation })">
      <div class="lineup-field" aria-hidden="true">
        <span class="lineup-center-line"></span>
        <span class="lineup-center-circle"></span>
        <span class="lineup-penalty lineup-penalty-top"></span>
        <span class="lineup-penalty lineup-penalty-bottom"></span>
      </div>
      <div class="lineup-rows">
        <div v-for="(row, rowIndex) in rows" :key="rowIndex" class="lineup-row">
          <span
            v-for="(name, playerIndex) in row"
            :key="`${rowIndex}-${playerIndex}`"
            class="lineup-player"
            :class="{ 'lineup-player-missing': isHidden(name) }"
          >{{ isHidden(name) ? t("lineup.missingPlayer") : name }}</span>
        </div>
      </div>
    </div>

    <div v-else class="lineup-fallback">
      <span v-for="(name, index) in players" :key="index" class="entry-chip">{{ isHidden(name) ? t("lineup.missingPlayer") : name }}</span>
    </div>
  </figure>
</template>

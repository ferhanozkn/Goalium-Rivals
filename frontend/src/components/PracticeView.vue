<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { createPracticeSession, submitPracticeAnswer } from "../lib/api";
import { useSessionStore } from "../stores/session";
import type { Language, ModeDefinition, PracticeMode, PracticeRound, PracticeSessionResponse } from "../types";

const props = defineProps<{
  language: Language;
  modes: ModeDefinition[];
}>();

const emit = defineEmits<{ back: [] }>();
const { t } = useI18n();
const session = useSessionStore();
const selectedModes = ref<PracticeMode[]>([]);
const practice = ref<PracticeSessionResponse | null>(null);
const round = ref<PracticeRound | null>(null);
const score = ref(0);
const loading = ref(false);
const submitting = ref(false);
const completed = ref(false);
const error = ref("");
const lastResult = ref<"correct" | "wrong" | "timeout" | "skipped" | "active" | "">("");
const lastPoints = ref(0);
const letterInput = ref("");
const textInput = ref("");
const homeScore = ref<number | null>(null);
const awayScore = ref<number | null>(null);
const selectedChoice = ref<number | null>(null);
const now = ref(Date.now());
const timeoutSubmitted = ref<string | null>(null);
let timer: ReturnType<typeof window.setInterval> | null = null;

const activeModeDefinition = computed(() => props.modes.find((mode) => mode.id === round.value?.mode));
const activeLanguage = computed(() => practice.value?.session.language ?? props.language);
const roundData = computed(() => round.value?.data ?? {});
const secondsRemaining = computed(() => {
  if (!round.value) return 0;
  return Math.max(0, Math.ceil((new Date(round.value.deadline).getTime() - now.value) / 1000));
});
const timerUrgent = computed(() => secondsRemaining.value <= 10);
const roundLabel = computed(() =>
  t("practice.roundLabel", {
    current: (round.value?.order ?? 0) + 1,
    total: selectedModes.value.length > 1 ? selectedModes.value.length : "∞",
  }),
);
const pattern = computed(() => String(roundData.value.pattern ?? ""));
const visibleEntries = computed(() => displayList("entries"));
const visibleSlots = computed(() => displayList("slots"));
const wrongLetters = computed(() => stringList("wrong_letters"));

function stringList(key: string): string[] {
  const value = roundData.value[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function displayList(key: string): string[] {
  const value = roundData.value[key];
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "string") return [item];
    if (item && typeof item === "object") {
      return [Object.values(item).filter((part): part is string => typeof part === "string").join(" · ")];
    }
    return [];
  });
}

function localized(value: unknown): string {
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return String(record[activeLanguage.value] ?? Object.values(record)[0] ?? "");
  }
  return String(value ?? "");
}

function modeTitle(mode: ModeDefinition) {
  return t(mode.title_key);
}

function modeDescription(mode: ModeDefinition) {
  return t(mode.description_key);
}

function toggleMode(mode: PracticeMode) {
  selectedModes.value = selectedModes.value.includes(mode)
    ? selectedModes.value.filter((item) => item !== mode)
    : [...selectedModes.value, mode];
}

function selectAllModes() {
  selectedModes.value = props.modes.map((mode) => mode.id as PracticeMode);
}

function resetInputs() {
  letterInput.value = "";
  textInput.value = "";
  homeScore.value = null;
  awayScore.value = null;
  selectedChoice.value = null;
}

async function startPractice() {
  if (!selectedModes.value.length) return;
  loading.value = true;
  error.value = "";
  try {
    await session.ensureGuest();
    practice.value = await createPracticeSession(props.language, selectedModes.value);
    round.value = practice.value.round;
    score.value = 0;
    completed.value = false;
    lastResult.value = "";
    lastPoints.value = 0;
    resetInputs();
  } catch {
    error.value = t("practice.error");
  } finally {
    loading.value = false;
  }
}

async function submitAnswer(answer: Record<string, unknown>) {
  if (!practice.value || !round.value || submitting.value) return;
  submitting.value = true;
  error.value = "";
  try {
    const response = await submitPracticeAnswer(practice.value.session.id, round.value.id, answer);
    score.value = response.score;
    lastResult.value = response.result;
    lastPoints.value = response.points;
    if (response.next_round) {
      round.value = response.next_round;
      resetInputs();
    } else if (response.round.status === "active") {
      round.value = response.round;
    } else {
      round.value = null;
      completed.value = true;
    }
  } catch {
    error.value = t("practice.answerError");
  } finally {
    submitting.value = false;
  }
}

function submitLetter() {
  const letter = letterInput.value.trim();
  if (letter) void submitAnswer({ letter });
}

function submitText() {
  const text = textInput.value.trim();
  if (text) void submitAnswer({ text });
}

function submitScore() {
  if (homeScore.value === null || awayScore.value === null) return;
  void submitAnswer({ home: homeScore.value, away: awayScore.value });
}

function submitChoice(choiceIndex: number) {
  selectedChoice.value = choiceIndex;
  void submitAnswer({ choice_index: choiceIndex });
}

function tick() {
  now.value = Date.now();
  if (round.value && round.value.status === "active" && secondsRemaining.value <= 0 && timeoutSubmitted.value !== round.value.id) {
    timeoutSubmitted.value = round.value.id;
    void submitAnswer({ action: "timeout" });
  }
}

function backToHome() {
  practice.value = null;
  round.value = null;
  completed.value = false;
  emit("back");
}

function restart() {
  practice.value = null;
  round.value = null;
  completed.value = false;
  lastResult.value = "";
  score.value = 0;
  resetInputs();
}

watch(
  () => round.value?.id,
  () => {
    timeoutSubmitted.value = null;
    now.value = Date.now();
  },
);

onMounted(() => {
  timer = window.setInterval(tick, 250);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <section id="practice" class="practice-shell">
    <div class="practice-toolbar">
      <button class="text-button" type="button" @click="backToHome">← {{ t("practice.back") }}</button>
      <div class="practice-toolbar-meta">
        <span>{{ t("practice.eyebrow") }}</span>
        <span v-if="practice" class="practice-score">{{ t("practice.score") }} {{ score }}</span>
      </div>
    </div>

    <div v-if="!practice" class="practice-setup">
      <div class="section-heading practice-heading">
        <div>
          <p class="eyebrow">02 / {{ t("practice.eyebrow") }}</p>
          <h2>{{ t("practice.title") }}</h2>
        </div>
        <p>{{ t("practice.description") }}</p>
      </div>

      <div class="practice-mode-grid">
        <button
          v-for="mode in modes"
          :key="mode.id"
          class="practice-mode-card"
          :class="{ selected: selectedModes.includes(mode.id as PracticeMode) }"
          type="button"
          @click="toggleMode(mode.id as PracticeMode)"
        >
          <span class="mode-index">{{ String(modes.indexOf(mode) + 1).padStart(2, "0") }}</span>
          <span class="practice-mode-copy">
            <strong>{{ modeTitle(mode) }}</strong>
            <span>{{ modeDescription(mode) }}</span>
          </span>
          <span class="mode-duration">{{ mode.duration_seconds }} {{ t("common.seconds") }}</span>
        </button>
      </div>

      <div class="practice-actions">
        <button class="button button-primary" type="button" :disabled="loading || !selectedModes.length" @click="startPractice">
          {{ loading ? t("status.loading") : t("practice.start") }}
        </button>
        <button class="button button-quiet" type="button" :disabled="loading" @click="selectAllModes">{{ t("practice.allModes") }}</button>
      </div>
      <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    </div>

    <div v-else-if="completed" class="practice-complete">
      <p class="eyebrow">{{ t("practice.completeEyebrow") }}</p>
      <h2>{{ t("practice.completeTitle") }}</h2>
      <p>{{ t("practice.finalScore", { score }) }}</p>
      <div class="practice-actions">
        <button class="button button-primary" type="button" @click="restart">{{ t("practice.playAgain") }}</button>
        <button class="button button-quiet" type="button" @click="backToHome">{{ t("practice.back") }}</button>
      </div>
    </div>

    <div v-else-if="round" class="practice-game">
      <div class="practice-round-rail">
        <span>{{ roundLabel }}</span>
        <span class="practice-timer" :class="{ urgent: timerUrgent }">{{ t("practice.time") }} {{ secondsRemaining }}{{ t("common.secondsShort") }}</span>
      </div>

      <div class="practice-question-header">
        <p class="eyebrow">{{ activeModeDefinition ? modeTitle(activeModeDefinition) : round.mode }}</p>
        <h2>{{ round.prompt }}</h2>
        <p v-if="activeModeDefinition" class="question-caption">{{ modeDescription(activeModeDefinition) }}</p>
      </div>

      <div class="practice-question-card">
        <div v-if="round.mode === 'hangman'" class="mode-play-area">
          <div class="hangman-pattern" aria-live="polite">{{ pattern }}</div>
          <div class="hint-row">
            <span>{{ t("practice.wrongLetters", { letters: wrongLetters.join(", ") || "—" }) }}</span>
            <span>{{ t("practice.hintsUsed", { used: round.data.hint_count ?? 0, max: round.data.max_hints ?? 0 }) }}</span>
          </div>
          <div class="answer-row">
            <input v-model="letterInput" maxlength="1" :placeholder="t('practice.letterPlaceholder')" :aria-label="t('practice.letterPlaceholder')" @keyup.enter="submitLetter" />
            <button class="button button-primary" type="button" :disabled="submitting || !letterInput.trim()" @click="submitLetter">{{ t("practice.tryLetter") }}</button>
            <button class="button button-quiet" type="button" :disabled="submitting || Number(round.data.hint_count ?? 0) >= Number(round.data.max_hints ?? 0)" @click="submitAnswer({ action: 'hint' })">{{ t("practice.useHint") }}</button>
          </div>
        </div>

        <div v-else-if="round.mode === 'career_path'" class="mode-play-area">
          <div class="entry-list">
            <span v-for="entry in visibleEntries" :key="entry" class="entry-chip">{{ entry }}</span>
          </div>
          <p class="attempts-label">{{ t("practice.attempts", { used: round.data.attempts_used ?? 0, max: round.data.max_attempts ?? 0 }) }}</p>
          <div class="answer-row">
            <input v-model="textInput" :placeholder="t('practice.playerPlaceholder')" :aria-label="t('practice.playerPlaceholder')" @keyup.enter="submitText" />
            <button class="button button-primary" type="button" :disabled="submitting || !textInput.trim()" @click="submitText">{{ t("practice.submit") }}</button>
          </div>
        </div>

        <div v-else-if="round.mode === 'timed_trivia'" class="mode-play-area">
          <div class="choice-grid">
            <button v-for="(choice, index) in round.choices" :key="choice" class="choice-button" :class="{ selected: selectedChoice === index }" type="button" :disabled="submitting" @click="submitChoice(index)">
              <span>{{ String.fromCharCode(65 + index) }}</span>{{ choice }}
            </button>
          </div>
          <button class="text-button skip-button" type="button" :disabled="submitting" @click="submitAnswer({ action: 'skip' })">{{ t("practice.skip") }} →</button>
        </div>

        <div v-else-if="round.mode === 'historical_score'" class="mode-play-area">
          <div class="score-inputs">
            <label><span>{{ localized(round.data.home_team) }}</span><input v-model.number="homeScore" min="0" type="number" /></label>
            <span class="score-separator">—</span>
            <label><span>{{ localized(round.data.away_team) }}</span><input v-model.number="awayScore" min="0" type="number" /></label>
          </div>
          <button class="button button-primary" type="button" :disabled="submitting || homeScore === null || awayScore === null" @click="submitScore">{{ t("practice.submitScore") }}</button>
        </div>

        <div v-else class="mode-play-area">
          <div class="lineup-slots">
            <span v-for="slot in visibleSlots" :key="slot" class="entry-chip">{{ slot }}</span>
          </div>
          <div class="answer-row">
            <input v-model="textInput" :placeholder="t('practice.playerPlaceholder')" :aria-label="t('practice.playerPlaceholder')" @keyup.enter="submitText" />
            <button class="button button-primary" type="button" :disabled="submitting || !textInput.trim()" @click="submitText">{{ t("practice.submit") }}</button>
          </div>
        </div>
      </div>

      <div class="practice-feedback" aria-live="polite">
        <span v-if="lastResult && lastResult !== 'active'" :class="lastResult === 'correct' ? 'feedback-correct' : 'feedback-muted'">
          {{ t(`practice.result.${lastResult}`) }} · {{ t("practice.points", { points: lastPoints }) }}
        </span>
        <span v-if="error" class="error-message" role="alert">{{ error }}</span>
      </div>
    </div>
  </section>
</template>

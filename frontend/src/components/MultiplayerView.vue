<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  createDuel,
  createRoom,
  fetchDuel,
  fetchRoom,
  joinDuel,
  joinRoom,
  startRoom,
  submitDuelAnswer,
  submitRoomAnswer,
} from "../lib/api";
import { useSessionStore } from "../stores/session";
import type { Language, ModeDefinition, MultiplayerAnswerResponse, MultiplayerResponse, PracticeMode, PracticeRound } from "../types";

const props = defineProps<{ language: Language; modes: ModeDefinition[] }>();
const emit = defineEmits<{ back: [] }>();
const { t } = useI18n();
const session = useSessionStore();
const kind = ref<"room" | "duel">("room");
const active = ref<MultiplayerResponse | null>(null);
const currentRound = ref<PracticeRound | null>(null);
const loading = ref(false);
const submitting = ref(false);
const error = ref("");
const roomMode = ref<"mixed" | PracticeMode>("mixed");
const roomCodeInput = ref("");
const duelIdInput = ref("");
const email = ref("");
const password = ref("");
const textInput = ref("");
const letterInput = ref("");
const homeScore = ref<number | null>(null);
const awayScore = ref<number | null>(null);
const selectedChoice = ref<number | null>(null);
const score = ref(0);
const lastResult = ref("");
const now = ref(Date.now());
let socket: WebSocket | null = null;
let poller: ReturnType<typeof window.setInterval> | null = null;
let timer: ReturnType<typeof window.setInterval> | null = null;

const activeMatch = computed(() => active.value?.match ?? null);
const roundData = computed(() => currentRound.value?.data ?? {});
const secondsRemaining = computed(() => currentRound.value ? Math.max(0, Math.ceil((new Date(currentRound.value.deadline).getTime() - now.value) / 1000)) : 0);
const activeMode = computed(() => props.modes.find((mode) => mode.id === currentRound.value?.mode));
const isOwner = computed(() => active.value?.participant_id === activeMatch.value?.participants?.[0]?.id);
const displayEntries = computed(() => displayList("entries"));
const displaySlots = computed(() => displayList("slots"));

function displayList(key: string): string[] {
  const value = roundData.value[key];
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "string") return [item];
    if (item && typeof item === "object") return [Object.values(item).filter((part): part is string => typeof part === "string").join(" · ")];
    return [];
  });
}

function localized(value: unknown): string {
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return String(record[props.language] ?? Object.values(record)[0] ?? "");
  }
  return String(value ?? "");
}

function modeTitle(mode: ModeDefinition) {
  return t(mode.title_key);
}

function applyResponse(response: MultiplayerResponse) {
  active.value = response;
  currentRound.value = response.round;
  score.value = response.match.participants.find((participant) => participant.id === response.participant_id)?.score ?? score.value;
  if (response.match.status === "waiting") currentRound.value = null;
}

function resetAnswerFields() {
  textInput.value = "";
  letterInput.value = "";
  homeScore.value = null;
  awayScore.value = null;
  selectedChoice.value = null;
}

async function ensureGuestAndRun(action: () => Promise<MultiplayerResponse>) {
  loading.value = true;
  error.value = "";
  try {
    await session.ensureGuest();
    applyResponse(await action());
    connectRealtime();
  } catch {
    error.value = t("multiplayer.error");
  } finally {
    loading.value = false;
  }
}

async function createRoomAction() {
  await ensureGuestAndRun(() => createRoom(props.language, roomMode.value === "mixed" ? { is_mixed: true, round_count: 5 } : { is_mixed: false, mode: roomMode.value, round_count: 1 }));
}

async function joinRoomAction() {
  const code = roomCodeInput.value.trim().toUpperCase();
  if (!code) return;
  await ensureGuestAndRun(() => joinRoom(code));
}

async function startRoomAction() {
  if (!activeMatch.value?.room_code) return;
  loading.value = true;
  try {
    applyResponse(await startRoom(activeMatch.value.room_code));
  } catch {
    error.value = t("multiplayer.error");
  } finally {
    loading.value = false;
  }
}

async function signIn() {
  loading.value = true;
  error.value = "";
  try {
    await session.signIn(email.value, password.value);
  } catch {
    error.value = t("multiplayer.loginError");
  } finally {
    loading.value = false;
  }
}

async function createDuelAction() {
  if (!session.user) return;
  loading.value = true;
  error.value = "";
  try {
    applyResponse(await createDuel(props.language, props.modes.map((mode) => mode.id as PracticeMode)));
  } catch {
    error.value = t("multiplayer.error");
  } finally {
    loading.value = false;
  }
}

async function joinDuelAction() {
  if (!duelIdInput.value.trim() || !session.user) return;
  loading.value = true;
  error.value = "";
  try {
    applyResponse(await joinDuel(duelIdInput.value.trim()));
  } catch {
    error.value = t("multiplayer.error");
  } finally {
    loading.value = false;
  }
}

function connectRealtime() {
  if (!activeMatch.value || kind.value !== "room") return;
  socket?.close();
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const token = session.guest?.guest_token;
  if (!token) return;
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/v1/match/${activeMatch.value.id}/?guest_token=${encodeURIComponent(token)}`);
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data) as Partial<{ type: string; status: string; participants: MultiplayerResponse["match"]["participants"]; mode: PracticeMode; id: string; deadline: string; server_now: string; prompt: string; choices: string[]; hints: string[]; data: Record<string, unknown> }>;
    if (message.type === "match.state" && active.value) {
      active.value.match = { ...active.value.match, status: message.status ?? active.value.match.status, participants: message.participants ?? active.value.match.participants };
    }
    if (message.type === "round.start" && message.id && message.mode && message.deadline && active.value) {
      currentRound.value = { id: message.id, order: 0, mode: message.mode, status: "active", deadline: message.deadline, server_now: message.server_now ?? new Date().toISOString(), prompt: message.prompt ?? "", choices: message.choices ?? [], hints: message.hints ?? [], data: message.data ?? {} };
    }
  });
}

async function refreshActive() {
  if (!active.value) return;
  try {
    const response = kind.value === "room" && active.value.match.room_code
      ? await fetchRoom(active.value.match.room_code)
      : await fetchDuel(active.value.match.id);
    applyResponse(response);
  } catch {
    // The realtime channel remains the source of live room updates.
  }
}

async function submitAnswer(answer: Record<string, unknown>) {
  if (!active.value || !currentRound.value || submitting.value) return;
  submitting.value = true;
  error.value = "";
  try {
    const response: MultiplayerAnswerResponse = kind.value === "room" && active.value.match.room_code
      ? await submitRoomAnswer(active.value.match.room_code, currentRound.value.id, answer)
      : await submitDuelAnswer(active.value.match.id, currentRound.value.id, answer);
    active.value.match = response.match;
    score.value = response.score;
    lastResult.value = response.result;
    currentRound.value = response.next_round;
    resetAnswerFields();
  } catch {
    error.value = t("multiplayer.answerError");
  } finally {
    submitting.value = false;
  }
}

function submitLetter() { if (letterInput.value.trim()) void submitAnswer({ letter: letterInput.value.trim() }); }
function submitText() { if (textInput.value.trim()) void submitAnswer({ text: textInput.value.trim() }); }
function submitScore() { if (homeScore.value !== null && awayScore.value !== null) void submitAnswer({ home: homeScore.value, away: awayScore.value }); }
function submitChoice(index: number) { selectedChoice.value = index; void submitAnswer({ choice_index: index }); }

function backToHome() {
  socket?.close();
  if (poller) window.clearInterval(poller);
  active.value = null;
  currentRound.value = null;
  emit("back");
}

onMounted(() => {
  timer = window.setInterval(() => { now.value = Date.now(); }, 250);
  poller = window.setInterval(() => { void refreshActive(); }, 2500);
});

onBeforeUnmount(() => {
  socket?.close();
  if (poller) window.clearInterval(poller);
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <section class="multiplayer-shell">
    <div class="practice-toolbar">
      <button class="text-button" type="button" @click="backToHome">← {{ t("multiplayer.back") }}</button>
      <span>{{ t("multiplayer.eyebrow") }}</span>
    </div>

    <div v-if="!active" class="multiplayer-setup">
      <div class="section-heading practice-heading">
        <div><p class="eyebrow">03 / {{ t("multiplayer.eyebrow") }}</p><h2>{{ t("multiplayer.title") }}</h2></div>
        <p>{{ t("multiplayer.description") }}</p>
      </div>
      <div class="multiplayer-tabs">
        <button :class="{ active: kind === 'room' }" :aria-pressed="kind === 'room'" type="button" @click="kind = 'room'">{{ t("multiplayer.roomTab") }}</button>
        <button :class="{ active: kind === 'duel' }" :aria-pressed="kind === 'duel'" type="button" @click="kind = 'duel'">{{ t("multiplayer.duelTab") }}</button>
      </div>

      <div v-if="kind === 'room'" class="multiplayer-grid">
        <div class="match-panel multiplayer-card">
          <p class="eyebrow">{{ t("multiplayer.createRoom") }}</p>
          <h3>{{ t("multiplayer.roomTitle") }}</h3>
          <div class="segmented-control">
            <button :class="{ active: roomMode === 'mixed' }" :aria-pressed="roomMode === 'mixed'" type="button" @click="roomMode = 'mixed'">{{ t("multiplayer.mixed") }}</button>
            <button v-for="mode in modes" :key="mode.id" :class="{ active: roomMode === mode.id }" :aria-pressed="roomMode === mode.id" type="button" @click="roomMode = mode.id as PracticeMode">{{ modeTitle(mode) }}</button>
          </div>
          <button class="button button-primary" type="button" :disabled="loading" @click="createRoomAction">{{ t("multiplayer.create") }}</button>
        </div>
        <div class="match-panel multiplayer-card">
          <p class="eyebrow">{{ t("multiplayer.joinRoom") }}</p>
          <h3>{{ t("multiplayer.joinTitle") }}</h3>
          <input v-model="roomCodeInput" class="wide-input" maxlength="6" :placeholder="t('multiplayer.roomCode')" :aria-label="t('multiplayer.roomCode')" @keyup.enter="joinRoomAction" />
          <button class="button button-quiet" type="button" :disabled="loading || !roomCodeInput" @click="joinRoomAction">{{ t("multiplayer.join") }}</button>
        </div>
      </div>

      <div v-else class="multiplayer-grid">
        <div v-if="!session.user" class="match-panel multiplayer-card">
          <p class="eyebrow">{{ t("multiplayer.accountRequired") }}</p>
          <h3>{{ t("multiplayer.loginTitle") }}</h3>
          <input v-model="email" class="wide-input" type="email" :placeholder="t('multiplayer.email')" :aria-label="t('multiplayer.email')" />
          <input v-model="password" class="wide-input" type="password" :placeholder="t('multiplayer.password')" :aria-label="t('multiplayer.password')" />
          <button class="button button-primary" type="button" :disabled="loading || !email || !password" @click="signIn">{{ t("multiplayer.login") }}</button>
        </div>
        <div v-else class="match-panel multiplayer-card">
          <p class="eyebrow">{{ t("multiplayer.createDuel") }}</p>
          <h3>{{ t("multiplayer.duelTitle") }}</h3>
          <p class="card-copy">{{ t("multiplayer.duelDetail") }}</p>
          <button class="button button-primary" type="button" :disabled="loading" @click="createDuelAction">{{ t("multiplayer.create") }}</button>
        </div>
        <div class="match-panel multiplayer-card">
          <p class="eyebrow">{{ t("multiplayer.joinDuel") }}</p>
          <h3>{{ t("multiplayer.duelJoinTitle") }}</h3>
          <input v-model="duelIdInput" class="wide-input" :placeholder="t('multiplayer.duelId')" :aria-label="t('multiplayer.duelId')" />
          <button class="button button-quiet" type="button" :disabled="loading || !session.user || !duelIdInput" @click="joinDuelAction">{{ t("multiplayer.join") }}</button>
        </div>
      </div>
      <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    </div>

    <div v-else class="multiplayer-game">
      <div class="multiplayer-rail">
        <span>{{ kind === 'room' ? t("multiplayer.room") : t("multiplayer.duel") }} <strong>{{ activeMatch?.room_code || activeMatch?.id }}</strong></span>
        <span>{{ activeMatch?.participants.length || 0 }} / {{ activeMatch?.max_players || 2 }} {{ t("multiplayer.players") }}</span>
        <span>{{ t("multiplayer.score") }} {{ score }}</span>
        <span v-if="currentRound" class="practice-timer" role="timer" aria-live="polite" :class="{ urgent: secondsRemaining <= 10 }">{{ secondsRemaining }}{{ t("common.secondsShort") }}</span>
      </div>

      <div v-if="activeMatch?.status === 'waiting'" class="multiplayer-lobby">
        <p class="eyebrow">{{ t("multiplayer.lobby") }}</p>
        <h2>{{ t("multiplayer.waitingTitle") }}</h2>
        <p>{{ t("multiplayer.shareCode") }} <strong class="room-code">{{ activeMatch.room_code }}</strong></p>
        <div class="participant-list">
          <div v-for="participant in activeMatch.participants" :key="participant.id" class="participant-row"><span>{{ participant.display_name }}</span><span>{{ participant.connected ? t("home.connected") : t("home.disconnected") }}</span></div>
        </div>
        <button v-if="kind === 'room' && isOwner" class="button button-primary" type="button" :disabled="loading || activeMatch.participants.length < 2" @click="startRoomAction">{{ t("multiplayer.startRoom") }}</button>
      </div>

      <div v-else-if="!currentRound && activeMatch?.status === 'live'" class="multiplayer-lobby">
        <p class="eyebrow">{{ t("multiplayer.waiting") }}</p>
        <h2>{{ t("multiplayer.waitingAnswer") }}</h2>
        <div class="participant-list"><div v-for="participant in activeMatch.participants" :key="participant.id" class="participant-row"><span>{{ participant.display_name }}</span><span>{{ participant.score }}</span></div></div>
      </div>

      <div v-else-if="activeMatch?.status === 'finished' || activeMatch?.status === 'forfeit'" class="multiplayer-lobby">
        <p class="eyebrow">{{ t("multiplayer.complete") }}</p>
        <h2>{{ t("multiplayer.finalTitle") }}</h2>
        <div class="participant-list"><div v-for="participant in activeMatch.participants" :key="participant.id" class="participant-row"><span>{{ participant.display_name }}</span><span>{{ participant.score }}</span></div></div>
      </div>

      <div v-else-if="currentRound" class="multiplayer-play">
        <p class="eyebrow">{{ activeMode ? modeTitle(activeMode) : currentRound.mode }}</p>
        <h2>{{ currentRound.prompt }}</h2>
        <div class="practice-question-card">
          <div v-if="currentRound.mode === 'hangman'" class="mode-play-area"><div class="hangman-pattern">{{ String(roundData.pattern ?? '') }}</div><div class="answer-row"><input v-model="letterInput" maxlength="1" :placeholder="t('practice.letterPlaceholder')" @keyup.enter="submitLetter" /><button class="button button-primary" type="button" :disabled="submitting || !letterInput" @click="submitLetter">{{ t("practice.tryLetter") }}</button></div></div>
          <div v-else-if="currentRound.mode === 'career_path'" class="mode-play-area"><div class="entry-list"><span v-for="entry in displayEntries" :key="entry" class="entry-chip">{{ entry }}</span></div><div class="answer-row"><input v-model="textInput" :placeholder="t('practice.playerPlaceholder')" @keyup.enter="submitText" /><button class="button button-primary" type="button" :disabled="submitting || !textInput" @click="submitText">{{ t("practice.submit") }}</button></div></div>
          <div v-else-if="currentRound.mode === 'timed_trivia'" class="mode-play-area"><div class="choice-grid"><button v-for="(choice, index) in currentRound.choices" :key="choice" class="choice-button" type="button" :disabled="submitting" @click="submitChoice(index)"><span>{{ String.fromCharCode(65 + index) }}</span>{{ choice }}</button></div></div>
          <div v-else-if="currentRound.mode === 'historical_score'" class="mode-play-area"><div class="score-inputs"><label><span>{{ localized(roundData.home_team) }}</span><input v-model.number="homeScore" min="0" type="number" /></label><span class="score-separator">—</span><label><span>{{ localized(roundData.away_team) }}</span><input v-model.number="awayScore" min="0" type="number" /></label></div><button class="button button-primary" type="button" :disabled="submitting || homeScore === null || awayScore === null" @click="submitScore">{{ t("practice.submitScore") }}</button></div>
          <div v-else class="mode-play-area"><div class="lineup-slots"><span v-for="slot in displaySlots" :key="slot" class="entry-chip">{{ slot }}</span></div><div class="answer-row"><input v-model="textInput" :placeholder="t('practice.playerPlaceholder')" @keyup.enter="submitText" /><button class="button button-primary" type="button" :disabled="submitting || !textInput" @click="submitText">{{ t("practice.submit") }}</button></div></div>
        </div>
      </div>
      <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  fetchLeaderboard,
  fetchRatingStats,
  leaveMatchmaking,
  matchmakingStatus,
  queueMatchmaking,
  submitLiveAnswer,
} from "../lib/api";
import { useSessionStore } from "../stores/session";
import type {
  Language,
  LeaderboardResponse,
  Match,
  MatchmakingResponse,
  ModeDefinition,
  MultiplayerAnswerResponse,
  PracticeMode,
  PracticeRound,
  RatingStats,
} from "../types";

const props = defineProps<{ language: Language; modes: ModeDefinition[] }>();
const emit = defineEmits<{ back: [] }>();
const { t } = useI18n();
const session = useSessionStore();

const activeMatch = ref<Match | null>(null);
const participantId = ref<string | null>(null);
const currentRound = ref<PracticeRound | null>(null);
const queueState = ref<MatchmakingResponse["status"]>("idle");
const queuePosition = ref<number | null>(null);
const stats = ref<RatingStats | null>(null);
const leaderboard = ref<LeaderboardResponse | null>(null);
const loading = ref(false);
const submitting = ref(false);
const error = ref("");
const notice = ref("");
const email = ref("");
const password = ref("");
const textInput = ref("");
const letterInput = ref("");
const homeScore = ref<number | null>(null);
const awayScore = ref<number | null>(null);
const now = ref(Date.now());
const socketStatus = ref<"disconnected" | "connecting" | "connected">("disconnected");
const lastResult = ref("");
let socket: WebSocket | null = null;
let queuePoller: ReturnType<typeof window.setInterval> | null = null;
let timer: ReturnType<typeof window.setInterval> | null = null;

const roundData = computed(() => currentRound.value?.data ?? {});
const secondsRemaining = computed(() => currentRound.value ? Math.max(0, Math.ceil((new Date(currentRound.value.deadline).getTime() - now.value) / 1000)) : 0);
const activeMode = computed(() => props.modes.find((mode) => mode.id === currentRound.value?.mode));
const score = computed(() => activeMatch.value?.participants.find((participant) => participant.id === participantId.value)?.score ?? 0);
const ratingDelta = computed(() => {
  const deltas = activeMatch.value?.result?.rating_deltas;
  if (!deltas || typeof deltas !== "object" || !participantId.value) return null;
  const value = (deltas as Record<string, unknown>)[participantId.value];
  return typeof value === "number" ? value : null;
});

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

function resetAnswerFields() {
  textInput.value = "";
  letterInput.value = "";
  homeScore.value = null;
  awayScore.value = null;
}

function applyQueueResponse(response: MatchmakingResponse) {
  queueState.value = response.status;
  queuePosition.value = response.position ?? null;
  if (response.status === "matched" && response.match && response.participant_id) {
    activeMatch.value = response.match;
    participantId.value = response.participant_id;
    currentRound.value = response.round ?? null;
    stopQueuePolling();
    connectRealtime();
  }
}

async function loadRankedData() {
  if (!session.user) return;
  try {
    [stats.value, leaderboard.value] = await Promise.all([fetchRatingStats(), fetchLeaderboard("global")]);
  } catch {
    error.value = t("ranked.dataError");
  }
}

async function signIn() {
  loading.value = true;
  error.value = "";
  try {
    await session.signIn(email.value, password.value);
    await loadRankedData();
  } catch {
    error.value = t("ranked.loginError");
  } finally {
    loading.value = false;
  }
}

async function enterQueue() {
  if (!session.user) return;
  loading.value = true;
  error.value = "";
  notice.value = "";
  try {
    applyQueueResponse(await queueMatchmaking(props.language));
    if (queueState.value === "queued") {
      notice.value = t("ranked.queuedNotice");
      startQueuePolling();
    }
  } catch {
    error.value = t("ranked.queueError");
  } finally {
    loading.value = false;
  }
}

async function cancelQueue() {
  loading.value = true;
  try {
    await leaveMatchmaking(props.language);
    queueState.value = "idle";
    queuePosition.value = null;
    notice.value = "";
    stopQueuePolling();
  } catch {
    error.value = t("ranked.queueError");
  } finally {
    loading.value = false;
  }
}

function startQueuePolling() {
  stopQueuePolling();
  queuePoller = window.setInterval(async () => {
    if (queueState.value !== "queued") return;
    try {
      applyQueueResponse(await matchmakingStatus(props.language));
    } catch {
      // Keep the queue visible while a transient request fails.
    }
  }, 2500);
}

function stopQueuePolling() {
  if (queuePoller) window.clearInterval(queuePoller);
  queuePoller = null;
}

function connectRealtime() {
  if (!activeMatch.value || !session.accessToken) return;
  socket?.close();
  socketStatus.value = "connecting";
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/v1/match/${activeMatch.value.id}/?token=${encodeURIComponent(session.accessToken)}`);
  socket.addEventListener("open", () => { socketStatus.value = "connected"; });
  socket.addEventListener("close", () => { socketStatus.value = "disconnected"; });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data) as Partial<PracticeRound> & {
      type?: string;
      status?: string;
      participants?: Match["participants"];
      result?: Match["result"] | MultiplayerAnswerResponse["result"];
      next_round?: PracticeRound | null;
      phase?: MultiplayerAnswerResponse["phase"];
      answer_result?: MultiplayerAnswerResponse["result"];
      points?: number;
    };
    if (message.type === "match.state" && activeMatch.value) {
      const matchResult = message.result && typeof message.result === "object" ? message.result : activeMatch.value.result;
      activeMatch.value = { ...activeMatch.value, status: message.status ?? activeMatch.value.status, participants: message.participants ?? activeMatch.value.participants, result: matchResult };
    }
    if (message.type === "round.start" && message.id && message.mode && message.deadline) {
      currentRound.value = {
        id: message.id,
        order: message.order ?? 0,
        mode: message.mode,
        status: "active",
        deadline: message.deadline,
        server_now: message.server_now ?? new Date().toISOString(),
        prompt: message.prompt ?? "",
        choices: message.choices ?? [],
        hints: message.hints ?? [],
        data: message.data ?? {},
      };
    }
    if (message.type === "answer.result") {
      lastResult.value = typeof message.result === "string" ? message.result : "";
      currentRound.value = message.next_round ?? null;
      submitting.value = false;
      resetAnswerFields();
    }
    if (message.type === "error") {
      submitting.value = false;
      error.value = t("ranked.answerError");
    }
  });
}

async function submitAnswer(answer: Record<string, unknown>) {
  if (!activeMatch.value || !currentRound.value || submitting.value || !participantId.value) return;
  submitting.value = true;
  error.value = "";
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "answer.submit", round_id: currentRound.value.id, answer }));
    return;
  }
  try {
    const response = await submitLiveAnswer(activeMatch.value.id, currentRound.value.id, answer);
    handleAnswerResponse(response);
  } catch {
    error.value = t("ranked.answerError");
    submitting.value = false;
  }
}

function handleAnswerResponse(response: MultiplayerAnswerResponse) {
  activeMatch.value = response.match;
  currentRound.value = response.next_round;
  lastResult.value = response.result;
  submitting.value = false;
  resetAnswerFields();
}

function submitLetter() { if (letterInput.value.trim()) void submitAnswer({ letter: letterInput.value.trim() }); }
function submitText() { if (textInput.value.trim()) void submitAnswer({ text: textInput.value.trim() }); }
function submitScore() { if (homeScore.value !== null && awayScore.value !== null) void submitAnswer({ home: homeScore.value, away: awayScore.value }); }
function submitChoice(index: number) { void submitAnswer({ choice_index: index }); }

function backToHome() {
  socket?.close();
  stopQueuePolling();
  if (queueState.value === "queued") void leaveMatchmaking(props.language);
  if (timer) window.clearInterval(timer);
  emit("back");
}

onMounted(() => {
  session.restore();
  void loadRankedData();
  timer = window.setInterval(() => { now.value = Date.now(); }, 250);
});

onBeforeUnmount(() => {
  socket?.close();
  stopQueuePolling();
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <section class="ranked-shell">
    <div class="practice-toolbar">
      <button class="text-button" type="button" @click="backToHome">← {{ t("ranked.back") }}</button>
      <span>{{ t("ranked.eyebrow") }}</span>
    </div>

    <div v-if="!session.user && !activeMatch" class="ranked-setup">
      <div class="section-heading practice-heading">
        <div><p class="eyebrow">04 / {{ t("ranked.eyebrow") }}</p><h2>{{ t("ranked.title") }}</h2></div>
        <p>{{ t("ranked.description") }}</p>
      </div>
      <div class="match-panel ranked-login-card">
        <p class="eyebrow">{{ t("ranked.accountRequired") }}</p>
        <h3>{{ t("ranked.loginTitle") }}</h3>
        <input v-model="email" class="wide-input" type="email" :placeholder="t('multiplayer.email')" :aria-label="t('multiplayer.email')" />
        <input v-model="password" class="wide-input" type="password" :placeholder="t('multiplayer.password')" :aria-label="t('multiplayer.password')" />
        <button class="button button-primary" type="button" :disabled="loading || !email || !password" @click="signIn">{{ t("multiplayer.login") }}</button>
      </div>
      <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    </div>

    <div v-else-if="!activeMatch" class="ranked-setup">
      <div class="section-heading practice-heading">
        <div><p class="eyebrow">04 / {{ t("ranked.eyebrow") }}</p><h2>{{ t("ranked.title") }}</h2></div>
        <p>{{ t("ranked.description") }}</p>
      </div>

      <div class="ranked-overview">
        <div class="match-panel ranked-stat-card"><span>{{ t("ranked.rating") }}</span><strong>{{ stats?.rating ?? 1000 }}</strong><small>{{ stats?.in_placement ? t("ranked.placement") : t("ranked.stable") }}</small></div>
        <div class="match-panel ranked-stat-card"><span>{{ t("ranked.globalRank") }}</span><strong>{{ stats?.global_rank ? `#${stats.global_rank}` : "—" }}</strong><small>{{ t("ranked.leaderboard") }}</small></div>
        <div class="match-panel ranked-stat-card"><span>{{ t("ranked.record") }}</span><strong>{{ stats?.wins ?? 0 }}—{{ stats?.draws ?? 0 }}—{{ stats?.losses ?? 0 }}</strong><small>{{ t("ranked.wdl") }}</small></div>
      </div>

      <div class="ranked-queue-panel match-panel">
        <div>
          <p class="eyebrow">{{ t("ranked.queueLabel") }}</p>
          <h3>{{ queueState === "queued" ? t("ranked.searching") : t("ranked.queueTitle") }}</h3>
          <p class="card-copy">{{ queueState === "queued" ? t("ranked.searchingDetail") : t("ranked.queueDetail") }}</p>
        </div>
        <div class="ranked-queue-action">
          <strong v-if="queueState === 'queued'">{{ t("ranked.position", { position: queuePosition ?? 1 }) }}</strong>
          <button v-if="queueState === 'queued'" class="button button-quiet" type="button" :disabled="loading" @click="cancelQueue">{{ t("ranked.cancel") }}</button>
          <button v-else class="button button-primary" type="button" :disabled="loading" @click="enterQueue">{{ t("ranked.enterQueue") }}</button>
        </div>
      </div>

      <div class="ranked-board">
        <div class="section-heading"><div><p class="eyebrow">{{ t("ranked.boardEyebrow") }}</p><h3>{{ t("ranked.boardTitle") }}</h3></div><span class="ranked-season">{{ leaderboard?.season ?? new Date().getFullYear() }}</span></div>
        <div class="ranked-table" role="table" :aria-label="t('ranked.boardTitle')">
          <div class="ranked-table-row ranked-table-head" role="row"><span>#</span><span>{{ t("ranked.player") }}</span><span>{{ t("ranked.rating") }}</span><span>{{ t("ranked.matches") }}</span></div>
          <div v-for="entry in leaderboard?.entries ?? []" :key="entry.user_id" class="ranked-table-row" role="row"><span>{{ entry.rank }}</span><span>{{ entry.display_name }}</span><strong>{{ entry.rating }}</strong><span>{{ entry.matches_played }}</span></div>
          <div v-if="!leaderboard?.entries.length" class="ranked-empty">{{ t("ranked.emptyBoard") }}</div>
        </div>
      </div>
      <p v-if="notice" class="notice" role="status">{{ notice }}</p>
      <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    </div>

    <div v-else class="ranked-game">
      <div class="multiplayer-rail ranked-rail"><span>{{ t("ranked.match") }} <strong>{{ activeMatch.id }}</strong></span><span>{{ activeMatch.participants.length }} / 2 {{ t("multiplayer.players") }}</span><span>{{ t("multiplayer.score") }} {{ score }}</span><span>{{ socketStatus === "connected" ? t("home.connected") : t("home.disconnected") }}</span><span v-if="currentRound" class="practice-timer" :class="{ urgent: secondsRemaining <= 10 }">{{ secondsRemaining }}{{ t("common.secondsShort") }}</span></div>

      <div v-if="activeMatch.status === 'finished' || activeMatch.status === 'forfeit'" class="multiplayer-lobby">
        <p class="eyebrow">{{ t("ranked.complete") }}</p>
        <h2>{{ t("ranked.finalTitle") }}</h2>
        <p v-if="ratingDelta !== null" class="ranked-delta" :class="{ negative: ratingDelta < 0 }">{{ ratingDelta >= 0 ? "+" : "" }}{{ ratingDelta }} {{ t("ranked.ratingChange") }}</p>
        <div class="participant-list"><div v-for="participant in activeMatch.participants" :key="participant.id" class="participant-row"><span>{{ participant.display_name }}</span><span>{{ participant.score }}</span></div></div>
        <button class="button button-primary" type="button" @click="activeMatch = null; currentRound = null; queueState = 'idle'; void loadRankedData()">{{ t("ranked.backToBoard") }}</button>
      </div>

      <div v-else-if="!currentRound" class="multiplayer-lobby">
        <p class="eyebrow">{{ t("ranked.waiting") }}</p>
        <h2>{{ t("ranked.waitingTitle") }}</h2>
        <div class="participant-list"><div v-for="participant in activeMatch.participants" :key="participant.id" class="participant-row"><span>{{ participant.display_name }}</span><span>{{ participant.score }}</span></div></div>
      </div>

      <div v-else class="multiplayer-play">
        <p class="eyebrow">{{ activeMode ? modeTitle(activeMode) : currentRound.mode }}</p>
        <h2>{{ currentRound.prompt }}</h2>
        <div class="practice-question-card">
          <div v-if="currentRound.mode === 'hangman'" class="mode-play-area"><div class="hangman-pattern">{{ String(roundData.pattern ?? '') }}</div><div class="answer-row"><input v-model="letterInput" maxlength="1" :placeholder="t('practice.letterPlaceholder')" @keyup.enter="submitLetter" /><button class="button button-primary" type="button" :disabled="submitting || !letterInput" @click="submitLetter">{{ t("practice.tryLetter") }}</button></div></div>
          <div v-else-if="currentRound.mode === 'career_path'" class="mode-play-area"><div class="entry-list"><span v-for="entry in displayList('entries')" :key="entry" class="entry-chip">{{ entry }}</span></div><div class="answer-row"><input v-model="textInput" :placeholder="t('practice.playerPlaceholder')" @keyup.enter="submitText" /><button class="button button-primary" type="button" :disabled="submitting || !textInput" @click="submitText">{{ t("practice.submit") }}</button></div></div>
          <div v-else-if="currentRound.mode === 'timed_trivia'" class="mode-play-area"><div class="choice-grid"><button v-for="(choice, index) in currentRound.choices" :key="choice" class="choice-button" type="button" :disabled="submitting" @click="submitChoice(index)"><span>{{ String.fromCharCode(65 + index) }}</span>{{ choice }}</button></div></div>
          <div v-else-if="currentRound.mode === 'historical_score'" class="mode-play-area"><div class="score-inputs"><label><span>{{ localized(roundData.home_team) }}</span><input v-model.number="homeScore" min="0" type="number" /></label><span class="score-separator">—</span><label><span>{{ localized(roundData.away_team) }}</span><input v-model.number="awayScore" min="0" type="number" /></label></div><button class="button button-primary" type="button" :disabled="submitting || homeScore === null || awayScore === null" @click="submitScore">{{ t("practice.submitScore") }}</button></div>
          <div v-else class="mode-play-area"><div class="lineup-slots"><span v-for="slot in displayList('slots')" :key="slot" class="entry-chip">{{ slot }}</span></div><div class="answer-row"><input v-model="textInput" :placeholder="t('practice.playerPlaceholder')" @keyup.enter="submitText" /><button class="button button-primary" type="button" :disabled="submitting || !textInput" @click="submitText">{{ t("practice.submit") }}</button></div></div>
        </div>
        <p v-if="lastResult" class="practice-feedback" :class="lastResult === 'correct' ? 'feedback-correct' : 'feedback-muted'">{{ t(`practice.result.${lastResult}`) }}</p>
        <p v-if="error" class="error-message" role="alert">{{ error }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { createLiveMatch, fetchModes } from "./lib/api";
import { useSessionStore } from "./stores/session";
import type { Language, Match, ModeDefinition } from "./types";

const { t, locale } = useI18n();
const session = useSessionStore();
const modes = ref<ModeDefinition[]>([]);
const match = ref<Match | null>(null);
const loading = ref(true);
const error = ref("");
const notice = ref("");
const socketStatus = ref<"disconnected" | "connecting" | "connected">("disconnected");
let socket: WebSocket | null = null;

const currentLanguage = computed(() => locale.value as Language);

function toggleLanguage(language: Language) {
  locale.value = language;
}

function modeTitle(mode: ModeDefinition) {
  return t(mode.title_key);
}

function modeDescription(mode: ModeDefinition) {
  return t(mode.description_key);
}

async function startGuest() {
  error.value = "";
  try {
    await session.ensureGuest();
    notice.value = t("status.guestReady");
  } catch {
    error.value = t("status.apiUnavailable");
  }
}

async function startMatch() {
  error.value = "";
  try {
    await session.ensureGuest();
    match.value = await createLiveMatch(currentLanguage.value);
    notice.value = t("status.matchCreated");
    connectSocket();
  } catch {
    error.value = t("status.failed");
  }
}

function connectSocket() {
  if (!match.value || !session.guest?.guest_token) return;
  socket?.close();
  socketStatus.value = "connecting";
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/v1/match/${match.value.id}/?guest_token=${encodeURIComponent(session.guest.guest_token)}`);
  socket.addEventListener("open", () => {
    socketStatus.value = "connected";
  });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data) as Partial<{ type: string; status: string; participants: Match["participants"] }>;
    if (message.type === "match.state" && message.participants) {
      match.value = { ...match.value!, status: message.status ?? match.value!.status, participants: message.participants };
    }
  });
  socket.addEventListener("close", () => {
    socketStatus.value = "disconnected";
  });
}

onMounted(async () => {
  session.restore();
  try {
    modes.value = await fetchModes();
  } catch {
    error.value = t("status.apiUnavailable");
  } finally {
    loading.value = false;
  }
});

onBeforeUnmount(() => socket?.close());
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <a class="brand" href="/" aria-label="Goalium Rivals">Goalium<span>Rivals</span></a>
      <nav class="topnav" :aria-label="t('navigation.primary')">
        <a href="#modes">{{ t("navigation.modes") }}</a>
        <a href="#live">{{ t("navigation.live") }}</a>
        <a href="#session">{{ t("navigation.account") }}</a>
      </nav>
      <div class="language-switcher" :aria-label="t('common.language')">
        <button :class="{ active: locale === 'tr' }" type="button" @click="toggleLanguage('tr')">{{ t("common.tr") }}</button>
        <button :class="{ active: locale === 'en' }" type="button" @click="toggleLanguage('en')">{{ t("common.en") }}</button>
      </div>
    </header>

    <section class="hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">{{ t("home.eyebrow") }}</p>
        <h1>{{ t("home.title") }}</h1>
        <p class="hero-description">{{ t("home.description") }}</p>
        <div class="hero-actions">
          <button class="button button-primary" type="button" :disabled="session.loading" @click="startMatch">{{ t("home.createMatch") }}</button>
          <button class="button button-quiet" type="button" :disabled="session.loading" @click="startGuest">{{ t("home.createGuest") }}</button>
        </div>
        <p v-if="notice" class="notice" role="status">{{ notice }}</p>
        <p v-if="error" class="error-message" role="alert">{{ error }}</p>
      </div>
      <aside id="live" class="match-panel" aria-live="polite">
        <div class="panel-heading">
          <span>{{ t("home.matchReady") }}</span>
          <span class="status-dot" :class="socketStatus"></span>
        </div>
        <div v-if="match" class="match-details">
          <div class="match-state-label">{{ match.status === "waiting" ? t("home.waiting") : t("common.active") }}</div>
          <dl>
            <div><dt>{{ t("home.matchId") }}</dt><dd>{{ match.id }}</dd></div>
            <div><dt>{{ t("home.participantCount") }}</dt><dd>{{ match.participants.length }} / 2</dd></div>
            <div><dt>{{ t("home.connection") }}</dt><dd>{{ socketStatus === "connected" ? t("home.connected") : t("home.disconnected") }}</dd></div>
          </dl>
          <div class="participants">
            <span v-for="participant in match.participants" :key="participant.id" class="participant-row">
              <span>{{ participant.display_name }}</span>
              <span>{{ participant.connected ? t("home.connected") : t("home.disconnected") }}</span>
            </span>
          </div>
        </div>
        <div v-else class="empty-panel">
          <strong>{{ t("home.noMatch") }}</strong>
          <span>{{ t("home.noMatchDetail") }}</span>
        </div>
      </aside>
    </section>

    <section id="modes" class="modes-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">01 / {{ t("navigation.modes") }}</p>
          <h2>{{ t("modes.sectionTitle") }}</h2>
        </div>
        <p>{{ t("modes.sectionDescription") }}</p>
      </div>
      <div v-if="loading" class="loading-row">{{ t("status.loading") }}</div>
      <div v-else class="mode-grid">
        <article v-for="(mode, index) in modes" :key="mode.id" class="mode-card">
          <div class="mode-index">0{{ index + 1 }}</div>
          <div class="mode-body">
            <h3>{{ modeTitle(mode) }}</h3>
            <p>{{ modeDescription(mode) }}</p>
          </div>
          <div class="mode-duration">{{ mode.duration_seconds }} {{ t("common.seconds") }}</div>
        </article>
      </div>
    </section>

    <footer id="session" class="footer-grid">
      <span>Goalium Rivals</span>
      <span>{{ t("common.phaseOne") }}</span>
    </footer>
  </main>
</template>

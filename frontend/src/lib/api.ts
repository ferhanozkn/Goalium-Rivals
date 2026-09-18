import axios from "axios";

import type {
  GuestSession,
  AuthResponse,
  Language,
  Match,
  ModeDefinition,
  PracticeAnswerResponse,
  PracticeMode,
  PracticeSessionResponse,
  MultiplayerAnswerResponse,
  MultiplayerResponse,
} from "../types";

const api = axios.create({ baseURL: "/api/v1" });

export function setGuestToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["X-Guest-Token"] = token;
  } else {
    delete api.defaults.headers.common["X-Guest-Token"];
  }
}

export function setAccessToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export async function fetchModes(): Promise<ModeDefinition[]> {
  const response = await api.get<ModeDefinition[]>("/modes");
  return response.data;
}

export async function createGuestSession(displayName = ""): Promise<GuestSession> {
  const response = await api.post<GuestSession>("/guest/session", { display_name: displayName });
  setGuestToken(response.data.guest_token);
  return response.data;
}

export async function createLiveMatch(language: Language): Promise<Match> {
  const response = await api.post<Match>("/matches", {
    language,
    is_mixed: true,
    origin: "invite",
  });
  return response.data;
}

export async function fetchMatch(matchId: string): Promise<Match> {
  const response = await api.get<Match>(`/matches/${matchId}`);
  return response.data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await api.post<AuthResponse>("/auth/login", { email, password });
  setAccessToken(response.data.tokens.access);
  return response.data;
}

export async function createRoom(
  language: Language,
  options: { is_mixed: boolean; mode?: PracticeMode; round_count?: number; duration_multiplier?: number },
): Promise<MultiplayerResponse> {
  const response = await api.post<MultiplayerResponse>("/rooms", { language, ...options });
  return response.data;
}

export async function fetchRoom(roomCode: string): Promise<MultiplayerResponse> {
  const response = await api.get<MultiplayerResponse>(`/rooms/${roomCode}`);
  return response.data;
}

export async function joinRoom(roomCode: string): Promise<MultiplayerResponse> {
  const response = await api.post<MultiplayerResponse>(`/rooms/${roomCode}/join`, {});
  return response.data;
}

export async function startRoom(roomCode: string): Promise<MultiplayerResponse> {
  const response = await api.post<MultiplayerResponse>(`/rooms/${roomCode}/start`, {});
  return response.data;
}

export async function submitRoomAnswer(roomCode: string, roundId: string, answer: Record<string, unknown>): Promise<MultiplayerAnswerResponse> {
  const response = await api.post<MultiplayerAnswerResponse>(`/rooms/${roomCode}/answers`, { round_id: roundId, answer });
  return response.data;
}

export async function createDuel(language: Language, modes: PracticeMode[]): Promise<MultiplayerResponse> {
  const response = await api.post<MultiplayerResponse>("/duels", { language, modes });
  return response.data;
}

export async function joinDuel(duelId: string): Promise<MultiplayerResponse> {
  const response = await api.post<MultiplayerResponse>(`/duels/${duelId}/join`, {});
  return response.data;
}

export async function fetchDuel(duelId: string): Promise<MultiplayerResponse> {
  const response = await api.get<MultiplayerResponse>(`/duels/${duelId}`);
  return response.data;
}

export async function submitDuelAnswer(duelId: string, roundId: string, answer: Record<string, unknown>): Promise<MultiplayerAnswerResponse> {
  const response = await api.post<MultiplayerAnswerResponse>(`/duels/${duelId}/play`, { round_id: roundId, answer });
  return response.data;
}

export async function createPracticeSession(language: Language, modes: PracticeMode[]): Promise<PracticeSessionResponse> {
  const response = await api.post<PracticeSessionResponse>("/practice/sessions", { language, modes });
  return response.data;
}

export async function submitPracticeAnswer(
  sessionId: string,
  roundId: string,
  answer: Record<string, unknown>,
): Promise<PracticeAnswerResponse> {
  const response = await api.post<PracticeAnswerResponse>(`/practice/sessions/${sessionId}/answers`, {
    round_id: roundId,
    answer,
  });
  return response.data;
}

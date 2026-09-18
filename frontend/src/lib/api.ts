import axios from "axios";

import type { GuestSession, Language, Match, ModeDefinition } from "../types";

const api = axios.create({ baseURL: "/api/v1" });

export function setGuestToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["X-Guest-Token"] = token;
  } else {
    delete api.defaults.headers.common["X-Guest-Token"];
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

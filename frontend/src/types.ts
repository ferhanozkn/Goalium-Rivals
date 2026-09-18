export type Language = "tr" | "en";

export interface ModeDefinition {
  id: string;
  title_key: string;
  description_key: string;
  duration_seconds: number;
}

export interface GuestSession {
  guest_token: string;
  guest_session_id: string;
  display_name: string;
  expires_at: string;
}

export interface Participant {
  id: string;
  display_name: string;
  score: number;
  connected: boolean;
}

export interface Match {
  id: string;
  game_session_id: string;
  match_type: string;
  origin: string;
  is_mixed: boolean;
  language: Language;
  status: string;
  ranked_eligible: boolean;
  participants: Participant[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

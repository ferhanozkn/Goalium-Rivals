export type Language = "tr" | "en";
export type PracticeMode = "hangman" | "career_path" | "timed_trivia" | "historical_score" | "missing_lineup";

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

export interface PracticeRound {
  id: string;
  order: number;
  mode: PracticeMode;
  status: "pending" | "active" | "finished" | "timeout";
  deadline: string;
  server_now: string;
  prompt: string;
  choices: string[];
  hints: string[];
  data: Record<string, unknown>;
}

export interface PracticeSessionResponse {
  session: {
    id: string;
    kind: string;
    modes: PracticeMode[];
    language: Language;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    deadline: string | null;
    created_at: string;
  };
  actor_type: "guest" | "user";
  participant_id: string;
  round: PracticeRound;
}

export interface PracticeAnswerResponse {
  round: PracticeRound;
  result: "correct" | "wrong" | "timeout" | "skipped" | "active";
  points: number;
  score: number;
  next_round: PracticeRound | null;
}

import { defineStore } from "pinia";

import { createGuestSession, login, setAccessToken, setGuestToken } from "../lib/api";
import type { AuthUser, GuestSession } from "../types";

const guestStorageKey = "goalium-rivals.guest-session";
const authStorageKey = "goalium-rivals.auth-session";

export const useSessionStore = defineStore("session", {
  state: () => ({
    guest: null as GuestSession | null,
    user: null as AuthUser | null,
    accessToken: null as string | null,
    loading: false,
  }),
  actions: {
    restore() {
      const raw = localStorage.getItem(guestStorageKey);
      if (raw) {
        try {
          this.guest = JSON.parse(raw) as GuestSession;
          setGuestToken(this.guest.guest_token);
        } catch {
          localStorage.removeItem(guestStorageKey);
        }
      }
      const authRaw = localStorage.getItem(authStorageKey);
      if (authRaw) {
        try {
          const auth = JSON.parse(authRaw) as { user: AuthUser; access: string };
          this.user = auth.user;
          this.accessToken = auth.access;
          setAccessToken(auth.access);
        } catch {
          localStorage.removeItem(authStorageKey);
        }
      }
    },
    async ensureGuest() {
      if (this.guest && new Date(this.guest.expires_at) > new Date()) return this.guest;
      this.loading = true;
      try {
        this.guest = await createGuestSession();
        localStorage.setItem(guestStorageKey, JSON.stringify(this.guest));
        return this.guest;
      } finally {
        this.loading = false;
      }
    },
    async signIn(email: string, password: string) {
      const response = await login(email, password);
      this.user = response.user;
      this.accessToken = response.tokens.access;
      localStorage.setItem(authStorageKey, JSON.stringify({ user: response.user, access: response.tokens.access }));
      return response.user;
    },
  },
});

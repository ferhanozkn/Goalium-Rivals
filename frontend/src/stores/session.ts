import { defineStore } from "pinia";

import { createGuestSession, setGuestToken } from "../lib/api";
import type { GuestSession } from "../types";

const guestStorageKey = "goalium-rivals.guest-session";

export const useSessionStore = defineStore("session", {
  state: () => ({
    guest: null as GuestSession | null,
    loading: false,
  }),
  actions: {
    restore() {
      const raw = localStorage.getItem(guestStorageKey);
      if (!raw) return;
      try {
        this.guest = JSON.parse(raw) as GuestSession;
        setGuestToken(this.guest.guest_token);
      } catch {
        localStorage.removeItem(guestStorageKey);
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
  },
});

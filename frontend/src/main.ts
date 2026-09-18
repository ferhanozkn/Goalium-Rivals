import { createApp } from "vue";
import { createPinia } from "pinia";
import { createI18n } from "vue-i18n";

import App from "./App.vue";
import "./styles.css";
import { messages } from "./i18n";

const i18n = createI18n({
  legacy: false,
  locale: "tr",
  fallbackLocale: "en",
  messages,
});

createApp(App).use(createPinia()).use(i18n).mount("#app");

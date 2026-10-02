import DefaultTheme from "vitepress/theme";
import type { Theme } from "vitepress";
import MarkdownButtons from "./MarkdownButtons.vue";
import "virtual:group-icons.css";
import "./custom.css";

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component("CopyOrDownloadAsMarkdownButtons", MarkdownButtons);
  },
} satisfies Theme;

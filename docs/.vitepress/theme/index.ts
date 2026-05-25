import { h } from "vue";
import DefaultTheme from "vitepress/theme";
import type { Theme } from "vitepress";
import RcBanner from "./RcBanner.vue";
import MarkdownButtons from "./MarkdownButtons.vue";
import "virtual:group-icons.css";
import "./custom.css";

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      "layout-top": () => h(RcBanner),
    });
  },
  enhanceApp({ app }) {
    app.component("CopyOrDownloadAsMarkdownButtons", MarkdownButtons);
  },
} satisfies Theme;

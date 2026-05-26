<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";

const STORAGE_KEY = "sqlalchemy-seedling-rc-banner-dismissed";
const BANNER_HEIGHT = "40px";
const visible = ref(false);

onMounted(() => {
  visible.value = sessionStorage.getItem(STORAGE_KEY) !== "1";
  if (visible.value) {
    document.documentElement.style.setProperty("--vp-layout-top-height", BANNER_HEIGHT);
  }
});

onUnmounted(() => {
  document.documentElement.style.removeProperty("--vp-layout-top-height");
});

function dismiss() {
  sessionStorage.setItem(STORAGE_KEY, "1");
  visible.value = false;
  document.documentElement.style.setProperty("--vp-layout-top-height", "0px");
}
</script>

<template>
  <div v-if="visible" class="rc-banner" role="banner">
    <span class="rc-banner-text">
      <strong>1.0 RC</strong> — feedback wanted. Track it in
      <a
        href="https://github.com/arthurvasconcelos/seedling/issues/1"
        target="_blank"
        rel="noopener noreferrer"
      >issue #1</a>.
      Final 1.0 ships ~2026-06-16.
    </span>
    <button
      class="rc-banner-dismiss"
      type="button"
      aria-label="Dismiss RC notice"
      @click="dismiss"
    >
      ✕
    </button>
  </div>
</template>

<style scoped>
.rc-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: calc(var(--vp-z-index-nav) + 1);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 8px 16px;
  height: 40px;
  background: var(--vp-c-brand-1);
  color: #fff;
  font-size: 13px;
  line-height: 1.4;
}

.rc-banner-text {
  flex: 1;
  text-align: center;
}

.rc-banner-text a {
  color: #fff;
  font-weight: 600;
  text-underline-offset: 2px;
}

.rc-banner-text a:hover {
  opacity: 0.85;
}

.rc-banner-dismiss {
  flex-shrink: 0;
  appearance: none;
  background: transparent;
  border: none;
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 4px;
  opacity: 0.8;
}

.rc-banner-dismiss:hover {
  background: rgb(255 255 255 / 15%);
  opacity: 1;
}

.rc-banner-dismiss:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}
</style>

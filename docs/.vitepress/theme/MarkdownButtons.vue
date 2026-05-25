<template>
	<div class="llm-buttons">
		<div class="llm-buttons-inner">
			<div class="dropdown-container" ref="dropdownContainer">
				<div class="dropdown-trigger">
					<button class="copy-btn" @click="handleCopyAsMarkdown">
						<span v-html="copied ? iconCheck : iconCopy" class="icon" />
						<span class="label">{{ copied ? "Copied" : "Copy Markdown" }}</span>
					</button>
					<span class="divider" />
					<button class="chevron-btn" @click.stop="toggleDropdown">
						<span v-html="iconChevron" class="icon chevron" :class="{ open: isOpen }" />
					</button>
				</div>

				<div v-if="isRendered" ref="dropdownMenu" class="dropdown-menu" :class="{ open: isOpen }">
					<button class="dropdown-item" @click="handleViewAsMarkdown">
						<span v-html="iconMarkdown" class="icon" />
						View as Markdown
						<span v-html="iconExternal" class="icon external" />
					</button>

					<button class="dropdown-item" @click="handleOpenInGitHub">
						<span v-html="iconGitHub" class="icon" />
						Open in GitHub
						<span v-html="iconExternal" class="icon external" />
					</button>

					<button
						v-for="provider in aiProviders"
						:key="provider.name"
						class="dropdown-item"
						@click="handleOpenInAI(provider)"
					>
						<span v-html="resolveProviderIcon(provider)" class="icon" />
						Open in {{ provider.name }}
						<span v-html="iconExternal" class="icon external" />
					</button>
				</div>
			</div>

			<button class="download-btn" title="Download as Markdown" @click="downloadMarkdown">
				<span v-html="downloaded ? iconCheck : iconDownload" class="icon" />
			</button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useData } from "vitepress";
import {
	useCopyOrDownloadAsMarkdownButtons,
	type MarkdownAiProvider,
} from "vitepress-plugin-llms/vitepress-components";
import iconChatGPT from "./icons/chatgpt.svg?raw";
import iconCheck from "./icons/check.svg?raw";
import iconChevron from "./icons/chevron.svg?raw";
import iconClaude from "./icons/claude.svg?raw";
import iconCopy from "./icons/copy.svg?raw";
import iconDownload from "./icons/download.svg?raw";
import iconExternal from "./icons/external.svg?raw";
import iconMarkdown from "./icons/markdown.svg?raw";

const iconGitHub = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/></svg>`;

const { page } = useData();

const isOpen = ref(false);
const isRendered = ref(false);
const dropdownContainer = ref<HTMLElement | undefined>();
const dropdownMenu = ref<HTMLElement | undefined>();

const { aiProviders, copied, copyAsMarkdown, downloadMarkdown, downloaded, openInAI, viewAsMarkdown } =
	useCopyOrDownloadAsMarkdownButtons();

const aiProviderIcons: Record<string, string> = { ChatGPT: iconChatGPT, Claude: iconClaude };

const githubUrl = computed(
	() => `https://github.com/arthurvasconcelos/seedling/blob/main/docs/${page.value.relativePath}`,
);

function resolveProviderIcon(provider: MarkdownAiProvider): string {
	return aiProviderIcons[provider.name] ?? iconExternal;
}

function closeDropdown(): void {
	if (!isOpen.value) {
		isRendered.value = false;
		return;
	}
	isOpen.value = false;
	const el = dropdownMenu.value;
	if (!el) {
		isRendered.value = false;
		return;
	}
	const onEnd = (): void => {
		isRendered.value = false;
		el.removeEventListener("transitionend", onEnd);
	};
	el.addEventListener("transitionend", onEnd);
}

function toggleDropdown(): void {
	if (isOpen.value) {
		closeDropdown();
	} else {
		isRendered.value = true;
		requestAnimationFrame(() => {
			isOpen.value = true;
		});
	}
}

async function handleCopyAsMarkdown(): Promise<void> {
	await copyAsMarkdown();
	closeDropdown();
}

function handleViewAsMarkdown(): void {
	viewAsMarkdown();
	closeDropdown();
}

function handleOpenInGitHub(): void {
	window.open(githubUrl.value, "_blank");
	closeDropdown();
}

function handleOpenInAI(provider: MarkdownAiProvider): void {
	openInAI(provider);
	closeDropdown();
}

function handleClickOutside(event: MouseEvent): void {
	if (dropdownContainer.value && !dropdownContainer.value.contains(event.target as Node)) {
		closeDropdown();
	}
}

onMounted(() => {
	document.addEventListener("click", handleClickOutside);
});
onUnmounted(() => document.removeEventListener("click", handleClickOutside));
</script>

<style scoped>
.llm-buttons {
	line-height: 1;
}

.llm-buttons-inner {
	display: flex;
	gap: 8px;
	position: relative;
}

.dropdown-container {
	position: relative;
}

.dropdown-trigger {
	display: flex;
	align-items: stretch;
	background: transparent;
	border: 1px solid var(--vp-c-divider);
	border-radius: 6px;
	color: var(--vp-c-text-1);
	font-size: 14px;
	overflow: hidden;
}

.copy-btn {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 14px;
	cursor: pointer;
	white-space: nowrap;
	background: transparent;
	border: none;
	color: inherit;
}

.divider {
	width: 1px;
	height: 25px;
	align-self: center;
	background: var(--vp-c-divider);
	opacity: 0.6;
}

.chevron-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 0 10px;
	cursor: pointer;
	background: transparent;
	border: none;
	color: inherit;
}

.dropdown-menu {
	position: absolute;
	top: calc(100% + 4px);
	right: 0;
	min-width: 220px;
	background: var(--vp-c-bg-elv);
	border: 1px solid var(--vp-c-divider);
	border-radius: 8px;
	overflow: hidden;
	z-index: 100;
	box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
	opacity: 0;
	transform: translateY(-6px) scale(0.96);
	pointer-events: none;
	transform-origin: top right;
	transition:
		opacity 0.18s cubic-bezier(0.4, 0, 0.2, 1),
		transform 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.dropdown-menu.open {
	opacity: 1;
	transform: translateY(0) scale(1);
	pointer-events: auto;
}

.dropdown-item {
	position: relative;
	width: 100%;
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 16px;
	background: transparent;
	border: none;
	color: var(--vp-c-text-1);
	font-size: 14px;
	cursor: pointer;
	text-align: left;
	transition: padding-left 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.dropdown-item::before {
	content: "";
	position: absolute;
	left: 0;
	top: 0;
	width: 0;
	height: 100%;
	background: var(--vp-c-brand-1);
	transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.dropdown-item:hover {
	padding-left: 20px;
}

.dropdown-item:hover::before {
	width: 3px;
}

.dropdown-item .icon.external {
	margin-left: auto;
	opacity: 0.6;
	transition: opacity 0.2s, transform 0.2s;
}

.dropdown-item:hover .icon.external {
	opacity: 1;
	transform: translateX(2px);
}

.download-btn {
	display: flex;
	align-items: center;
	padding: 6px 10px;
	background: transparent;
	border: 1px solid var(--vp-c-divider);
	border-radius: 6px;
	color: var(--vp-c-text-1);
	cursor: pointer;
	transition:
		border-color 0.25s,
		transform 0.25s,
		box-shadow 0.25s,
		background 0.25s;
}

.icon {
	width: 16px;
	height: 16px;
	flex-shrink: 0;
}

.chevron {
	transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.chevron.open {
	transform: rotate(180deg);
}

.dropdown-trigger,
.download-btn {
	transition:
		border-color 0.25s,
		transform 0.25s,
		box-shadow 0.25s;
}

.dropdown-trigger:hover,
.download-btn:hover {
	border-color: var(--vp-c-brand-1);
	transform: translateY(-1px);
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.copy-btn:hover,
.chevron-btn:hover,
.download-btn:hover {
	background: var(--vp-c-bg-soft);
}
</style>

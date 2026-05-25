import { readFileSync } from 'node:fs'
import { defineConfig } from 'vitepress'
import llmstxt, { copyOrDownloadAsMarkdownButtons } from 'vitepress-plugin-llms'
import { groupIconMdPlugin, groupIconVitePlugin } from 'vitepress-plugin-group-icons'

const pyproject = readFileSync(`${__dirname}/../../pyproject.toml`, 'utf-8')
const version = pyproject.match(/^version\s*=\s*"([^"]+)"/m)?.[1] ?? 'dev'

export default defineConfig({
  title: 'sqlalchemy-seedling',
  description: 'Async-native seeder and factory library for SQLAlchemy',
  base: process.env.DOCS_BASE ?? '/seedling/',

  vite: {
    plugins: [llmstxt(), groupIconVitePlugin()],
  },

  head: [
    ['link', { rel: 'icon', href: 'assets/favicon.png' }],
  ],

  themeConfig: {
    logo: '/assets/logo.png',

    nav: [
      {
        text: 'Guide',
        items: [
          { text: 'Getting Started', link: '/getting-started' },
          { text: 'Seeders', link: '/seeders' },
          { text: 'Factories', link: '/factories' },
          { text: 'State Tracking', link: '/state-tracking' },
          { text: 'Runner', link: '/runner' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'CLI', link: '/cli' },
          { text: 'Configuration', link: '/configuration' },
        ],
      },
      {
        text: 'Resources',
        items: [
          { text: 'Migrate from factory_boy', link: '/migration' },
          { text: 'Cookbook', link: '/cookbook' },
          { text: 'Benchmarks', link: '/benchmarks' },
        ],
      },
      { text: 'For LLMs', link: '/llms' },
      {
        text: `v${version}`,
        items: [
          { text: 'Changelog', link: 'https://github.com/arthurvasconcelos/seedling/blob/main/CHANGELOG.md' },
          { text: 'Contributing', link: 'https://github.com/arthurvasconcelos/seedling/blob/main/CONTRIBUTING.md' },
          { text: 'Releases', link: 'https://github.com/arthurvasconcelos/seedling/releases' },
        ],
      },
    ],

    sidebar: [
      { text: 'Getting Started', link: '/getting-started' },
      { text: 'Seeders', link: '/seeders' },
      { text: 'Factories', link: '/factories' },
      { text: 'State Tracking', link: '/state-tracking' },
      { text: 'Runner', link: '/runner' },
      { text: 'CLI Reference', link: '/cli' },
      { text: 'Configuration', link: '/configuration' },
      { text: 'Migrate from factory_boy', link: '/migration' },
      { text: 'Cookbook', link: '/cookbook' },
      { text: 'Benchmarks', link: '/benchmarks' },
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/arthurvasconcelos/seedling' },
    ],

    search: {
      provider: 'local',
    },

    footer: {
      message: 'Released under the <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>.',
      copyright: `Copyright © ${new Date().getFullYear()} Arthur Vasconcelos`,
    },
  },

  markdown: {
    lineNumbers: true,
    config(md) {
      md.use(groupIconMdPlugin)
      md.use(copyOrDownloadAsMarkdownButtons)
    },
  },
})

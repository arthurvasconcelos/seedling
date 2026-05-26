import { readFileSync } from 'node:fs'
import type { DefaultTheme, HeadConfig, TransformContext } from 'vitepress'
import { defineConfig } from 'vitepress'
import llmstxt, { copyOrDownloadAsMarkdownButtons } from 'vitepress-plugin-llms'
import { groupIconMdPlugin, groupIconVitePlugin } from 'vitepress-plugin-group-icons'

const pyproject = readFileSync(`${__dirname}/../../pyproject.toml`, 'utf-8')
const version = pyproject.match(/^version\s*=\s*"([^"]+)"/m)?.[1] ?? 'dev'

const base = process.env.DOCS_BASE ?? '/seedling/'
const siteUrl = process.env.SITE_URL ?? 'https://arthurvasconcelos.github.io'

function sidebarMain(): DefaultTheme.SidebarItem[] {
  return [
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
        { text: 'CLI Reference', link: '/cli' },
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
  ]
}

export default defineConfig({
  title: 'sqlalchemy-seedling',
  description: 'Async-native seeder and factory library for SQLAlchemy',
  lang: 'en-US',
  base,
  cleanUrls: true,
  lastUpdated: true,

  vite: {
    plugins: [llmstxt(), groupIconVitePlugin()],
  },

  markdown: {
    config(md) {
      md.use(groupIconMdPlugin)
      md.use(copyOrDownloadAsMarkdownButtons)
    },
  },

  head: [
    ['link', { rel: 'icon', href: `${base}favicon.svg`, type: 'image/svg+xml' }],
  ],

  transformHead({ pageData, page }: TransformContext): HeadConfig[] {
    const head: HeadConfig[] = []
    const pageUrl = page.replace(/\.md$/, '').replace(/index$/, '')
    const canonicalUrl = `${siteUrl}${base}${pageUrl}`

    head.push(['link', { rel: 'canonical', href: canonicalUrl }])
    head.push(['meta', { property: 'og:title', content: pageData.title }])
    if (pageData.description) {
      head.push(['meta', { property: 'og:description', content: pageData.description }])
    }
    return head
  },

  themeConfig: {
    logo: { src: '/assets/logo.png', alt: 'sqlalchemy-seedling logo' },

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
      {
        text: `v${version}`,
        items: [
          { text: 'Changelog', link: 'https://github.com/arthurvasconcelos/seedling/blob/main/CHANGELOG.md' },
          { text: 'Contributing', link: 'https://github.com/arthurvasconcelos/seedling/blob/main/CONTRIBUTING.md' },
          { text: 'Releases', link: 'https://github.com/arthurvasconcelos/seedling/releases' },
        ],
      },
      { text: 'For LLMs', link: '/llms' },
    ],

    sidebar: sidebarMain(),

    socialLinks: [
      { icon: 'github', link: 'https://github.com/arthurvasconcelos/seedling' },
    ],

    search: {
      provider: 'local',
      options: {
        miniSearch: {
          searchOptions: {
            boostDocument(documentId: string) {
              if (documentId.includes('getting-started')) return 2
              if (/\/(seeders|factories|state-tracking|runner)/.test(documentId)) return 1.5
              if (/\/(cli|configuration)/.test(documentId)) return 1.3
              return 1
            },
          },
        },
      },
    },

    footer: {
      message: 'Released under the <a href="https://github.com/arthurvasconcelos/seedling/blob/main/LICENSE" target="_blank">MIT License</a>.',
      copyright: `Copyright © ${new Date().getFullYear()} <a href="https://github.com/arthurvasconcelos" target="_blank">Arthur Vasconcelos</a>`,
    },

    editLink: {
      pattern: 'https://github.com/arthurvasconcelos/seedling/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },
  },
})

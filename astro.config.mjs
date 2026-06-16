// @ts-check

import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { defineConfig, fontProviders } from 'astro/config';

// https://astro.build/config
export default defineConfig({
	site: 'https://leejuju.me',
	integrations: [mdx(), sitemap()],
	markdown: {
		shikiConfig: {
			theme: 'github-dark',
		},
		rehypePlugins: [['rehype-slug', {}]],
	},
	redirects: {
		// ──  section landing ──────────────────────
		'/blog':                             '/',

		// ──  relocated ────────────────────────────
		'/blog/agent-memory-systems':        '/blog/memory/agent-memory-systems',
		'/blog/building-effective-agents':   '/blog/paper & engineering/building-effective-agents/building-effective-agents',
		'/blog/ecom1-agent-challenge':       '/blog/challenge/ecom1-agent-challenge/ecom1-agent-challenge',
		'/blog/is-graph-all-you-need':       '/blog/paper & engineering/is-graph-all-you-need/is-graph-all-you-need',
		'/blog/rag-strategies-comparison':   '/blog/RAG/RAG-Challenge-2 & 3/rag-strategies-comparison',

		// ──  merged into framework/langchain ────
		'/blog/langchain-agent-notes':       '/blog/framework/langchain/2-langchain/agent',
		'/blog/langchain-middleware-catalog': '/blog/framework/langchain/2-langchain/agent',
		'/blog/langgraph-notes':             '/blog/framework/langchain/3-langgraph',

		// ──  deleted ─────────────────────────────
		'/blog/hello-world':                 '/',
		'/blog/multi-agent-framework-survey': '/engineering',
		'/blog/pac1-agent-challenge':        '/eval',
		'/blog/wechat-ai-skill-design':      '/engineering',
		'/blog/framework/langchain':         '/',
		'/blog/framework/langchain/README':  '/',
	},
});

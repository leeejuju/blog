# juju's blog

Built with [Astro](https://astro.build).

## 本地开发

```bash
npm install
npm run dev        # http://localhost:4321
```

## 写文章

在 `src/content/blog/` 下新建 `.md` 文件：

```md
---
title: "文章标题"
description: "文章简介"
pubDate: 2026-06-15
---

正文内容...
```

## 部署

push 到 `main` 分支，GitHub Actions 自动构建并部署到 GitHub Pages（leejuju.me）。

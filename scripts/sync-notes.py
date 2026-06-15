#!/usr/bin/env python3
"""
从 multi-agent-design-patterns 知识库同步笔记到 blog。
在 GitHub Actions 中每次构建前运行，检测新内容并自动生成文章。
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 配置
BLOG_CONTENT = Path(__file__).parent.parent / "src" / "content" / "blog"
SOURCE_REPO = "https://github.com/leeejuju/multi-agent-design-patterns.git"
SOURCE_DIR = Path("/tmp/multi-agent-source")

# 需要同步的目录映射：源路径 -> 文章 slug
SYNC_MAP = {
    "agent-system-design/building-effective-agents/README.md": "building-effective-agents",
    "agent-system-design/writing-effective-tools-for-agents/README.md": "writing-effective-tools",
    "agent-system-design/wechat-skill-practice/README.md": "wechat-ai-skill-design",
    "agent-system-paper/Is-Grep-All-You-Need/README.md": "is-graph-all-you-need",
    "agent-challenge/PAC1/README.md": "pac1-agent-challenge",
    "agent-challenge/ECOM1/README.md": "ecom1-agent-challenge",
}

# 目录级同步：整个目录合并为一篇文章
DIR_SYNC = {
    "multi-agent-framework/langchain/1-langchain-core": {
        "slug": "langchain-core-notes",
        "title": "LangChain 源码阅读笔记：Core 模块",
        "description": "LangChain Core 模块源码阅读笔记，涵盖 Runnable、Message、Prompt、Tool、Callback 等核心组件。",
    },
    "multi-agent-framework/langchain/2-langchain/agent": {
        "slug": "langchain-agent-notes",
        "title": "LangChain Agent 架构与中间件系统",
        "description": "深入 LangChain Agent 架构，分析 Factory 模式、Middleware 系统、Graph 编排与循环控制。",
    },
}

SKIP_PATTERNS = [
    r"^\..*",           # 隐藏文件/目录
    r"node_modules",
    r"__pycache__",
    r"\.git$",
]


def run(cmd):
    """运行命令并返回输出。"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def clone_or_pull():
    """克隆或更新源仓库。"""
    if SOURCE_DIR.exists():
        print(f"[sync] 更新已有仓库: {SOURCE_DIR}")
        stdout, stderr, code = run(f"cd {SOURCE_DIR} && git pull --ff-only origin main")
        if code != 0:
            print(f"[sync] git pull 失败: {stderr}，重新克隆...")
            run(f"rm -rf {SOURCE_DIR}")
            return clone_or_pull()
    else:
        print(f"[sync] 克隆仓库: {SOURCE_REPO}")
        stdout, stderr, code = run(f"git clone --depth 1 {SOURCE_REPO} {SOURCE_DIR}")
        if code != 0:
            print(f"[sync] 克隆失败: {stderr}")
            return False
    return True


def get_git_date(filepath, which="first"):
    """获取文件的 git 首次/最后提交日期。"""
    order = "tail -1" if which == "first" else "head -1"
    stdout, _, code = run(
        f"cd {SOURCE_DIR} && git log --follow --format='%ai' -- '{filepath}' | {order}"
    )
    if code != 0 or not stdout:
        return None
    try:
        return datetime.fromisoformat(stdout.strip().replace(" ", "T")).strftime("%Y-%m-%d")
    except ValueError:
        return datetime.now().strftime("%Y-%m-%d")


def should_skip(path):
    """根据规则跳过文件。"""
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, str(path)):
            return True
    return False


def read_source_file(filepath):
    """读取源文件内容。"""
    full_path = SOURCE_DIR / filepath
    if not full_path.exists():
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")


def extract_title_and_desc(content):
    """从内容中提取标题和描述。"""
    lines = content.strip().split("\n")
    title = None
    desc = None

    for line in lines:
        line = line.strip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line and not line.startswith("#") and not line.startswith("!") and not desc:
            if len(line) > 20:
                desc = line[:200]

    return title or "未命名", desc or "暂无描述"


def build_frontmatter(pub_date, updated_date, title, desc):
    """构建 frontmatter。"""
    fm = ["---", f'title: "{title}"', f'description: "{desc}"', f"pubDate: {pub_date}"]
    if updated_date and updated_date != pub_date:
        fm.append(f"updatedDate: {updated_date}")
    fm.append("---\n")
    return "\n".join(fm)


def sync_file(source_path, slug):
    """同步单个文件。"""
    content = read_source_file(source_path)
    if content is None:
        print(f"  [skip] 文件不存在: {source_path}")
        return False

    pub_date = get_git_date(source_path, "first")
    updated_date = get_git_date(source_path, "last")

    if pub_date is None:
        print(f"  [skip] 无法获取 git 日期: {source_path}")
        return False

    # 去掉源文件自身的一级标题，由 frontmatter 的 title 替代
    content_clean = content.strip()
    if content_clean.startswith("# "):
        content_clean = "\n".join(content_clean.split("\n")[1:]).strip()

    title, desc = extract_title_and_desc(content)
    fm = build_frontmatter(pub_date, updated_date, title, desc)

    dest = BLOG_CONTENT / f"{slug}.md"
    dest.write_text(fm + "\n" + content_clean + "\n", encoding="utf-8")
    print(f"  [ok] {slug}.md ({pub_date})")
    return True


def sync_directory(source_dir, slug, title, desc):
    """将整个目录的 README 合并为一篇文章。"""
    dir_path = SOURCE_DIR / source_dir
    if not dir_path.exists():
        print(f"  [skip] 目录不存在: {source_dir}")
        return False

    sections = []
    pub_date = None
    updated_date = None

    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if not should_skip(d)]
        for f in sorted(files):
            if f.endswith(".md") or f.endswith(".MD") or f.endswith(".READNE"):
                filepath = Path(root) / f
                rel_path = filepath.relative_to(SOURCE_DIR)
                content = read_source_file(rel_path)
                if not content or len(content.strip()) < 20:
                    continue

                fp_date = get_git_date(str(rel_path), "first")
                lu_date = get_git_date(str(rel_path), "last")

                if fp_date:
                    if pub_date is None or fp_date < pub_date:
                        pub_date = fp_date
                if lu_date:
                    if updated_date is None or lu_date > updated_date:
                        updated_date = lu_date

                sections.append(content.strip())

    if not sections:
        print(f"  [skip] 无有效内容: {source_dir}")
        return False

    full_content = "\n\n---\n\n".join(sections)
    fm = build_frontmatter(pub_date, updated_date, title, desc)

    dest = BLOG_CONTENT / f"{slug}.md"
    dest.write_text(fm + "\n" + full_content + "\n", encoding="utf-8")
    print(f"  [ok] {slug}.md ({pub_date}" +
          (f", updated {updated_date}" if updated_date != pub_date else "") + ")")
    return True


def main():
    print("[sync] 开始同步笔记...")

    if not clone_or_pull():
        print("[sync] 仓库拉取失败，跳过同步")
        sys.exit(0)  # 不阻止构建

    BLOG_CONTENT.mkdir(parents=True, exist_ok=True)

    updated = 0

    # 单文件同步
    for source_path, slug in SYNC_MAP.items():
        if sync_file(source_path, slug):
            updated += 1

    # 目录级同步
    for source_dir, config in DIR_SYNC.items():
        if sync_directory(source_dir, config["slug"], config["title"], config["description"]):
            updated += 1

    print(f"[sync] 完成，更新 {updated} 篇文章")


if __name__ == "__main__":
    main()

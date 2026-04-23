---
name: qdrant-landing-page-contribution
description: "Step-by-step guide for contributing to the qdrant/landing_page repo. Use when someone needs to add a blog post, article, documentation page, customer logo, or any content to qdrant.tech."
---

# Contributing to the Qdrant Landing Page

Repo: `qdrant/landing_page`. Stack: Hugo + Dart Sass. Default branch: `master`. Never push directly to `master` — always open a PR.


## Local Setup

### Prerequisites

- [Hugo](https://gohugo.io/getting-started/installing/) (required)
- [Node.js + npm](https://nodejs.org/) (required for dev)
- [Dart Sass](https://sass-lang.com/install) — install via brew, NOT npm (`npm install sass` is a different implementation)

```bash
brew install sass/sass/sass   # macOS
```

### Run locally

```bash
cd qdrant-landing
hugo serve
```

Open http://localhost:1313/

To see draft posts:

```bash
hugo serve -D
```

If your changes aren't showing, check for `draft: true` in the markdown frontmatter.


## What Do You Want to Add?

### Blog Post

```bash
cd qdrant-landing
hugo new --kind blog-post blog/<post-title>.md
```

Edit `content/blog/<post-title>.md`. Key frontmatter fields:

```yaml
title: "Post Title"
draft: false
preview_image: /blog/<post-title>/preview.png   # at least 1200x600px
featured: false   # true = appears in "Featured & News" section (only last 4 shown)
```

Store images in `static/blog/<post-title>/`.

Add tags — they're used for related posts even though they don't show on the page.


### Article (Technical / Long-form)

Articles live in `content/articles/`. Required frontmatter:

```yaml
title: "Article Title"
description: "Under 140 characters"
social_preview_image: /articles_data/<alias>/social_preview.jpg   # 1200x630px
preview_dir: /articles_data/<alias>/preview
author: Your Name
author_link: https://...
date: 2026-01-01T00:00:00+00:00
draft: false
```

Generate preview images from one source image:

```bash
bash -x automation/process-article-img.sh ~/Pictures/my_preview.jpg <article-alias>
```

On macOS: swap `stat -c %Y` → `stat -f %m` and `realpath` → `grealpath` in `process-img.sh`.


### Documentation Page

Pages live in `content/documentation/`. Required frontmatter:

```yaml
title: "Page Title"
weight: 10   # lower = higher in sidebar
```

Optional:
```yaml
hideInSidebar: true   # hide from sidebar nav
canonicalUrl: https://qdrant.tech/documentation/...
```

To add a sidebar delimiter:
```bash
hugo new --kind delimiter documentation/<delimiter-title>.md
```

To add a sidebar external link:
```bash
hugo new --kind external-link documentation/<link-title>.md
```


### Customer / Partner Logo

1. Add logo to `qdrant-landing/static/content/images/logos/` — PNG, transparent background, 200px wide, color `#B6C0E4`

2. Create the entry:
```bash
cd qdrant-landing
hugo new --kind customer-logo stack/<customer-name>.md
```

3. Update logo count in `static/css/main.scss`:
```scss
@include marquee.base(80px, 200px, 13, 6, 20px, false, 50s);
// change 13 to the new total number of logos
```

4. To change logo order, edit `weight` in the markdown files in `content/stack/`.


## PR Workflow

1. Branch off `master`
2. Make changes, test locally with `hugo serve`
3. Open PR against `master`
4. Once merged, changes auto-deploy to qdrant.tech


## Common Gotchas

| Issue | Fix |
|-------|-----|
| Changes not showing | Check `draft: true` in frontmatter — run `hugo serve -D` to see drafts |
| CSS not updating | Dart Sass must be installed (not npm `sass`) |
| Preview images missing | Run `process-article-img.sh` or `generate-all-docs-preview.sh` |
| Shortcode not rendering | Check Hugo version compatibility |
| Logo not showing | Check logo count in `main.scss` matches actual file count |


## Useful Shortcuts

```bash
# Generate all doc preview images at once
bash -x automation/generate-all-docs-preview.sh

# Update npm deps via hugo
cd qdrant-landing/themes/qdrant-2024
hugo mod npm pack
cd qdrant-landing
hugo mod npm pack
npm install
```

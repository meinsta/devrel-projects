---
theme: default
title: Qdrant - High-Performance Vector Search at Scale
info: |
  ## Qdrant Presentation
  All Rights Reserved @ Qdrant GmbH 2025
  CONFIDENTIAL DOCUMENT
class: text-center
highlighter: shiki
drawings:
  persist: false
transition: slide-left
mdc: true
background: '#0D0D0D'
---

<style>
:root {
  --slidev-theme-primary: #DC244C;
}
.slidev-layout {
  background: linear-gradient(135deg, #0D0D0D 0%, #1A1A1A 100%);
  color: white;
}
h1 {
  background: linear-gradient(135deg, #FFFFFF 0%, #A0A0A0 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
h1 span, .text-red {
  color: #DC244C !important;
  -webkit-text-fill-color: #DC244C !important;
}
.qdrant-red {
  color: #DC244C;
}
</style>

# High-Performance <span>Vector Search</span> at Scale

<div class="pt-12">
  <span class="px-2 py-1 rounded bg-red-900/30 text-red-400 text-sm">
    All Rights Reserved @ Qdrant GmbH 2025
  </span>
</div>

<div class="abs-br m-6 flex gap-2">
  <span class="text-gray-400 text-sm">CONFIDENTIAL DOCUMENT</span>
</div>

---
layout: center
class: text-center
---

# Our Vision

<div class="text-xl text-gray-300 max-w-3xl mx-auto mt-8 leading-relaxed">
Qdrant is the only open-source vector database built entirely in-house and in Rust for high-performance vector search. Designed specifically for AI workloads, it optimizes speed, accuracy and memory for fast, scalable, and precise vector search, and fits into any deployment type.
</div>

---

# Index

<div class="grid grid-cols-3 gap-4 mt-8">
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">01</span> / Chapter One
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">02</span> / Chapter Two
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">03</span> / Chapter Three
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">04</span> / Chapter Four
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">05</span> / Chapter Five
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">06</span> / Chapter Six
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">07</span> / Chapter Seven
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">08</span> / Chapter Eight
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-red-500 transition cursor-pointer">
    <span class="text-red-500 font-bold">09</span> / Chapter Nine
  </div>
</div>

---
layout: two-cols
layoutClass: gap-16
---

# Key Features

<v-clicks>

- **Lightning Fast** - Built in Rust for maximum performance
- **Real-Time Updates** - Support without downtime
- **Scalable Architecture** - Horizontal scaling with automatic sharding
- **Enterprise Security** - Built-in authentication and RBAC
- **Rich Filtering** - Combine vector similarity with payload filtering
- **Multi-Tenancy** - Native support for multiple collections

</v-clicks>

::right::

<div class="flex items-center justify-center h-full">
  <div class="text-9xl font-bold text-red-500/20">Q</div>
</div>

---
layout: center
---

# Feature Highlights

<div class="grid grid-cols-4 gap-6 mt-12">
  <div class="text-center">
    <div class="text-5xl mb-4">01.</div>
    <div class="text-red-500 font-semibold mb-2">Feature X</div>
    <div class="text-gray-400 text-sm">High-performance vector search optimized for AI workloads</div>
  </div>
  <div class="text-center">
    <div class="text-5xl mb-4">02.</div>
    <div class="text-red-500 font-semibold mb-2">Feature X</div>
    <div class="text-gray-400 text-sm">Scalable architecture for any deployment type</div>
  </div>
  <div class="text-center">
    <div class="text-5xl mb-4">03.</div>
    <div class="text-red-500 font-semibold mb-2">Feature X</div>
    <div class="text-gray-400 text-sm">Speed, accuracy and memory optimization</div>
  </div>
  <div class="text-center">
    <div class="text-5xl mb-4">04.</div>
    <div class="text-red-500 font-semibold mb-2">Feature X</div>
    <div class="text-gray-400 text-sm">Fast, scalable, and precise vector search</div>
  </div>
</div>

---

# Architecture Overview

<div class="grid grid-cols-3 gap-8 mt-8">
  <div class="p-6 bg-gray-800/50 rounded-xl border border-gray-700">
    <h3 class="text-red-500 font-bold text-lg mb-3">Heading 01</h3>
    <p class="text-gray-400 text-sm">High-performance vector search built entirely in-house with Rust for maximum efficiency and reliability.</p>
  </div>
  <div class="p-6 bg-gray-800/50 rounded-xl border border-gray-700">
    <h3 class="text-red-500 font-bold text-lg mb-3">Heading 02</h3>
    <p class="text-gray-400 text-sm">Designed specifically for AI workloads with optimized speed, accuracy and memory management.</p>
  </div>
  <div class="p-6 bg-gray-800/50 rounded-xl border border-gray-700">
    <h3 class="text-red-500 font-bold text-lg mb-3">Heading 03</h3>
    <p class="text-gray-400 text-sm">Fast, scalable, and precise vector search that fits into any deployment type.</p>
  </div>
</div>

---
layout: quote
---

# "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis."

<div class="mt-8 text-gray-400">
  <span class="text-white font-semibold">Name Surname</span> / Position @Company
</div>

---

# Key Metrics

<div class="grid grid-cols-5 gap-6 mt-12 text-center">
  <div class="p-6 bg-gray-800/30 rounded-xl">
    <div class="text-4xl font-bold text-red-500 mb-2">#24M</div>
    <div class="text-sm text-gray-400">Title Here</div>
    <div class="text-xs text-gray-500 mt-2">Description here</div>
  </div>
  <div class="p-6 bg-gray-800/30 rounded-xl">
    <div class="text-4xl font-bold text-red-500 mb-2">#24M</div>
    <div class="text-sm text-gray-400">Title Here</div>
    <div class="text-xs text-gray-500 mt-2">Description here</div>
  </div>
  <div class="p-6 bg-gray-800/30 rounded-xl">
    <div class="text-4xl font-bold text-red-500 mb-2">#24M</div>
    <div class="text-sm text-gray-400">Title Here</div>
    <div class="text-xs text-gray-500 mt-2">Description here</div>
  </div>
  <div class="p-6 bg-gray-800/30 rounded-xl">
    <div class="text-4xl font-bold text-red-500 mb-2">#24M</div>
    <div class="text-sm text-gray-400">Title Here</div>
    <div class="text-xs text-gray-500 mt-2">Description here</div>
  </div>
  <div class="p-6 bg-gray-800/30 rounded-xl">
    <div class="text-4xl font-bold text-red-500 mb-2">#24M</div>
    <div class="text-sm text-gray-400">Title Here</div>
    <div class="text-xs text-gray-500 mt-2">Description here</div>
  </div>
</div>

---

# Data Table

| Text | Text | Text | Text | Text |
|------|------|------|------|------|
| Text | Text | Text | Text | Text |
| Text | Text | Text | Text | Text |
| Text | Text | Text | Text | Text |
| Text | Text | Text | Text | Text |
| Text | Text | Text | Text | Text |

---
layout: two-cols
layoutClass: gap-8
---

# Main Features

<div class="space-y-4">
  <div class="p-4 bg-gray-800/50 rounded-lg">
    <h4 class="text-red-500 font-semibold">Main Title Here</h4>
    <p class="text-gray-400 text-sm mt-2">High-performance vector search optimized for AI workloads.</p>
    <a class="text-red-400 text-xs mt-2 inline-block">Learn More →</a>
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg">
    <h4 class="text-red-500 font-semibold">Main Title Here</h4>
    <p class="text-gray-400 text-sm mt-2">Scalable architecture for enterprise deployment.</p>
    <a class="text-red-400 text-xs mt-2 inline-block">Learn More →</a>
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg">
    <h4 class="text-red-500 font-semibold">Main Title Here</h4>
    <p class="text-gray-400 text-sm mt-2">Speed, accuracy and memory optimization built-in.</p>
    <a class="text-red-400 text-xs mt-2 inline-block">Learn More →</a>
  </div>
</div>

::right::

<div class="space-y-4">
  <div class="p-4 bg-gray-800/50 rounded-lg">
    <h4 class="text-red-500 font-semibold">Main Title Here</h4>
    <p class="text-gray-400 text-sm mt-2">Open-source vector database built entirely in Rust.</p>
    <a class="text-red-400 text-xs mt-2 inline-block">Learn More →</a>
  </div>
  <div class="p-4 bg-gray-800/50 rounded-lg">
    <h4 class="text-red-500 font-semibold">Main Title Here</h4>
    <p class="text-gray-400 text-sm mt-2">Designed specifically for AI and ML workloads.</p>
    <a class="text-red-400 text-xs mt-2 inline-block">Learn More →</a>
  </div>
</div>

---

# Metrics & Partners

<div class="grid grid-cols-3 gap-8 mt-8">
  <div class="p-8 bg-gradient-to-br from-red-900/20 to-transparent rounded-xl border border-red-900/30 text-center">
    <div class="text-sm text-gray-400 mb-2">Metrics</div>
    <div class="text-3xl font-bold text-white mb-4">Key Metric Here</div>
    <p class="text-gray-400 text-sm">High-performance vector search optimized for AI workloads with maximum efficiency.</p>
  </div>
  <div class="p-8 bg-gradient-to-br from-gray-800/50 to-transparent rounded-xl border border-gray-700 text-center">
    <div class="text-sm text-gray-400 mb-2">Partners</div>
    <div class="text-3xl font-bold text-white mb-4">Key Metric Here</div>
    <p class="text-gray-400 text-sm">Scalable architecture designed for enterprise deployment at any scale.</p>
  </div>
  <div class="p-8 bg-gradient-to-br from-gray-800/50 to-transparent rounded-xl border border-gray-700 text-center">
    <div class="text-sm text-gray-400 mb-2">Growth</div>
    <div class="text-3xl font-bold text-white mb-4">Key Metric Here</div>
    <p class="text-gray-400 text-sm">Speed, accuracy and memory optimization for any workload.</p>
  </div>
</div>

---
layout: center
---

# Engineered For Epic Scale

<div class="text-xl text-gray-400 max-w-2xl mx-auto text-center mt-4">
  "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis."
</div>

<div class="mt-8 text-center">
  <span class="text-gray-400">Review From /</span>
  <span class="text-white font-semibold">Name Surname</span>
  <span class="text-gray-400">Year / Position @Company</span>
</div>

<div class="abs-br m-6 text-xs text-gray-500">
  All Rights Reserved @ Qdrant GmbH 2025 | CONFIDENTIAL DOCUMENT
</div>

---
layout: center
class: text-center
---

# High-Performance Vector Search at Scale

<div class="text-2xl text-gray-300 mt-8">
  Create your first cluster on Qdrant Cloud.
</div>

<div class="mt-12">
  <a href="https://cloud.qdrant.io" target="_blank" class="px-8 py-4 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition inline-block">
    Get Started
  </a>
</div>

---
layout: center
class: text-center
---

# Thank You

<div class="text-6xl font-bold text-red-500/20 mt-8">Qdrant</div>

<div class="abs-br m-6 text-xs text-gray-500">
  All Rights Reserved @ Qdrant GmbH 2025
</div>

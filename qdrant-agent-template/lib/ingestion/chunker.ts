/**
 * Text chunking utilities
 * Splits documents into retrieval-friendly chunks
 */

export interface ChunkOptions {
  maxTokens: number;
  overlapTokens: number;
  preserveParagraphs: boolean;
}

export interface Chunk {
  text: string;
  index: number;
  tokenCount: number;
  startOffset: number;
  endOffset: number;
}

const DEFAULT_OPTIONS: ChunkOptions = {
  maxTokens: 500,
  overlapTokens: 50,
  preserveParagraphs: true,
};

/**
 * Estimate token count (rough approximation)
 * ~4 characters per token for English text
 */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

/**
 * Get approximately the last N tokens of text
 */
function getLastNTokens(text: string, n: number): string {
  const approxChars = n * 4;
  if (text.length <= approxChars) return text;
  return text.slice(-approxChars);
}

/**
 * Get approximately the first N tokens of text
 */
function getFirstNTokens(text: string, n: number): string {
  const approxChars = n * 4;
  if (text.length <= approxChars) return text;
  return text.slice(0, approxChars);
}

/**
 * Split text into chunks
 */
export function chunkText(
  text: string,
  options: Partial<ChunkOptions> = {}
): Chunk[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const chunks: Chunk[] = [];

  // Normalize whitespace
  const normalized = text.replace(/\r\n/g, "\n").trim();

  if (!normalized) {
    return [];
  }

  // If text fits in one chunk, return it
  if (estimateTokens(normalized) <= opts.maxTokens) {
    return [
      {
        text: normalized,
        index: 0,
        tokenCount: estimateTokens(normalized),
        startOffset: 0,
        endOffset: normalized.length,
      },
    ];
  }

  if (opts.preserveParagraphs) {
    return chunkByParagraphs(normalized, opts);
  } else {
    return chunkBySentences(normalized, opts);
  }
}

/**
 * Chunk by paragraphs (preserves document structure)
 */
function chunkByParagraphs(text: string, opts: ChunkOptions): Chunk[] {
  const paragraphs = text.split(/\n\n+/);
  const chunks: Chunk[] = [];

  let currentChunk = "";
  let currentTokens = 0;
  let currentStartOffset = 0;
  let textOffset = 0;

  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i].trim();
    if (!para) {
      textOffset += 2; // Account for paragraph separator
      continue;
    }

    const paraTokens = estimateTokens(para);

    // If paragraph alone exceeds max, split it
    if (paraTokens > opts.maxTokens) {
      // Flush current chunk first
      if (currentChunk) {
        chunks.push({
          text: currentChunk.trim(),
          index: chunks.length,
          tokenCount: currentTokens,
          startOffset: currentStartOffset,
          endOffset: textOffset,
        });
      }

      // Split large paragraph by sentences
      const paraChunks = chunkBySentences(para, opts);
      for (const pc of paraChunks) {
        chunks.push({
          ...pc,
          index: chunks.length,
          startOffset: textOffset + pc.startOffset,
          endOffset: textOffset + pc.endOffset,
        });
      }

      currentChunk = "";
      currentTokens = 0;
      currentStartOffset = textOffset + para.length + 2;
      textOffset += para.length + 2;
      continue;
    }

    // Check if adding paragraph would exceed max
    if (currentTokens + paraTokens > opts.maxTokens && currentChunk) {
      // Save current chunk
      chunks.push({
        text: currentChunk.trim(),
        index: chunks.length,
        tokenCount: currentTokens,
        startOffset: currentStartOffset,
        endOffset: textOffset,
      });

      // Start new chunk with overlap
      if (opts.overlapTokens > 0 && currentChunk) {
        const overlap = getLastNTokens(currentChunk, opts.overlapTokens);
        currentChunk = overlap + "\n\n" + para;
        currentTokens = estimateTokens(overlap) + paraTokens;
      } else {
        currentChunk = para;
        currentTokens = paraTokens;
      }
      currentStartOffset = textOffset;
    } else {
      // Add paragraph to current chunk
      if (currentChunk) {
        currentChunk += "\n\n" + para;
      } else {
        currentChunk = para;
        currentStartOffset = textOffset;
      }
      currentTokens += paraTokens;
    }

    textOffset += para.length + 2;
  }

  // Flush remaining
  if (currentChunk.trim()) {
    chunks.push({
      text: currentChunk.trim(),
      index: chunks.length,
      tokenCount: currentTokens,
      startOffset: currentStartOffset,
      endOffset: text.length,
    });
  }

  return chunks;
}

/**
 * Chunk by sentences (for large paragraphs)
 */
function chunkBySentences(text: string, opts: ChunkOptions): Chunk[] {
  // Simple sentence splitting (handles common cases)
  const sentences = text.split(/(?<=[.!?])\s+/);
  const chunks: Chunk[] = [];

  let currentChunk = "";
  let currentTokens = 0;
  let currentStartOffset = 0;
  let textOffset = 0;

  for (const sentence of sentences) {
    const sentenceTokens = estimateTokens(sentence);

    // If single sentence exceeds max, split by character count
    if (sentenceTokens > opts.maxTokens) {
      if (currentChunk) {
        chunks.push({
          text: currentChunk.trim(),
          index: chunks.length,
          tokenCount: currentTokens,
          startOffset: currentStartOffset,
          endOffset: textOffset,
        });
      }

      // Split long sentence
      const charChunks = splitByCharCount(sentence, opts.maxTokens * 4);
      for (const cc of charChunks) {
        chunks.push({
          text: cc,
          index: chunks.length,
          tokenCount: estimateTokens(cc),
          startOffset: textOffset,
          endOffset: textOffset + cc.length,
        });
        textOffset += cc.length;
      }

      currentChunk = "";
      currentTokens = 0;
      currentStartOffset = textOffset;
      continue;
    }

    if (currentTokens + sentenceTokens > opts.maxTokens && currentChunk) {
      chunks.push({
        text: currentChunk.trim(),
        index: chunks.length,
        tokenCount: currentTokens,
        startOffset: currentStartOffset,
        endOffset: textOffset,
      });

      // Overlap
      if (opts.overlapTokens > 0) {
        const overlap = getLastNTokens(currentChunk, opts.overlapTokens);
        currentChunk = overlap + " " + sentence;
        currentTokens = estimateTokens(overlap) + sentenceTokens;
      } else {
        currentChunk = sentence;
        currentTokens = sentenceTokens;
      }
      currentStartOffset = textOffset;
    } else {
      currentChunk += (currentChunk ? " " : "") + sentence;
      currentTokens += sentenceTokens;
    }

    textOffset += sentence.length + 1;
  }

  if (currentChunk.trim()) {
    chunks.push({
      text: currentChunk.trim(),
      index: chunks.length,
      tokenCount: currentTokens,
      startOffset: currentStartOffset,
      endOffset: text.length,
    });
  }

  return chunks;
}

/**
 * Split by character count (last resort)
 */
function splitByCharCount(text: string, maxChars: number): string[] {
  const chunks: string[] = [];
  let remaining = text;

  while (remaining.length > maxChars) {
    // Try to break at word boundary
    let breakPoint = remaining.lastIndexOf(" ", maxChars);
    if (breakPoint < maxChars * 0.5) {
      breakPoint = maxChars;
    }

    chunks.push(remaining.slice(0, breakPoint).trim());
    remaining = remaining.slice(breakPoint).trim();
  }

  if (remaining) {
    chunks.push(remaining);
  }

  return chunks;
}

/**
 * Chunk code files (respects function/class boundaries where possible)
 */
export function chunkCode(
  code: string,
  language: string,
  options: Partial<ChunkOptions> = {}
): Chunk[] {
  const opts = { ...DEFAULT_OPTIONS, maxTokens: 600, ...options };

  // Try to split by function/class boundaries
  const boundaries = findCodeBoundaries(code, language);

  if (boundaries.length > 1) {
    return chunkByBoundaries(code, boundaries, opts);
  }

  // Fall back to regular chunking
  return chunkText(code, { ...opts, preserveParagraphs: false });
}

/**
 * Find code boundaries (functions, classes, etc.)
 */
function findCodeBoundaries(code: string, language: string): number[] {
  const boundaries: number[] = [0];
  const lines = code.split("\n");
  let offset = 0;

  // Language-specific patterns
  const patterns: Record<string, RegExp> = {
    typescript: /^(export\s+)?(async\s+)?(function|class|interface|type|const\s+\w+\s*=\s*(async\s+)?\()/,
    javascript: /^(export\s+)?(async\s+)?(function|class|const\s+\w+\s*=\s*(async\s+)?\()/,
    python: /^(def|class|async def)\s+/,
    rust: /^(pub\s+)?(fn|struct|enum|impl|trait)\s+/,
    go: /^(func|type)\s+/,
  };

  const pattern = patterns[language] || patterns.typescript;

  for (const line of lines) {
    if (pattern.test(line.trim())) {
      if (offset > 0) {
        boundaries.push(offset);
      }
    }
    offset += line.length + 1;
  }

  boundaries.push(code.length);
  return boundaries;
}

/**
 * Chunk by pre-identified boundaries
 */
function chunkByBoundaries(
  text: string,
  boundaries: number[],
  opts: ChunkOptions
): Chunk[] {
  const chunks: Chunk[] = [];

  for (let i = 0; i < boundaries.length - 1; i++) {
    const start = boundaries[i];
    const end = boundaries[i + 1];
    const segment = text.slice(start, end).trim();

    if (!segment) continue;

    const segmentTokens = estimateTokens(segment);

    if (segmentTokens <= opts.maxTokens) {
      chunks.push({
        text: segment,
        index: chunks.length,
        tokenCount: segmentTokens,
        startOffset: start,
        endOffset: end,
      });
    } else {
      // Segment too large, split it
      const subChunks = chunkText(segment, opts);
      for (const sc of subChunks) {
        chunks.push({
          ...sc,
          index: chunks.length,
          startOffset: start + sc.startOffset,
          endOffset: start + sc.endOffset,
        });
      }
    }
  }

  return chunks;
}

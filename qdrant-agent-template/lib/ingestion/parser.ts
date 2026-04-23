/**
 * Document parsing utilities
 * Extracts text and metadata from various formats
 */

export interface ParsedDocument {
  content: string;
  title?: string;
  metadata: {
    format: string;
    wordCount: number;
    hasCode: boolean;
    language?: string;
    sections?: string[];
  };
}

/**
 * Parse markdown document
 */
export function parseMarkdown(text: string): ParsedDocument {
  // Extract title from first H1
  const titleMatch = text.match(/^#\s+(.+)$/m);
  const title = titleMatch?.[1]?.trim();

  // Extract sections (H2, H3)
  const sectionMatches = text.matchAll(/^#{2,3}\s+(.+)$/gm);
  const sections = Array.from(sectionMatches).map((m) => m[1].trim());

  // Check for code blocks
  const hasCode = /```[\s\S]*?```/.test(text);

  // Detect language from code blocks
  const langMatch = text.match(/```(\w+)/);
  const language = langMatch?.[1];

  // Clean up content (remove excessive whitespace, normalize newlines)
  const content = text
    .replace(/\r\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  const wordCount = content.split(/\s+/).length;

  return {
    content,
    title,
    metadata: {
      format: "markdown",
      wordCount,
      hasCode,
      language,
      sections,
    },
  };
}

/**
 * Parse HTML document (basic)
 */
export function parseHTML(html: string): ParsedDocument {
  // Extract title
  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  const title = titleMatch?.[1]?.trim();

  // Remove script and style tags
  let content = html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<noscript[^>]*>[\s\S]*?<\/noscript>/gi, "");

  // Convert common tags to text
  content = content
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n\n")
    .replace(/<\/div>/gi, "\n")
    .replace(/<\/li>/gi, "\n")
    .replace(/<h[1-6][^>]*>/gi, "\n\n")
    .replace(/<\/h[1-6]>/gi, "\n\n");

  // Extract headings for sections
  const sectionMatches = html.matchAll(/<h[2-3][^>]*>([^<]+)<\/h[2-3]>/gi);
  const sections = Array.from(sectionMatches).map((m) =>
    m[1].replace(/<[^>]+>/g, "").trim()
  );

  // Remove remaining tags
  content = content.replace(/<[^>]+>/g, " ");

  // Decode HTML entities
  content = decodeHTMLEntities(content);

  // Clean up whitespace
  content = content
    .replace(/\s+/g, " ")
    .replace(/\n\s*\n/g, "\n\n")
    .trim();

  const hasCode = /<code|<pre/i.test(html);
  const wordCount = content.split(/\s+/).length;

  return {
    content,
    title,
    metadata: {
      format: "html",
      wordCount,
      hasCode,
      sections,
    },
  };
}

/**
 * Parse plain text
 */
export function parsePlainText(text: string): ParsedDocument {
  // Try to extract title from first line if it looks like a heading
  const lines = text.trim().split("\n");
  let title: string | undefined;

  if (lines[0] && lines[0].length < 100 && !lines[0].includes(". ")) {
    title = lines[0].trim();
  }

  const content = text.replace(/\r\n/g, "\n").trim();
  const wordCount = content.split(/\s+/).length;
  const hasCode = /function|class|const|let|var|import|export|def |=>/.test(content);

  return {
    content,
    title,
    metadata: {
      format: "text",
      wordCount,
      hasCode,
    },
  };
}

/**
 * Parse code file
 */
export function parseCode(code: string, filename: string): ParsedDocument {
  // Detect language from filename
  const ext = filename.split(".").pop()?.toLowerCase();
  const languageMap: Record<string, string> = {
    ts: "typescript",
    tsx: "typescript",
    js: "javascript",
    jsx: "javascript",
    py: "python",
    rs: "rust",
    go: "go",
    rb: "ruby",
    java: "java",
    cpp: "cpp",
    c: "c",
    cs: "csharp",
    php: "php",
    swift: "swift",
    kt: "kotlin",
    scala: "scala",
    sql: "sql",
    sh: "shell",
    bash: "shell",
    yaml: "yaml",
    yml: "yaml",
    json: "json",
    xml: "xml",
    md: "markdown",
  };

  const language = ext ? languageMap[ext] : undefined;

  // Try to extract module/file description from first comment
  let title: string | undefined;
  const docCommentMatch = code.match(/^\/\*\*[\s\S]*?\*\/|^"""[\s\S]*?"""|^'''[\s\S]*?'''/m);
  if (docCommentMatch) {
    const comment = docCommentMatch[0]
      .replace(/^\/\*\*|\*\/$/g, "")
      .replace(/^"""|"""$/g, "")
      .replace(/^\s*\*\s?/gm, "")
      .trim();
    const firstLine = comment.split("\n")[0];
    if (firstLine && firstLine.length < 100) {
      title = firstLine;
    }
  }

  // Extract function/class names as sections
  const sections: string[] = [];
  const patterns: Record<string, RegExp> = {
    typescript: /(?:export\s+)?(?:async\s+)?(?:function|class)\s+(\w+)/g,
    javascript: /(?:export\s+)?(?:async\s+)?(?:function|class)\s+(\w+)/g,
    python: /(?:def|class)\s+(\w+)/g,
    rust: /(?:pub\s+)?(?:fn|struct|enum|impl|trait)\s+(\w+)/g,
    go: /(?:func|type)\s+(\w+)/g,
  };

  const pattern = patterns[language || "typescript"];
  if (pattern) {
    const matches = code.matchAll(pattern);
    for (const match of matches) {
      sections.push(match[1]);
    }
  }

  const content = code.trim();
  const wordCount = content.split(/\s+/).length;

  return {
    content,
    title: title || filename,
    metadata: {
      format: "code",
      wordCount,
      hasCode: true,
      language,
      sections,
    },
  };
}

/**
 * Auto-detect format and parse
 */
export function parseDocument(
  content: string,
  options: { filename?: string; format?: string } = {}
): ParsedDocument {
  const { filename, format } = options;

  // If format specified, use it
  if (format === "markdown" || format === "md") {
    return parseMarkdown(content);
  }
  if (format === "html") {
    return parseHTML(content);
  }
  if (format === "code") {
    return parseCode(content, filename || "unknown");
  }

  // Auto-detect from filename
  if (filename) {
    const ext = filename.split(".").pop()?.toLowerCase();
    if (ext === "md" || ext === "markdown") {
      return parseMarkdown(content);
    }
    if (ext === "html" || ext === "htm") {
      return parseHTML(content);
    }
    if (["ts", "tsx", "js", "jsx", "py", "rs", "go", "rb", "java", "cpp", "c"].includes(ext || "")) {
      return parseCode(content, filename);
    }
  }

  // Auto-detect from content
  if (content.trim().startsWith("<!DOCTYPE") || content.trim().startsWith("<html")) {
    return parseHTML(content);
  }
  if (content.includes("```") || /^#\s+/.test(content)) {
    return parseMarkdown(content);
  }

  // Default to plain text
  return parsePlainText(content);
}

/**
 * Decode HTML entities
 */
function decodeHTMLEntities(text: string): string {
  const entities: Record<string, string> = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&nbsp;": " ",
    "&mdash;": "—",
    "&ndash;": "–",
    "&hellip;": "…",
    "&copy;": "©",
    "&reg;": "®",
    "&trade;": "™",
  };

  return text.replace(/&[#\w]+;/g, (match) => entities[match] || match);
}

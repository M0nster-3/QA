import { Component } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';

/* ── LaTeX preprocessing ──────────────────────────────── */

function preprocessLaTeX(content) {
  if (!content) return content;
  let s = content;

  // 1. \[ ... \] → $$ ... $$  (display math)
  s = s.replace(/\\\[\s*([\s\S]*?)\s*\\\]/g, (_, inner) => `$$\n${inner.trim()}\n$$`);

  // 2. \( ... \) → $ ... $  (inline math)
  s = s.replace(/\\\(\s*([\s\S]*?)\s*\\\)/g, (_, inner) => `$${inner.trim()}$`);

  // 3. Bare [ \begin{...} ... \end{...} ] → $$ \begin{...} ... \end{...} $$
  //    Handles the pattern where \[ \] delimiters got stripped to [ ]
  s = s.replace(
    /(?:^|\n)\s*\[\s*(\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\})\s*\]\s*(?:\n|$)/g,
    (_, inner) => `\n$$\n${inner.trim()}\n$$\n`
  );

  // 4. Standalone \begin{align/equation/gather/...} not wrapped in $$ → wrap them
  //    But only if not already inside $$
  s = s.replace(
    /(?<!\$)\s*(\\begin\{(align|align\*|equation|equation\*|gather|gather\*|multline|multline\*|cases|pmatrix|bmatrix|vmatrix)\}[\s\S]*?\\end\{\2\})\s*(?!\$)/g,
    (match, inner) => {
      // Check if already wrapped (crude but effective)
      const before = s.substring(0, s.indexOf(match));
      const dollarCount = (before.match(/\$\$/g) || []).length;
      if (dollarCount % 2 === 1) return match; // inside $$, leave alone
      return `\n$$\n${inner.trim()}\n$$\n`;
    }
  );

  return s;
}

/* ── Error boundary for MD rendering ──────────────────── */

class MDErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return <pre className="md-fallback">{String(this.props.content || '')}</pre>;
    }
    return this.props.children;
  }
}

/* ── MarkdownRenderer ─────────────────────────────────── */

export default function MarkdownRenderer({ content, className }) {
  if (!content) return null;

  const processed = preprocessLaTeX(content);

  return (
    <MDErrorBoundary content={content}>
      <div className={className || 'markdown-body'}>
        <ReactMarkdown
          remarkPlugins={[remarkMath, remarkGfm]}
          rehypePlugins={[rehypeKatex]}
        >
          {processed}
        </ReactMarkdown>
      </div>
    </MDErrorBoundary>
  );
}

import "katex/dist/katex.min.css";

import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { cn } from "@/lib/utils";

const components: Components = {
  h1: ({ node: _node, ...props }) => <h1 className="mb-4 text-2xl font-semibold" {...props} />,
  h2: ({ node: _node, ...props }) => (
    <h2 className="mt-8 mb-3 scroll-mt-20 border-b pb-1 text-xl font-semibold" {...props} />
  ),
  h3: ({ node: _node, ...props }) => (
    <h3 className="mt-5 mb-2 text-base font-semibold" {...props} />
  ),
  p: ({ node: _node, ...props }) => <p className="my-3 leading-7" {...props} />,
  ul: ({ node: _node, ...props }) => <ul className="my-3 list-disc space-y-1.5 pl-6" {...props} />,
  ol: ({ node: _node, ...props }) => (
    <ol className="my-3 list-decimal space-y-1.5 pl-6" {...props} />
  ),
  li: ({ node: _node, ...props }) => <li className="leading-7" {...props} />,
  em: ({ node: _node, ...props }) => <em className="text-muted-foreground" {...props} />,
  strong: ({ node: _node, ...props }) => <strong className="font-semibold" {...props} />,
  code: ({ node: _node, ...props }) => (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm" {...props} />
  ),
  a: ({ node: _node, ...props }) => (
    <a className="text-primary underline underline-offset-4" target="_blank" {...props} />
  ),
};

/** Markdown + công thức LaTeX ($...$) bằng KaTeX. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("text-[15px]", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

/** Một dòng văn bản ngắn có thể chứa công thức inline. */
export function InlineMath({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{ p: ({ node: _node, ...props }) => <span {...props} /> }}
    >
      {children}
    </ReactMarkdown>
  );
}

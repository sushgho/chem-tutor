"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import React from "react";
import type { Components } from "react-markdown";
import MermaidDiagram from "@/components/MermaidDiagram";
import "katex/dist/katex.min.css";
import "katex/contrib/mhchem"; // enables \ce{...} chemical equations

function normalizeMathDelimiters(markdown: string): string {
  return markdown
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, formula: string) => `$$\n${formula}\n$$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, formula: string) => `$${formula}$`);
}

const components: Components = {
  pre({ children, ...props }) {
    const code = React.Children.only(children);
    if (
      React.isValidElement<{ className?: string; children?: React.ReactNode }>(code) &&
      code.props.className?.includes("language-mermaid")
    ) {
      return <MermaidDiagram chart={String(code.props.children).replace(/\n$/, "")} />;
    }
    return <pre {...props}>{children}</pre>;
  },
};

export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
      {normalizeMathDelimiters(children)}
    </ReactMarkdown>
  );
}

"use client";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import React from "react";
import type { Components } from "react-markdown";
import MermaidDiagram from "@/components/MermaidDiagram";
import "katex/dist/katex.min.css";
import "katex/contrib/mhchem"; // enables \ce{...} chemical equations

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
    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
      {children}
    </ReactMarkdown>
  );
}

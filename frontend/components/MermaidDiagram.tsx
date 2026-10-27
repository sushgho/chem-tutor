"use client";

import { useEffect, useId, useState } from "react";

let mermaidPromise: Promise<typeof import("mermaid").default> | null = null;

function getMermaid() {
  mermaidPromise ??= import("mermaid").then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "default",
      flowchart: { htmlLabels: false },
    });
    return mermaid;
  });
  return mermaidPromise;
}

export default function MermaidDiagram({ chart }: { chart: string }) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(false);
  const id = `diagram-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const mermaid = await getMermaid();
        const result = await mermaid.render(id, chart);
        if (active) {
          setSvg(result.svg);
          setError(false);
        }
      } catch {
        if (active) {
          setSvg("");
          setError(true);
        }
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [chart, id]);

  return (
    <figure className="diagram">
      {svg ? (
        <div className="diagram-canvas" dangerouslySetInnerHTML={{ __html: svg }} />
      ) : error ? (
        <figcaption>Diagram could not be rendered.</figcaption>
      ) : (
        <figcaption>Preparing diagram…</figcaption>
      )}
    </figure>
  );
}

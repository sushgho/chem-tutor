import { API, type Source } from "@/lib/api";

export default function SourcePages({ sources }: { sources: Source[] }) {
  const uniquePages = new Map<string, Source>();
  for (const source of sources) {
    if (source.image_url) uniquePages.set(source.image_url, source);
  }
  const pages = Array.from(uniquePages.values());
  if (pages.length === 0) return null;

  return (
    <div className="source-pages">
      {pages.map((source) => (
        <details key={source.image_url}>
          <summary>
            View original textbook page{source.page ? ` ${source.page}` : ""}
          </summary>
          <img
            src={`${API}${source.image_url}`}
            alt={`Original textbook page ${source.page ?? ""} from ${source.source}`}
            loading="lazy"
          />
        </details>
      ))}
    </div>
  );
}

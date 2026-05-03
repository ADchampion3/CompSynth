import { useState, useEffect, useRef, useCallback } from "react";
import { safeHref } from "../../api/client";

type ViewMode = "original" | "text";

const STORAGE_KEY = "compsynth-article-view";
const BLOCKED_TIMEOUT_MS = 3000;

function readStoredView(): ViewMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "original" || stored === "text") return stored;
  } catch {
    // localStorage unavailable
  }
  return "original";
}

function writeStoredView(mode: ViewMode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // localStorage unavailable
  }
}

interface ArticleContentProps {
  url: string;
  content: string;
}

export default function ArticleContent({ url, content }: ArticleContentProps) {
  const validatedUrl = safeHref(url);
  const canEmbed = validatedUrl !== "#";

  const [mode, setMode] = useState<ViewMode>(() => {
    if (!canEmbed) return "text";
    return readStoredView();
  });
  const [iframeState, setIframeState] = useState<
    "loading" | "loaded" | "blocked"
  >("loading");
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const handleLoad = useCallback(() => {
    setIframeState("loaded");
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  // Reset iframe state when URL changes
  useEffect(() => {
    if (mode === "original" && canEmbed) {
      setIframeState("loading");
      timerRef.current = setTimeout(() => {
        setIframeState("blocked");
      }, BLOCKED_TIMEOUT_MS);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [mode, validatedUrl, canEmbed]);

  // Cleanup iframe on unmount
  useEffect(() => {
    const iframe = iframeRef.current;
    return () => {
      if (iframe) iframe.src = "about:blank";
    };
  }, []);

  const toggleMode = (next: ViewMode) => {
    setMode(next);
    writeStoredView(next);
  };

  const domain = canEmbed ? new URL(validatedUrl).hostname : "";

  return (
    <section className="mt-8">
      {/* Toggle bar */}
      <div className="flex items-center justify-between mb-3">
        <div
          role="tablist"
          className="inline-flex rounded-sm border border-rule overflow-hidden"
        >
          <button
            role="tab"
            aria-selected={mode === "original"}
            onClick={() => toggleMode("original")}
            className={`px-3 py-1 text-[0.6875rem] font-semibold uppercase tracking-wider transition-colors ${
              mode === "original"
                ? "bg-ink text-paper"
                : "bg-paper text-ink-3 hover:text-ink-2"
            }`}
          >
            Original Page
          </button>
          <button
            role="tab"
            aria-selected={mode === "text"}
            onClick={() => toggleMode("text")}
            className={`px-3 py-1 text-[0.6875rem] font-semibold uppercase tracking-wider transition-colors ${
              mode === "text"
                ? "bg-ink text-paper"
                : "bg-paper text-ink-3 hover:text-ink-2"
            }`}
          >
            Full Text
          </button>
        </div>

        {canEmbed && (
          <a
            href={validatedUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[0.6875rem] font-medium text-ink-4 hover:text-ink transition-colors"
          >
            Open in new tab
          </a>
        )}
      </div>

      {/* Content area */}
      <div role="tabpanel" className="min-h-[400px]">
        {mode === "original" && canEmbed ? (
          <>
            {iframeState === "loading" && (
              <div className="flex items-center justify-center h-[70vh] text-sm text-ink-3">
                <span className="animate-pulse">Loading original page...</span>
              </div>
            )}

            {iframeState === "blocked" && (
              <div className="flex flex-col items-center justify-center h-[70vh] text-center bg-paper-2 rounded-md">
                <div className="w-10 h-10 rounded-full bg-paper-3 flex items-center justify-center text-sm font-bold text-ink-3 mb-4">
                  {domain.charAt(0).toUpperCase()}
                </div>
                <p className="text-sm font-medium text-ink-2 mb-1">
                  {domain} blocks iframe embedding
                </p>
                <p className="text-xs text-ink-4 mb-4 max-w-sm">
                  This site doesn't allow embedding. You can open the original
                  article or switch to Full Text view.
                </p>
                <div className="flex gap-3">
                  <a
                    href={validatedUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 text-xs font-semibold bg-ink text-paper rounded-sm hover:bg-ink-2 transition-colors"
                  >
                    Open original
                  </a>
                  <button
                    onClick={() => toggleMode("text")}
                    className="px-4 py-2 text-xs font-semibold border border-rule text-ink-3 rounded-sm hover:text-ink-2 transition-colors"
                  >
                    Full Text
                  </button>
                </div>
              </div>
            )}

            <iframe
              ref={iframeRef}
              src={validatedUrl}
              onLoad={handleLoad}
              title="Article content"
              sandbox="allow-scripts allow-popups allow-forms"
              className={`w-full border-0 rounded-md ${
                iframeState === "loaded" ? "h-[70vh]" : "hidden"
              }`}
            />
          </>
        ) : (
          <div>
            {content ? (
              <div className="text-[0.9375rem] text-ink-2 leading-relaxed whitespace-pre-wrap max-w-none font-display">
                {content}
              </div>
            ) : (
              <p className="text-sm text-ink-4">No full content available.</p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

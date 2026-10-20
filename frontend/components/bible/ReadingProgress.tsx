"use client";

import { useEffect, useRef } from "react";

/** A scroll-position indicator, deliberately not a chapter-completion marker. */
export default function ReadingProgress({ chapterKey }: { chapterKey: string }) {
  const bar = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const article = document.getElementById("sb-reading-article");
    const indicator = bar.current;
    if (!article || !indicator) return;
    let frame = 0;
    let lastValue = -1;
    const measure = () => {
      frame = 0;
      const toolbarBottom = indicator.parentElement?.getBoundingClientRect().bottom ?? 0;
      const rect = article.getBoundingClientRect();
      const start = window.scrollY + rect.top - toolbarBottom;
      const end = window.scrollY + rect.bottom - window.innerHeight;
      const fraction = end <= start
        ? (window.scrollY >= start ? 1 : 0)
        : Math.max(0, Math.min(1, (window.scrollY - start) / (end - start)));
      const percent = Math.round(fraction * 100);
      if (percent !== lastValue) {
        indicator.style.setProperty("--sb-progress", `${percent}%`);
        indicator.setAttribute("aria-valuenow", String(percent));
        lastValue = percent;
      }
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(measure); };
    schedule();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(schedule) : null;
    observer?.observe(article);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      observer?.disconnect();
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [chapterKey]);

  return <div ref={bar} className="sb-progress" role="progressbar" aria-label="Chapter scroll position"
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={0} />;
}

"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { CloseIcon } from "./icons";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal dialog: a bottom sheet on phones, a centred panel on wider screens.
 * Traps Tab inside, closes on Escape or backdrop click, and returns focus to the opener.
 */
export default function Sheet({
  title,
  onClose,
  children,
  footer,
  size = "md",
  initialFocus,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  initialFocus?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const first = (initialFocus && panel?.querySelector<HTMLElement>(initialFocus)) || panel?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const items = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((item) => item.offsetParent !== null);
      if (!items.length) return;
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, [onClose, initialFocus]);

  return (
    <div className="sb-backdrop" onClick={onClose}>
      <div
        ref={panelRef}
        className={`sb-sheet sb-sheet-${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sb-sheet-head">
          <h2 className="font-playfair sb-sheet-title">{title}</h2>
          <button type="button" className="sb-icon-btn" onClick={onClose} aria-label={`Close ${title}`}>
            <CloseIcon />
          </button>
        </div>
        <div className="sb-sheet-body">{children}</div>
        {footer && <div className="sb-sheet-foot">{footer}</div>}
      </div>
    </div>
  );
}

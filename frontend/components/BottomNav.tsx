"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconHome, IconBook, IconCross, IconTranslate } from "./Icons";

const TABS = [
  { href: "/", Icon: IconHome, label: "Home" },
  { href: "/zomidictionary", Icon: IconBook, label: "Dictionary" },
  { href: "/zomitranslate", Icon: IconTranslate, label: "Translate" },
  { href: "/bible", Icon: IconCross, label: "Bible" },
];

function MoreIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M5 7h14M5 12h14M5 17h14" />
    </svg>
  );
}

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="bottom-nav" aria-label="Main sections">
      {TABS.map(({ href, Icon, label }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`nav-item${active ? " active" : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <span className="nav-icon"><Icon size={20} filled={active} /></span>
            <span className="nav-label">{label}</span>
          </Link>
        );
      })}
      <button type="button" className="nav-item" onClick={() => window.dispatchEvent(new Event("siamsil:open-menu"))}>
        <span className="nav-icon"><MoreIcon /></span>
        <span className="nav-label">More</span>
      </button>
    </nav>
  );
}

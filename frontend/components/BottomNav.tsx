"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconHome, IconBook, IconTranslate, IconAcademic, IconLibrary } from "./Icons";

const TABS = [
  { href: "/", Icon: IconHome, label: "Home" },
  { href: "/zomidictionary", Icon: IconBook, label: "Dictionary" },
  { href: "/zomitranslate", Icon: IconTranslate, label: "Translate" },
  { href: "/learning", Icon: IconAcademic, label: "Learn" },
  { href: "/library", Icon: IconLibrary, label: "Library" },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="bottom-nav">
      {TABS.map(({ href, Icon, label }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`nav-item${active ? " active" : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <span className="nav-icon"><Icon size={18} filled={active} /></span>
            <span className="nav-label">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

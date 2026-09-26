"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconHome, IconBook, IconCross, IconChat, IconUser } from "./Icons";

const TABS = [
  { href: "/", Icon: IconHome, label: "Home" },
  { href: "/zomidictionary", Icon: IconBook, label: "Dictionary" },
  { href: "/bible", Icon: IconCross, label: "Bible" },
  { href: "/chat", Icon: IconChat, label: "AI" },
  { href: "/profile", Icon: IconUser, label: "Profile" },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="bottom-nav">
      {TABS.map(({ href, Icon, label }, i) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        const tone = i % 2 === 0 ? "navy" : "navy2";
        return (
          <Link
            key={href}
            href={href}
            className={`nav-item ${tone}${active ? " active" : ""}`}
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

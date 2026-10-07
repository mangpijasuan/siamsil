"use client";

import { useEffect, useState, type ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconAcademic,
  IconBook,
  IconChat,
  IconCross,
  IconHome,
  IconLibrary,
  IconSearch,
  IconTranslate,
  IconUser,
} from "./Icons";

type NavTab = {
  href: string;
  Icon: typeof IconHome;
  label: string;
  short: string;
  hint: string;
};

const NAV_GROUPS: Array<{ title: string; tabs: NavTab[] }> = [
  {
    title: "Read",
    tabs: [
      { href: "/", Icon: IconHome, label: "Home", short: "Home", hint: "Your Zomi library" },
      { href: "/library", Icon: IconLibrary, label: "Library", short: "Library", hint: "Books & archives" },
      { href: "/zomidictionary", Icon: IconBook, label: "Dictionary", short: "Dictionary", hint: "Zomi–English" },
      { href: "/bible", Icon: IconCross, label: "Bible", short: "Bible", hint: "Laisiangtho" },
    ],
  },
  {
    title: "Learn",
    tabs: [
      { href: "/learning", Icon: IconAcademic, label: "Learning", short: "Learn", hint: "Grammar & phrases" },
      { href: "/zomitranslate", Icon: IconTranslate, label: "Translate", short: "Translate", hint: "Retrieve known pairs" },
      { href: "/chat", Icon: IconChat, label: "Siamsil AI", short: "AI", hint: "Retrieval assistant" },
    ],
  },
];
const PROFILE_TAB: NavTab = { href: "/profile", Icon: IconUser, label: "Profile", short: "Profile", hint: "Progress & settings" };

const PAGE_META = [
  { match: /^\/$/, eyebrow: "Zomi literature hub", title: "Home" },
  { match: /^\/library/, eyebrow: "Books & archives", title: "Library" },
  { match: /^\/zomidictionary/, eyebrow: "Words & meaning", title: "Dictionary" },
  { match: /^\/bible/, eyebrow: "Laisiangtho", title: "Bible" },
  { match: /^\/learning/, eyebrow: "Build your fluency", title: "Learning" },
  { match: /^\/zomitranslate/, eyebrow: "English ↔ Zomi", title: "Translate" },
  { match: /^\/chat/, eyebrow: "Zomi language assistant", title: "Siamsil AI" },
  { match: /^\/profile/, eyebrow: "Your account", title: "Profile" },
];

const SIDEBAR_KEY = "siamsil-sidebar-collapsed";
const DESKTOP_QUERY = "(min-width: 1024px)";

function MenuIcon() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

function BrandLogo({ size = 38 }: { size?: number }) {
  return (
    <span className="shell-brand-logo-wrap" style={{ width: size, height: size }}>
      <Image src="/logo.png" alt="" width={size} height={size} className="shell-brand-logo" priority unoptimized />
    </span>
  );
}

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function NavLink({ tab, pathname, onNavigate }: { tab: NavTab; pathname: string; onNavigate?: () => void }) {
  const active = isActive(pathname, tab.href);
  const { Icon } = tab;
  return (
    <Link
      href={tab.href}
      className={`side-panel-item${active ? " active" : ""}`}
      title={`${tab.label} — ${tab.hint}`}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
    >
      <span className="side-panel-icon"><Icon size={19} filled={active} /></span>
      <span className="side-panel-copy">
        <span className="side-panel-label">{tab.label}</span>
        <span className="side-panel-hint">{tab.hint}</span>
      </span>
      <span className="side-panel-short" aria-hidden="true">{tab.short}</span>
    </Link>
  );
}

function Navigation({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="side-panel-nav" aria-label="Primary navigation">
      {NAV_GROUPS.map((group) => (
        <div key={group.title} className="side-panel-group">
          <div className="side-panel-group-title">{group.title}</div>
          {group.tabs.map((tab) => (
            <NavLink key={tab.href} tab={tab} pathname={pathname} onNavigate={onNavigate} />
          ))}
        </div>
      ))}
      <div className="side-panel-group side-panel-group-end">
        <NavLink tab={PROFILE_TAB} pathname={pathname} onNavigate={onNavigate} />
      </div>
    </nav>
  );
}

export default function SidebarNav({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const page = PAGE_META.find(({ match }) => match.test(pathname)) ?? PAGE_META[0];

  useEffect(() => {
    const media = window.matchMedia(DESKTOP_QUERY);
    const frame = window.requestAnimationFrame(() => {
      setCollapsed(localStorage.getItem(SIDEBAR_KEY) === "true");
      setIsDesktop(media.matches);
    });
    const onChange = (event: MediaQueryListEvent) => {
      setIsDesktop(event.matches);
      if (event.matches) setMobileOpen(false);
    };
    media.addEventListener("change", onChange);
    return () => {
      window.cancelAnimationFrame(frame);
      media.removeEventListener("change", onChange);
    };
  }, []);

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  function toggleMenu() {
    if (window.matchMedia(DESKTOP_QUERY).matches) {
      setCollapsed((value) => {
        localStorage.setItem(SIDEBAR_KEY, String(!value));
        return !value;
      });
    } else {
      setMobileOpen((value) => !value);
    }
  }

  const menuExpanded = isDesktop ? !collapsed : mobileOpen;

  return (
    <>
      <header className="shell-topbar">
        <div className="shell-topbar-inner">
          <button
            type="button"
            className="shell-menu-btn"
            onClick={toggleMenu}
            aria-label={menuExpanded ? "Hide navigation" : "Show navigation"}
            aria-expanded={menuExpanded}
            aria-controls={isDesktop ? "desktop-sidebar" : "mobile-drawer"}
          >
            <MenuIcon />
          </button>

          <Link href="/" className="shell-brand shell-brand-mobile" aria-label="Siamsil home">
            <BrandLogo size={36} />
            <span className="shell-brand-text">
              <span className="font-playfair shell-brand-title">SIAMSIL</span>
              <span className="shell-brand-sub">The Art of Literature</span>
            </span>
          </Link>

          <div className="shell-page-context">
            <span className="shell-page-eyebrow">{page.eyebrow}</span>
            <span className="font-playfair shell-page-title">{page.title}</span>
          </div>

          <Link href="/zomidictionary" className="shell-topbar-search" aria-label="Search dictionary">
            <IconSearch size={16} />
            <span className="shell-topbar-search-text">Search the dictionary</span>
          </Link>
        </div>
      </header>

      <div className="app-shell">
        <aside id="desktop-sidebar" className={`desktop-sidebar${collapsed ? " collapsed" : ""}`} aria-label="Primary">
          <Navigation pathname={pathname} />
          <div className="side-panel-foot">
            <span className="sidebar-foot-mark">S</span>
            <span className="sidebar-foot-copy">Preserving language through literature.</span>
          </div>
        </aside>

        <div className={`mobile-drawer-backdrop${mobileOpen ? " visible" : ""}`} onClick={() => setMobileOpen(false)} aria-hidden="true" />
        <aside id="mobile-drawer" className={`mobile-drawer${mobileOpen ? " open" : ""}`} aria-label="Mobile navigation" aria-hidden={!mobileOpen}>
          <div className="mobile-drawer-head">
            <Link href="/" className="sidebar-brand-link" onClick={() => setMobileOpen(false)}>
              <BrandLogo size={40} />
              <span className="sidebar-brand-copy">
                <span className="font-playfair sidebar-brand-title">SIAMSIL</span>
                <span className="sidebar-brand-sub">The Art of Literature</span>
              </span>
            </Link>
            <button type="button" className="side-panel-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
              <CloseIcon />
            </button>
          </div>
          <Navigation pathname={pathname} onNavigate={() => setMobileOpen(false)} />
          <div className="side-panel-foot">Literature in Zomi</div>
        </aside>

        <main className="app-main">{children}</main>
      </div>
    </>
  );
}

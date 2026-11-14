"use client";

import { useEffect, useState, type ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconAI,
  IconAcademic,
  IconBook,
  IconCross,
  IconHelp,
  IconHome,
  IconInfo,
  IconLibrary,
  IconResources,
  IconSearch,
  IconTranslate,
  IconUser,
} from "./Icons";

type NavTab = {
  href: string;
  Icon: typeof IconHome;
  /** The glyph cut from the design sheet (public/theme/nav-<glyph>.png). */
  glyph: string;
  label: string;
  short: string;
  hint: string;
};

const NAV_GROUPS: Array<{ title: string; tabs: NavTab[] }> = [
  {
    title: "Language",
    tabs: [
      { href: "/", Icon: IconHome, glyph: "home", label: "Home", short: "Home", hint: "Your Zomi library" },
      { href: "/zomidictionary", Icon: IconBook, glyph: "dictionary", label: "Dictionary", short: "Dictionary", hint: "Zomi–English" },
      { href: "/zomitranslate", Icon: IconTranslate, glyph: "translate", label: "Translate", short: "Translate", hint: "Retrieve known pairs" },
    ],
  },
  {
    title: "Read",
    tabs: [
      { href: "/bible", Icon: IconCross, glyph: "bible", label: "Bible", short: "Bible", hint: "Laisiangtho" },
      { href: "/library", Icon: IconLibrary, glyph: "library", label: "Library", short: "Library", hint: "Books & archives" },
    ],
  },
  {
    title: "Learn",
    tabs: [
      { href: "/learning", Icon: IconAcademic, glyph: "learn", label: "Learn", short: "Learn", hint: "Grammar & phrases" },
      { href: "/chat", Icon: IconAI, glyph: "ai", label: "Siamsil AI", short: "AI", hint: "Retrieval assistant" },
    ],
  },
];
const ABOUT_TABS: NavTab[] = [
  { href: "/resources", Icon: IconResources, glyph: "resources", label: "Resources", short: "Resources", hint: "Where our data comes from" },
  { href: "/about", Icon: IconInfo, glyph: "about", label: "About", short: "About", hint: "What Siamsil is" },
  { href: "/help", Icon: IconHelp, glyph: "help", label: "Help", short: "Help", hint: "Using Siamsil" },
];
const PROFILE_TAB: NavTab = { href: "/profile", Icon: IconUser, glyph: "profile", label: "Profile", short: "Profile", hint: "Progress & settings" };

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

// The Siamsil Technology Hub lockup (mark, wordmark and tagline in one image). Silver and gold on a transparent background, for the navy bars. logo-lockup-light.png is the navy and red version for white backgrounds.
function BrandLockup({ height }: { height: number }) {
  return (
    <Image
      src="/logo-lockup.png"
      alt="Siamsil Technology Hub"
      width={Math.round(height * (1200 / 358))}
      height={height}
      className="brand-lockup"
      priority
      unoptimized
    />
  );
}

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function NavLink({ tab, pathname, onNavigate }: { tab: NavTab; pathname: string; onNavigate?: () => void }) {
  const active = isActive(pathname, tab.href);
  return (
    <Link
      href={tab.href}
      className={`side-panel-item${active ? " active" : ""}`}
      title={`${tab.label} — ${tab.hint}`}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
    >
      <span className="side-panel-icon"><span className="st-nav-glyph" style={{ ["--glyph" as string]: `url(/theme/nav-${tab.glyph}.png)` }} aria-hidden="true" /></span>
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
      <div className="side-panel-group side-panel-group-more">
        {ABOUT_TABS.map((tab) => (
          <NavLink key={tab.href} tab={tab} pathname={pathname} onNavigate={onNavigate} />
        ))}
      </div>
      <div className="side-panel-group side-panel-group-end">
        <NavLink tab={PROFILE_TAB} pathname={pathname} onNavigate={onNavigate} />
      </div>
    </nav>
  );
}

export default function SidebarNav({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  // Desktop starts with the full menu; ☰ shrinks it to an icon rail and the choice is remembered.
  const [collapsed, setCollapsed] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);

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
    // The phone's bottom bar "More" button opens the menu drawer.
    const openMenu = () => setMobileOpen(true);
    media.addEventListener("change", onChange);
    window.addEventListener("siamsil:open-menu", openMenu);
    return () => {
      window.cancelAnimationFrame(frame);
      media.removeEventListener("change", onChange);
      window.removeEventListener("siamsil:open-menu", openMenu);
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
      <header className={`shell-topbar${collapsed ? " nav-collapsed" : ""}`}>
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
            <BrandLockup height={46} />
          </Link>

          <form action="/zomidictionary" method="GET" className="shell-topbar-search" role="search">
            <IconSearch size={17} />
            <input name="q" type="search" placeholder="Search the dictionary…" aria-label="Search the dictionary" className="shell-topbar-search-input" />
          </form>
          <Link href="/zomidictionary" className="shell-topbar-search-btn" aria-label="Search the dictionary">
            <IconSearch size={18} />
          </Link>
          <Link
            href="/profile"
            className={`shell-user-link${isActive(pathname, "/profile") ? " active" : ""}`}
            aria-label="Open guest profile"
            aria-current={isActive(pathname, "/profile") ? "page" : undefined}
          >
            <span className="shell-user-copy"><strong>Guest</strong><small>Local profile</small></span>
            <span className="shell-user-avatar"><IconUser size={20} /></span>
          </Link>
        </div>
      </header>

      <div className="app-shell">
        <aside id="desktop-sidebar" className={`desktop-sidebar${collapsed ? " collapsed" : ""}`} aria-label="Primary">
          <Navigation pathname={pathname} />
        </aside>

        <div className={`mobile-drawer-backdrop${mobileOpen ? " visible" : ""}`} onClick={() => setMobileOpen(false)} aria-hidden="true" />
        <aside id="mobile-drawer" className={`mobile-drawer${mobileOpen ? " open" : ""}`} aria-label="Mobile navigation" aria-hidden={!mobileOpen}>
          <div className="mobile-drawer-head">
            <Link href="/" className="sidebar-brand-link" onClick={() => setMobileOpen(false)}>
              <BrandLockup height={44} />
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

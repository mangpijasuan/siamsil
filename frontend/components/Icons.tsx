export type IconProps = {
  size?: number;
  className?: string;
  /** Outline for inactive; filled for active nav items */
  filled?: boolean;
};

export function IconHome({ size = 18, className = "", filled = false }: IconProps) {
  if (filled) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
        <path d="M12 3.2L3 10.2V20a1.2 1.2 0 001.2 1.2h5.3V13.5h4.9v7.7h5.4A1.2 1.2 0 0021 20V10.2L12 3.2z" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/>
      <path d="M9 21V12h6v9"/>
    </svg>
  );
}

export function IconBook({ size = 18, className = "", filled = false }: IconProps) {
  if (filled) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
        <path d="M4 4.5A2.5 2.5 0 016.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15z" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
    </svg>
  );
}

export function IconLibrary({ size = 18, className = "", filled = false }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={filled ? 0 : 1.5} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {filled ? (
        <path d="M3 4.5A1.5 1.5 0 014.5 3h3A1.5 1.5 0 019 4.5V21H3V4.5zm7.5 1A1.5 1.5 0 0112 4h3a1.5 1.5 0 011.5 1.5V21h-6V5.5zm7.08-.23 2.9-.78 4.27 15.94-2.9.78-4.27-15.94z" />
      ) : (
        <>
          <path d="M3 4h6v17H3zM10.5 5h6v16h-6zM17.5 5l3-1 4.5 16-3 1z" />
          <path d="M5 7h2M12.5 8h2M19.2 8l2-.55" />
        </>
      )}
    </svg>
  );
}

export function IconCross({ size = 18, className = "", filled = false }: IconProps) {
  // Cross reads clearly as a filled mark; use same solid form with optional softer outline ring when inactive
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke={filled ? "none" : "currentColor"}
      strokeWidth={filled ? undefined : 1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {filled ? (
        <>
          <rect x="10.25" y="2.5" width="3.5" height="19" rx="1" />
          <rect x="5" y="6.5" width="14" height="3.5" rx="1" />
        </>
      ) : (
        <>
          <path d="M12 3.5v17" />
          <path d="M6.5 8.5h11" />
        </>
      )}
    </svg>
  );
}

export function IconAcademic({ size = 18, className = "", filled = false }: IconProps) {
  if (filled) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
        <path d="M12 3.2L2 8.2l10 5 8.2-4.1V14h1.8V8.2L12 3.2z" />
        <path d="M6 12.2v4.3c0 1.7 2.7 3.1 6 3.1s6-1.4 6-3.1v-4.3l-6 3-6-3z" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M22 10v6M2 10l10-5 10 5-10 5-10-5z"/>
      <path d="M6 12v5c0 1.657 2.686 3 6 3s6-1.343 6-3v-5"/>
    </svg>
  );
}

export function IconTranslate({ size = 18, className = "", filled = false }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={filled ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M5 8l6 6M4 6h7M2 4h8M7 4v2M5 14s-.5 1.5 2 3 4.5.5 4.5.5M15 15l5 5M15 20l5-5M20 4l-5 7.5M15 4l5 7.5"/>
    </svg>
  );
}

export function IconUser({ size = 18, className = "", filled = false }: IconProps) {
  if (filled) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6v1H4v-1z" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 0v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  );
}

export function IconSearch({ size = 18, className = "", filled = false }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={filled ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="11" cy="11" r="8"/>
      <path d="M21 21l-4.35-4.35"/>
    </svg>
  );
}

export function IconArrow({ size = 16, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M5 12h14M12 5l7 7-7 7"/>
    </svg>
  );
}

export function IconChat({ size = 18, className = "", filled = false }: IconProps) {
  if (filled) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
        <path d="M4 3h16a2 2 0 012 2v10a2 2 0 01-2 2H8l-4 4V5a2 2 0 012-2z" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
    </svg>
  );
}

export function IconQuote({ size = 20, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/>
      <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/>
    </svg>
  );
}

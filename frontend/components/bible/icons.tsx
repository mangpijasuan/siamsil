// Small stroke icons for the Bible reader (decorative: buttons carry their own labels).
type P = { size?: number };
const svg = (size: number, children: React.ReactNode, fill = "none") => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {children}
  </svg>
);
export const CloseIcon = ({ size = 20 }: P) => svg(size, <path d="M18 6 6 18M6 6l12 12" />);
export const ChevronLeft = ({ size = 20 }: P) => svg(size, <path d="m15 18-6-6 6-6" />);
export const ChevronRight = ({ size = 20 }: P) => svg(size, <path d="m9 18 6-6-6-6" />);
export const ChevronDown = ({ size = 16 }: P) => svg(size, <path d="m6 9 6 6 6-6" />);
export const SearchIcon = ({ size = 20 }: P) => svg(size, <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>);
export const SettingsIcon = ({ size = 20 }: P) => svg(size, <><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></>);
export const BookmarkIcon = ({ size = 20, filled = false }: P & { filled?: boolean }) => svg(size, <path d="M6 3h12v18l-6-4-6 4z" />, filled ? "currentColor" : "none");
export const CopyIcon = ({ size = 20 }: P) => svg(size, <><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h8" /></>);
export const ShareIcon = ({ size = 20 }: P) => svg(size, <><path d="M12 3v13" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></>);
export const NoteIcon = ({ size = 20 }: P) => svg(size, <><path d="M4 4h16v12l-4 4H4z" /><path d="M16 20v-4h4M8 9h8M8 13h5" /></>);
export const HighlightIcon = ({ size = 20 }: P) => svg(size, <><path d="m9 11-6 6v3h3l6-6" /><path d="m22 4-8.5 8.5-3-3L19 1z" /></>);
export const SunIcon = ({ size = 20 }: P) => svg(size, <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>);
export const MoonIcon = ({ size = 20 }: P) => svg(size, <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />);
export const SepiaIcon = ({ size = 20 }: P) => svg(size, <><path d="M4 19V5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2z" /><path d="M8 7h6M8 11h6" /></>);

// Reading preferences: browser-local, non-sensitive settings for the Bible reader.

export type DisplayMode = "both" | "primary" | "secondary";
export type ReadingTheme = "light" | "sepia" | "dark";
export type Typeface = "sans" | "serif";

export type ReadingPreferences = {
  mode: DisplayMode;
  theme: ReadingTheme | "system";
  fontSize: number;
  lineHeight: number;
  typeface: Typeface;
};

export const PREFERENCES_KEY = "siamsil.bible.preferences";
export const FONT_SIZE = { min: 14, max: 24, step: 1 } as const;
export const LINE_HEIGHT = { min: 1.4, max: 2.1, step: 0.1 } as const;

export const DEFAULT_PREFERENCES: ReadingPreferences = {
  mode: "both",
  theme: "system",
  fontSize: 18,
  lineHeight: 1.8,
  typeface: "sans",
};

const MODES: DisplayMode[] = ["both", "primary", "secondary"];
const THEMES: Array<ReadingPreferences["theme"]> = ["system", "light", "sepia", "dark"];
const TYPEFACES: Typeface[] = ["sans", "serif"];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

/** Round to one decimal so repeated +/- steps don't drift (1.4 + 0.1 * 3 stays 1.7). */
function round1(value: number) {
  return Math.round(value * 10) / 10;
}

/** Accept anything (stored JSON may be stale or edited) and return valid preferences. */
export function normalizePreferences(raw: unknown): ReadingPreferences {
  const value = (raw && typeof raw === "object" ? raw : {}) as Partial<Record<keyof ReadingPreferences, unknown>>;
  const fontSize = typeof value.fontSize === "number" && Number.isFinite(value.fontSize)
    ? clamp(Math.round(value.fontSize), FONT_SIZE.min, FONT_SIZE.max)
    : DEFAULT_PREFERENCES.fontSize;
  const lineHeight = typeof value.lineHeight === "number" && Number.isFinite(value.lineHeight)
    ? clamp(round1(value.lineHeight), LINE_HEIGHT.min, LINE_HEIGHT.max)
    : DEFAULT_PREFERENCES.lineHeight;
  return {
    mode: MODES.includes(value.mode as DisplayMode) ? (value.mode as DisplayMode) : DEFAULT_PREFERENCES.mode,
    theme: THEMES.includes(value.theme as ReadingPreferences["theme"]) ? (value.theme as ReadingPreferences["theme"]) : DEFAULT_PREFERENCES.theme,
    fontSize,
    lineHeight,
    typeface: TYPEFACES.includes(value.typeface as Typeface) ? (value.typeface as Typeface) : DEFAULT_PREFERENCES.typeface,
  };
}

export function stepFontSize(current: number, direction: 1 | -1) {
  return clamp(current + direction * FONT_SIZE.step, FONT_SIZE.min, FONT_SIZE.max);
}

export function stepLineHeight(current: number, direction: 1 | -1) {
  return clamp(round1(current + direction * LINE_HEIGHT.step), LINE_HEIGHT.min, LINE_HEIGHT.max);
}

/** The theme actually shown: "system" follows the device's dark-mode setting. */
export function resolveTheme(theme: ReadingPreferences["theme"], prefersDark: boolean): ReadingTheme {
  if (theme === "system") return prefersDark ? "dark" : "light";
  return theme;
}

/**
 * Inline script run before the reader paints, so saved settings apply without a flash.
 * It only reads localStorage and sets data attributes and CSS variables on <html>.
 */
export const PREFERENCES_BOOT_SCRIPT = `(function(){try{var d=${JSON.stringify(DEFAULT_PREFERENCES)};var s={};try{s=JSON.parse(localStorage.getItem(${JSON.stringify(PREFERENCES_KEY)})||"{}")||{}}catch(e){}
var t=["light","sepia","dark"].indexOf(s.theme)>=0?s.theme:(window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
var f=typeof s.fontSize==="number"?Math.min(24,Math.max(14,Math.round(s.fontSize))):d.fontSize;
var l=typeof s.lineHeight==="number"?Math.min(2.1,Math.max(1.4,s.lineHeight)):d.lineHeight;var y=s.typeface==="sans"?"sans":d.typeface;
var h=document.documentElement;h.setAttribute("data-bible-theme",t);h.setAttribute("data-bible-face",y);
h.style.setProperty("--sb-font-size",f+"px");h.style.setProperty("--sb-line-height",String(l));}catch(e){}})();`;

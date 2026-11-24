// Application appearance: Light, Dark or System. Browser-local and non-sensitive.
// The chosen mode is stored under APPEARANCE_KEY; the mode actually shown ("light" or "dark") is written to
// <html data-app-theme> before first paint by APPEARANCE_BOOT_SCRIPT, and kept in step by AppearanceSelect.

export type Appearance = "light" | "dark" | "system";
export type ResolvedAppearance = "light" | "dark";

export const APPEARANCES: readonly Appearance[] = ["light", "dark", "system"];
export const DEFAULT_APPEARANCE: Appearance = "light";
export const APPEARANCE_KEY = "siamsil-app-theme";
export const APPEARANCE_EVENT = "siamsil:appearance";
export const DARK_QUERY = "(prefers-color-scheme: dark)";

/** Accept anything stored (it may be stale or edited) and return a valid mode. */
export function normalizeAppearance(value: unknown): Appearance {
  return APPEARANCES.includes(value as Appearance) ? (value as Appearance) : DEFAULT_APPEARANCE;
}

/** The look actually shown: "system" follows the device's dark-mode setting. */
export function resolveAppearance(mode: Appearance, prefersDark: boolean): ResolvedAppearance {
  if (mode === "system") return prefersDark ? "dark" : "light";
  return mode;
}

/**
 * Inline script run while the page is parsed, so the saved mode applies before first paint (no flash of the wrong look).
 * It only reads localStorage and sets an attribute and color-scheme on <html>. Static text; no user input.
 */
export const APPEARANCE_BOOT_SCRIPT = `(function(){try{var m=${JSON.stringify(DEFAULT_APPEARANCE)};try{var s=localStorage.getItem(${JSON.stringify(APPEARANCE_KEY)});if(s==="light"||s==="dark"||s==="system")m=s}catch(e){}
var d=m==="dark"||(m==="system"&&window.matchMedia&&matchMedia(${JSON.stringify(DARK_QUERY)}).matches);
var h=document.documentElement;h.setAttribute("data-app-theme",d?"dark":"light");h.style.colorScheme=d?"dark":"light";}catch(e){}})();`;

"use client";

import { FONT_SIZE, LINE_HEIGHT, stepFontSize, stepLineHeight } from "@/lib/bible/preferences";
import type { DisplayMode, ReadingPreferences } from "@/lib/bible/preferences";
import Sheet from "./Sheet";

type Props = {
  prefs: ReadingPreferences;
  update: (change: Partial<ReadingPreferences>) => void;
  onClose: () => void;
  primaryLanguage: string;
  secondaryLanguage: string | null;
};

function Choice<T extends string>({ name, legend, value, options, onChange }: {
  name: string;
  legend: string;
  value: T;
  options: Array<{ value: T; label: string; note?: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="sb-fieldset">
      <legend className="sb-group-title">{legend}</legend>
      <div className="sb-segments">
        {options.map((option) => (
          <label key={option.value} className={`sb-segment${value === option.value ? " is-on" : ""}`}>
            <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(option.value)} />
            <span>{option.label}</span>
            {option.note && <small>{option.note}</small>}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function ReadingSettings({ prefs, update, onClose, primaryLanguage, secondaryLanguage }: Props) {
  const second = secondaryLanguage ?? "second version";
  const modes: Array<{ value: DisplayMode; label: string; note?: string }> = [
    { value: "both", label: `${primaryLanguage} + ${second}` },
    { value: "primary", label: `${primaryLanguage} only` },
    { value: "secondary", label: `${second} only`, note: secondaryLanguage ? undefined : "Choose a version to show alongside first" },
  ];
  return (
    <Sheet title="Reading settings" onClose={onClose}>
      <Choice name="sb-mode" legend="Show" value={prefs.mode} options={modes} onChange={(mode) => update({ mode })} />
      <Choice name="sb-theme" legend="Theme" value={prefs.theme} onChange={(theme) => update({ theme })}
        options={[{ value: "system", label: "Device" }, { value: "light", label: "Light" }, { value: "sepia", label: "Sepia" }, { value: "dark", label: "Dark" }]} />

      <div className="sb-fieldset">
        <span className="sb-group-title" id="sb-size-label">Text size</span>
        <div className="sb-stepper" role="group" aria-labelledby="sb-size-label">
          <button type="button" className="sb-icon-btn sb-text-btn" onClick={() => update({ fontSize: stepFontSize(prefs.fontSize, -1) })}
            disabled={prefs.fontSize <= FONT_SIZE.min} aria-label="Smaller text">A−</button>
          <output aria-live="polite">{prefs.fontSize}px</output>
          <button type="button" className="sb-icon-btn sb-text-btn sb-text-btn-lg" onClick={() => update({ fontSize: stepFontSize(prefs.fontSize, 1) })}
            disabled={prefs.fontSize >= FONT_SIZE.max} aria-label="Larger text">A+</button>
        </div>
      </div>

      <div className="sb-fieldset">
        <span className="sb-group-title" id="sb-lh-label">Line spacing</span>
        <div className="sb-stepper" role="group" aria-labelledby="sb-lh-label">
          <button type="button" className="sb-icon-btn" onClick={() => update({ lineHeight: stepLineHeight(prefs.lineHeight, -1) })}
            disabled={prefs.lineHeight <= LINE_HEIGHT.min} aria-label="Less line spacing">−</button>
          <output aria-live="polite">{prefs.lineHeight.toFixed(1)}</output>
          <button type="button" className="sb-icon-btn" onClick={() => update({ lineHeight: stepLineHeight(prefs.lineHeight, 1) })}
            disabled={prefs.lineHeight >= LINE_HEIGHT.max} aria-label="More line spacing">+</button>
        </div>
      </div>

      <Choice name="sb-face" legend="Typeface" value={prefs.typeface} onChange={(typeface) => update({ typeface })}
        options={[{ value: "sans", label: "Sans (Inter)" }, { value: "serif", label: "Serif (Playfair)" }]} />

      <p className="sb-sample" aria-hidden="true">
        <span className="sb-vnum-sample">1</span> A kipat cilin Pasian in vantung leh leitung a piangsak hi.
      </p>
      <p className="sb-muted">Settings are saved in this browser only.</p>
    </Sheet>
  );
}

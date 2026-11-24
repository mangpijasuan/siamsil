import Image from "next/image";

// The owner's Siamsil wordmark, used exactly as supplied (2172×724 PNGs, with the TECHNOLOGIES line, with transparent padding). The padding is hidden
// with CSS only — the files are not edited. White for the navy shell, navy for light surfaces.
const FILES = {
  white: { src: "/siamsil-wordmark-white.png", x: 155, y: 181, w: 1873, h: 350 },
  navy: { src: "/siamsil-wordmark-navy.png", x: 135, y: 164, w: 1917, h: 365 },
} as const;
const FULL = { w: 2172, h: 724 };

// variant "auto" follows the appearance: the white mark in Dark, the navy mark in Light (CSS switches them, so no flash).
export default function BrandWordmark({ variant = "white" }: { variant?: keyof typeof FILES | "auto" }) {
  if (variant === "auto") {
    return (
      <>
        <span className="wm-light-only"><BrandWordmark variant="navy" /></span>
        <span className="wm-dark-only"><BrandWordmark variant="white" /></span>
      </>
    );
  }
  const f = FILES[variant];
  return (
    <span className="brand-wordmark" style={{ aspectRatio: `${f.w} / ${f.h}` }}>
      <Image
        src={f.src}
        alt="Siamsil"
        width={FULL.w}
        height={FULL.h}
        priority
        unoptimized
        style={{
          position: "absolute",
          width: `${(FULL.w / f.w) * 100}%`,
          height: "auto",
          maxWidth: "none",
          left: `${(-f.x / f.w) * 100}%`,
          top: `${(-f.y / f.h) * 100}%`,
        }}
      />
    </span>
  );
}

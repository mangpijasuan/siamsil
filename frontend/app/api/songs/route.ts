import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  // The copyrighted songbook must stay in private storage. Only a server-side
  // approved catalog endpoint may supply lyrics; never embed them in git.
  const endpoint = process.env.SIAMSIL_SONGS_API_URL;
  if (!endpoint) return NextResponse.json({ songs: [] });
  try {
    const url = new URL(endpoint);
    if (url.protocol !== "https:") throw new Error("HTTPS required");
    const response = await fetch(url, {
      headers: process.env.SIAMSIL_SONGS_API_TOKEN
        ? { Authorization: `Bearer ${process.env.SIAMSIL_SONGS_API_TOKEN}` }
        : {},
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error("Upstream unavailable");
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== "object" || !("songs" in payload) || !Array.isArray(payload.songs)) throw new Error("Invalid catalog");
    return NextResponse.json({ songs: payload.songs }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Song catalog unavailable" }, { status: 503 });
  }
}

import type { MetadataRoute } from "next";

import { getBibleVersionBooks, getBibleVersions } from "@/lib/api";
import { SITE_URL, forSitemapXml, sitemapEntries } from "@/lib/site";

// Regenerated at most daily, and no more often than the API data it reads allows (lib/api caches
// responses for a minute), so Bible versions added to the API appear without a new deployment.
export const revalidate = 86400;

/**
 * Public pages, plus every chapter of the Zomi Bible versions the API serves (it serves only
 * versions cleared for display). English Bibles are left out: Siamsil adds little to them.
 * If the API is unreachable the sitemap still lists the pages.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  if (!SITE_URL) return [];
  let bibles: { id: string; books: { book_id: number; chapters: number[] }[] }[] = [];
  try {
    const zomi = (await getBibleVersions()).versions.filter((version) => version.language_iso === "ctd");
    bibles = await Promise.all(
      zomi.map(async (version) => ({ id: version.id, books: (await getBibleVersionBooks(version.id)).books })),
    );
  } catch {
    bibles = [];
  }
  return forSitemapXml(sitemapEntries(SITE_URL, bibles));
}

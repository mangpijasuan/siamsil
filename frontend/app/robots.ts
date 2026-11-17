import type { MetadataRoute } from "next";

import { SITE_URL, robotsPolicy } from "@/lib/site";

// Without SIAMSIL_SITE_URL this disallows everything, so preview builds stay out of search results.
export default function robots(): MetadataRoute.Robots {
  return robotsPolicy(SITE_URL);
}

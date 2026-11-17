# Search engines

Updated: 2026-10-27

How Siamsil tells search engines what to index, and what to do at launch. The code is in `frontend/lib/site.ts`, `frontend/app/robots.ts`, and `frontend/app/sitemap.ts`.

## The one setting

Set **`SIAMSIL_SITE_URL`** in the frontend's build environment to the public address, for example `https://siamsil.com`, next to `SIAMSIL_API_URL`.

- **With it set:**
  - `robots.txt` allows the site and names the sitemap.
  - Pages get absolute canonical links and social-preview images.
  - The home page carries schema.org `WebSite` data, which tells search engines the dictionary search is the site search.
- **Without it** (local runs, preview deployments): `robots.txt` disallows everything, the sitemap is empty, and no structured data is emitted. A half-configured deployment cannot end up in search results.

Only an `https` address is accepted.

## What is indexed

| Indexed | Not indexed, and why |
| --- | --- |
| Home, Dictionary, Translate, Bible, Bible search, Learning, Citizenship, Library, Siamsil AI | **Profile:** saved words and history are personal and live on the device (`noindex`). **`/api/`:** data, not pages. |
| Every chapter of the Zomi Bible versions the API serves, which are only versions cleared for display (TDB and TB77: about 2,400 chapters). Each chapter has its own title (e.g. "Matthai 5 — Zomi Bible (TDB)"), description, and canonical address. | **English, Falam, Hakha and Burmese Bibles:** large established sites already rank for them, and they are not Siamsil's purpose. |
| | **Individual dictionary words:** waiting on the dictionary's display rights (`DATA_RIGHTS.md`). Words are only reachable through search today. |
| | **The machine-translated corpus:** it is not reviewed Zomi, and publishing it as pages would present machine output as real Zomi. Search engines also penalize mass machine-made content. |

Titles and headings lead with what people search for: "Zomi Dictionary", "Zomi Translate", "Zomi Bible", "Learn Zomi".

## At launch

1. Deploy with `SIAMSIL_SITE_URL` set, then open `/robots.txt` and `/sitemap.xml` on the live site and check them.
2. In [Google Search Console](https://search.google.com/search-console), add the domain, verify it (a DNS record), and submit `https://<domain>/sitemap.xml`. Do the same in Bing Webmaster Tools.
3. Ask Zomi community sites, churches, and cultural organisations to link to Siamsil. For a small language, links from them matter more than anything on the page.

Ranking first for "Zomi" alone is not a realistic first goal: encyclopedias and news sites hold it. Searches like "Zomi dictionary", "Zomi Bible", "Zomi to English", and "Matthai 5 Zomi" are.

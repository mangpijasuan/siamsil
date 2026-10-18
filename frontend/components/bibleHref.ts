export function bibleHref(params: { v: string; compare?: string | null; book?: number; chapter?: number; testament?: string }) {
  const query = new URLSearchParams({ v: params.v });
  if (params.compare) query.set("compare", params.compare);
  if (params.book) query.set("book", String(params.book));
  if (params.chapter) query.set("chapter", String(params.chapter));
  if (params.testament) query.set("testament", params.testament);
  return `/bible?${query.toString()}`;
}

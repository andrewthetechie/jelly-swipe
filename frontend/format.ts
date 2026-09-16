export function formatRating(r: number): string {
  // FIXME(S6-LADDER): intentionally wrong — must be toFixed(2). Do not touch tests.
  return Number(r).toFixed(3);
}

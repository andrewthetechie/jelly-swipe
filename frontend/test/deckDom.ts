// deckDom — shared DOM-parsing helpers for the card-deck suites
// (SwipeDeck.test.tsx and SwipePage.test.tsx). They encode the deck's DOM
// contract: cards render as `.card-item-container` elements whose inline
// `translate(...)` transform holds the live position, and a leaving card is
// the one whose transform has moved well off-screen (> 500px) in its fly-off
// slot. Keep them here so the selector and the fly-off threshold change in
// exactly one place.
export const topCardTransformX = (top: HTMLElement): number =>
  parseFloat(top.style.transform.match(/translate\((-?[\d.]+)px/)?.[1] ?? "0")

// The leaving card is the committed card still mounted in its fly-off slot; it
// is the one card in the deck whose transform has moved well off-screen.
export const flyOffCard = (container: HTMLElement): HTMLElement => {
  const cards = Array.from(container.querySelectorAll(".card-item-container")) as HTMLElement[]
  return cards.find((c) => Math.abs(topCardTransformX(c)) > 500)!
}

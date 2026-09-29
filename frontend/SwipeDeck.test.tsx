// SwipeDeck.test.tsx — covers the deck module's commit choreography through its
// public interface (SwipeDeckHandle): the leaving-card lifetime (issue #360),
// stack slicing/reversal/z-index (issue #343), and the single reduced-motion
// read (issue #399). Commits are driven via `commit(direction)` and the drag
// stubs, so a wiring bug is caught by focused deck tests instead of only by
// page-level tests that re-assemble the choreography.
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import SwipeDeck from "./SwipeDeck";
import type { SwipeDeckHandle } from "./SwipeDeck";
import { makeDeck, swipeLeft, swipeRight } from "./test/fixtures";
import { flyOffCard, topCardTransformX } from "./test/deckDom";
import { stubMatchMedia } from "./test/stubMatchMedia";
import type { CardItem } from "./types";

vi.mock("./roomApi", async () => {
  const actual = await vi.importActual<typeof import("./roomApi")>("./roomApi");
  return {
    ...actual,
    fetchTrailer: vi.fn(),
    fetchCast: vi.fn(),
  };
});

// Choreography harness: renders the deck module directly with a seeded deck and
// a mocked save callback. On a successful save the card is sliced off the deck
// head (mirroring the real session flow); an "undo" button restores the most
// recently committed card to the head, so the undo/leaving-entry interplay can
// be exercised through the deck's public interface.
function ChoreographyHarness({
  deckSize,
  onDeckRef,
  onSave,
  emptyState,
}: {
  deckSize: number
  onDeckRef: (ref: SwipeDeckHandle | null) => void
  onSave: (card: CardItem, direction: "left" | "right") => void | Promise<void>
  emptyState?: JSX.Element | null
}) {
  const [deck, setDeck] = useState(makeDeck(deckSize));
  const committedRef = useRef<CardItem[]>([]);

  const handleSave = async (card: CardItem, direction: "left" | "right") => {
    await onSave(card, direction);
    committedRef.current.push(card);
    setDeck((prev) => prev.filter((c) => c.mediaId !== card.mediaId));
  };

  const undo = () => {
    const card = committedRef.current.pop();
    if (!card) return;
    setDeck((prev) => [card, ...prev.filter((c) => c.mediaId !== card.mediaId)]);
  };

  return (
    <>
      <SwipeDeck ref={(ref) => onDeckRef(ref)} deck={deck} onSave={handleSave} emptyState={emptyState} />
      <button type="button" onClick={undo}>undo</button>
    </>
  );
}

describe("SwipeDeck — reduced-motion derivation (issue #399)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("threads the 0.15s resting and exit transitions from one reduced-motion read", async () => {
    stubMatchMedia(true);
    const onSave = vi.fn().mockResolvedValue(undefined);
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={(ref) => (deckRef = ref)} onSave={onSave} />,
    );

    // The top card's resting/snap-back transition is the reduced-motion duration
    // (150ms → 0.15s), derived from the single matchMedia read in the deck.
    const top = container.querySelector(".card-item-container") as HTMLElement;
    expect(top.style.transition).toBe("transform 0.15s ease, filter 0.15s ease");

    // Commit through the deck's imperative surface: the leaving card's inline
    // exit transition uses the same reduced-motion duration (0.15s).
    act(() => deckRef?.commit("right"));

    // The leaving card is the only one with the exit transition (no filter arm).
    await act(async () => {});
    const leaving = Array.from(container.querySelectorAll(".card-item-container"))
      .find((c) => (c as HTMLElement).style.transition === "transform 0.15s ease") as HTMLElement;
    expect(leaving).toBeTruthy();
    expect(leaving.style.transition).toBe("transform 0.15s ease");

    // The reduced-motion unmount hold is also 150ms (hold ≥ animation, decision
    // 5) — the leaving card unmounts once it elapses.
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(1);
  });
});

describe("SwipeDeck — card-stack slicing", () => {
  it("renders at most 3 cards (visibleCards = deck.slice(0,3)) in reverse order", () => {
    const { container } = render(
      <ChoreographyHarness deckSize={7} onDeckRef={() => {}} onSave={vi.fn()} />,
    );
    const cards = container.querySelectorAll(".card-item-container");
    expect(cards).toHaveLength(3);

    const titles = Array.from(cards).map(
      (c) => c.querySelector(".card-item-title")?.textContent,
    );
    expect(titles).toEqual(["Movie 3", "Movie 2", "Movie 1"]);
  });

  it("renders every card when the deck is smaller than 3", () => {
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={() => {}} onSave={vi.fn()} />,
    );
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(2);
  });
});

describe("SwipeDeck — card-stack depth (issue #343)", () => {
  it("marks only the top card as interactive and the back cards as dimmed stack", () => {
    const { container } = render(
      <ChoreographyHarness deckSize={7} onDeckRef={() => {}} onSave={vi.fn()} />,
    );
    const cards = Array.from(container.querySelectorAll(".card-item-container"));
    // Rendered reversed: index 0 is deepest (stackIndex 2), last is top (stackIndex 0).
    expect(cards).toHaveLength(3);

    const top = cards[2] as HTMLElement;
    const mid = cards[1] as HTMLElement;
    const deep = cards[0] as HTMLElement;

    // Top card: interactive, full shadow, no dim/stack class.
    expect(top.style.pointerEvents).toBe("auto");
    expect(top).not.toHaveClass("stack-back");
    expect(top.style.filter).toBe("");

    // Back cards: non-interactive and stacked.
    expect(mid.style.pointerEvents).toBe("none");
    expect(deep.style.pointerEvents).toBe("none");
    expect(mid).toHaveClass("stack-back");
    expect(deep).toHaveClass("stack-back");
  });

  it("orders back-card transforms and brightness by depth", () => {
    // Assert the ordering pattern (deeper = more offset, less scale, less brightness),
    // not exact pixel values — those may be fine-tuned without breaking the intent.
    // Back cards are pushed *up* out of the top card's outline, so the offset
    // is a negative percentage; deeper cards sit further up.
    const parseTranslateY = (transform: string) =>
      parseFloat(transform.match(/translateY\(([^%]+)%\)/)?.[1] ?? "0");
    const parseScale = (transform: string) =>
      parseFloat(transform.match(/scale\(([^)]+)\)/)?.[1] ?? "1");
    const parseBrightness = (filter: string) =>
      parseFloat(filter.match(/brightness\(([^)]+)\)/)?.[1] ?? "1");

    const { container } = render(
      <ChoreographyHarness deckSize={7} onDeckRef={() => {}} onSave={vi.fn()} />,
    );
    const cards = Array.from(container.querySelectorAll(".card-item-container")) as HTMLElement[];
    // cards[0] = stackIndex 2 (deepest), cards[1] = stackIndex 1, cards[2] = stackIndex 0 (top).

    const deep = cards[0];
    const mid = cards[1];
    const top = cards[2];

    // Top card has no stack offset/filter.
    expect(top.style.transform).not.toContain("translateY");
    expect(top.style.filter).toBe("");

    // Offset grows with depth (further up, so more negative).
    expect(parseTranslateY(mid.style.transform)).toBeLessThan(0);
    expect(parseTranslateY(deep.style.transform)).toBeLessThan(parseTranslateY(mid.style.transform));

    // Scale shrinks with depth.
    expect(parseScale(mid.style.transform)).toBeLessThan(1);
    expect(parseScale(deep.style.transform)).toBeLessThan(parseScale(mid.style.transform));

    // Brightness dims with depth.
    expect(parseBrightness(mid.style.filter)).toBeLessThan(1);
    expect(parseBrightness(deep.style.filter)).toBeLessThan(parseBrightness(mid.style.filter));
  });

  it("renders a single-card deck as just a top card with no phantom stack", () => {
    const { container } = render(
      <ChoreographyHarness deckSize={1} onDeckRef={() => {}} onSave={vi.fn()} />,
    );
    const cards = container.querySelectorAll(".card-item-container");
    expect(cards).toHaveLength(1);
    expect(cards[0]).not.toHaveClass("stack-back");
  });
});

describe("SwipeDeck — leaving card (issue #360)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps the committed card mounted as a non-interactive leaving card flying off-screen", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={(r) => (deckRef = r)} onSave={onSave} />,
    );

    act(() => deckRef?.commit("right"));
    await act(async () => {});

    // The committed card (Movie 1) is still mounted, flying off-screen.
    await waitFor(() => {
      const leaving = flyOffCard(container);
      expect(leaving.querySelector(".card-item-title")?.textContent).toBe("Movie 1");
      expect(Math.abs(topCardTransformX(leaving))).toBeGreaterThan(500);
    });

    // The leaving card is non-interactive so it can't swallow pointers.
    expect(flyOffCard(container).style.pointerEvents).toBe("none");

    // The new top card (Movie 2) is already mounted and interactive.
    const top = container.querySelector(".card-item-container") as HTMLElement;
    expect(top.style.pointerEvents).toBe("auto");
    expect(top.querySelector(".card-item-title")?.textContent).toBe("Movie 2");
  });

  it("removes the leaving card after the normal-mode exit hold (400ms)", async () => {
    vi.useFakeTimers();
    const onSave = vi.fn().mockResolvedValue(undefined);
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={(r) => (deckRef = r)} onSave={onSave} />,
    );

    act(() => deckRef?.commit("right"));
    await act(async () => {});

    // The leaving card is mounted mid-exit.
    expect(flyOffCard(container)).toBeTruthy();

    // After the 400ms hold (normal mode), the leaving card unmounts — only the
    // new top card (Movie 2) remains in the deck.
    act(() => {
      vi.advanceTimersByTime(400);
    });
    const cards = Array.from(container.querySelectorAll(".card-item-container"));
    expect(cards).toHaveLength(1);
    expect(cards[0].querySelector(".card-item-title")?.textContent).toBe("Movie 2");
  });

  it("keeps the final committed card flying over the empty state after the deck empties", async () => {
    vi.useFakeTimers();
    const onSave = vi.fn().mockResolvedValue(undefined);
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness
        deckSize={1}
        onDeckRef={(r) => (deckRef = r)}
        onSave={onSave}
        emptyState={<div className="deck-end">Deck finished</div>}
      />,
    );

    act(() => deckRef?.commit("right"));
    await act(async () => {});

    // The single card commit empties the deck, so the empty-state node renders.
    const emptyStateNode = container.querySelector(".deck-end");
    expect(emptyStateNode).toBeTruthy();

    // Movie 1 is still mounted as exactly one non-interactive leaving card
    // flying off-screen over the empty-state node.
    const leaving = flyOffCard(container);
    expect(leaving.querySelector(".card-item-title")?.textContent).toBe("Movie 1");
    expect(Math.abs(topCardTransformX(leaving))).toBeGreaterThan(500);
    expect(leaving.style.pointerEvents).toBe("none");
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(1);

    // The leaving card appears after the empty-state node in DOM order.
    const children = Array.from(container.children);
    const emptyIndex = children.indexOf(emptyStateNode as HTMLElement);
    const leavingIndex = children.indexOf(leaving);
    expect(emptyIndex).toBeGreaterThanOrEqual(0);
    expect(leavingIndex).toBeGreaterThan(emptyIndex);

    // Once the 400ms hold elapses, the leaving card unmounts.
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(0);
  });

  it("undo restores a mid-exit card to the deck head and drops its leaving entry", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={(r) => (deckRef = r)} onSave={onSave} />,
    );

    act(() => deckRef?.commit("right"));
    await act(async () => {});
    await waitFor(() => expect(flyOffCard(container)).toBeTruthy());

    // Undo while the committed card is still exiting.
    await user.click(screen.getByRole("button", { name: /undo/i }));

    // Movie 1 is restored to the deck head (top card, interactive) — Movie 2
    // is the back card.
    const top = Array.from(container.querySelectorAll(".card-item-container"))
      .find((c) => (c as HTMLElement).style.pointerEvents === "auto") as HTMLElement;
    expect(top.querySelector(".card-item-title")?.textContent).toBe("Movie 1");

    // …and its leaving entry is gone — no ghost duplicate still flying.
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(2);
    const flying = Array.from(container.querySelectorAll(".card-item-container"))
      .filter((c) => Math.abs(topCardTransformX(c as HTMLElement)) > 500);
    expect(flying).toHaveLength(0);
  });

  it("rapid consecutive swipes each get their own leaving card and keep the top card interactive", async () => {
    vi.useFakeTimers();
    const onSave = vi.fn().mockResolvedValue(undefined);
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={3} onDeckRef={(r) => (deckRef = r)} onSave={onSave} />,
    );

    // Two quick swipes: Movie 1 then Movie 2, both leave while Movie 3 is top.
    act(() => deckRef?.commit("right"));
    await act(async () => {});
    act(() => deckRef?.commit("right"));
    await act(async () => {});

    // Two distinct leaving cards fly off at once (uniquely keyed). Fake timers
    // keep both 400ms removal holds pending, so the entries stay mounted
    // deterministically (no real-time race between the commits and the assert).
    const leaving = Array.from(container.querySelectorAll(".card-item-container"))
      .filter((c) => Math.abs(topCardTransformX(c as HTMLElement)) > 500);
    expect(leaving).toHaveLength(2);

    // The new top card (Movie 3) stays interactive.
    const top = container.querySelector(".card-item-container") as HTMLElement;
    expect(top.style.pointerEvents).toBe("auto");
    expect(top.querySelector(".card-item-title")?.textContent).toBe("Movie 3");

    expect(onSave).toHaveBeenNthCalledWith(1, expect.objectContaining({ mediaId: "1" }), "right");
    expect(onSave).toHaveBeenNthCalledWith(2, expect.objectContaining({ mediaId: "2" }), "right");
  });

  it("continues a drag-past-threshold commit from the dragged transform (no teleport to centre)", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={() => {}} onSave={onSave} />,
    );
    const cards = container.querySelectorAll(".card-item-container");
    const topCard = cards[cards.length - 1] as HTMLElement;

    await swipeRight(topCard);

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ mediaId: "1" }), "right");

    // The leaving card continues from the committed card's drag-derived
    // transform: rotation is dragDistance / 5 (250 / 5 = 50), not the
    // button/keyboard path's ±12, and x is already at the fly-off distance —
    // it never restarts from translate x = 0. jsdom jumps styles to each set
    // value (see the rejected-save comment), so the rendered transform is
    // deterministic.
    const leaving = flyOffCard(container);
    expect(leaving.querySelector(".card-item-title")?.textContent).toBe("Movie 1");
    expect(topCardTransformX(leaving)).toBeGreaterThan(500);
    expect(leaving.style.transform).toContain("rotate(50deg)");
  });

  it("continues a drag-past-threshold left commit from the dragged transform", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={() => {}} onSave={onSave} />,
    );
    const cards = container.querySelectorAll(".card-item-container");
    const topCard = cards[cards.length - 1] as HTMLElement;

    await swipeLeft(topCard);

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ mediaId: "1" }), "left");

    const leaving = flyOffCard(container);
    expect(leaving.querySelector(".card-item-title")?.textContent).toBe("Movie 1");
    expect(topCardTransformX(leaving)).toBeLessThan(-500);
    expect(leaving.style.transform).toContain("rotate(-50deg)");
  });

  it("never renders the leaving card at translate x = 0 when a slow POST resolves", async () => {
    let resolveSwipe!: () => void;
    const onSave = vi
      .fn()
      .mockImplementationOnce(() => new Promise<void>((resolve) => { resolveSwipe = resolve }));
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={(r) => (deckRef = r)} onSave={onSave} />,
    );

    act(() => deckRef?.commit("right"));
    await act(async () => {});

    // POST still pending: the deck has not sliced and no leaving entry exists.
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(2);

    await act(async () => {
      resolveSwipe();
    });

    // The leaving card mounts already carrying the committed card's transform —
    // never at translate x = 0 — so the exit continues instead of restarting
    // from rest under latency.
    const leaving = flyOffCard(container);
    expect(leaving.querySelector(".card-item-title")?.textContent).toBe("Movie 1");
    expect(topCardTransformX(leaving)).not.toBe(0);
    expect(Math.abs(topCardTransformX(leaving))).toBeGreaterThan(500);
  });

  it("seeds the leaving card from the committed card's live mid-flight transform when a deferred POST resolves mid-transition", async () => {
    let resolveSwipe!: () => void;
    const onSave = vi
      .fn()
      .mockImplementationOnce(() => new Promise<void>((resolve) => { resolveSwipe = resolve }));

    // jsdom applies CSS transforms instantly, so the capture seam would read the
    // committed card at its final commit transform instead of a mid-transition
    // value. Stub `getComputedStyle` so the capture returns a deterministic
    // MID-TRANSITION transform for the committed card: x=400 (past centre, well
    // short of the 832px fly-off target) and rotation 30deg.
    const originalGetComputedStyle = window.getComputedStyle;
    const getComputedStyleSpy = vi
      .spyOn(window, "getComputedStyle")
      .mockImplementation((el: Element) => {
        const style = originalGetComputedStyle(el);
        if (el.classList.contains("card-item-container")) {
          // matrix(a, b, c, d, e, f): x=e=400, rotation=atan2(b,a)=30deg.
          return { ...style, transform: "matrix(0.8660254, 0.5, -0.5, 0.8660254, 400, 0)" } as CSSStyleDeclaration;
        }
        return style;
      });

    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={(r) => (deckRef = r)} onSave={onSave} />,
    );

    act(() => deckRef?.commit("right"));
    await act(async () => {});

    // POST still pending: the deck has not sliced and no leaving entry exists.
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(2);

    await act(async () => {
      resolveSwipe();
    });

    // The leaving card mounts at the captured mid-flight position (x=400, not
    // x=0 and not the 832px commit target) and the exit mount effect animates it
    // forward to the fly-off target. jsdom runs the mount effect immediately, so
    // the rendered transform is the fly-off target — the mid-flight seeding is
    // proven by the effect having run at all: rotation is the effect's 12, not
    // the held commit-target rotation (30) the guard suppresses for a from that
    // is already at/past the target.
    const leaving = flyOffCard(container);
    expect(leaving.querySelector(".card-item-title")?.textContent).toBe("Movie 1");
    expect(topCardTransformX(leaving)).toBe(832);
    expect(leaving.style.transform).toContain("rotate(12deg)");

    getComputedStyleSpy.mockRestore();
  });

  it("adds nothing to the leaving slot when the save rejects", async () => {
    const onSave = vi.fn().mockRejectedValue(new Error("save failed"));
    let deckRef: SwipeDeckHandle | null = null;
    const { container } = render(
      <ChoreographyHarness deckSize={2} onDeckRef={(r) => (deckRef = r)} onSave={onSave} />,
    );

    act(() => deckRef?.commit("right"));
    await act(async () => {});

    // The rejected save slices nothing and records no leaving entry — the swiped
    // card stays mounted and retryable, and the leaving slot stays empty.
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ mediaId: "1" }), "right");
    const cards = Array.from(container.querySelectorAll(".card-item-container"));
    expect(cards).toHaveLength(2);
    const flying = cards.filter((c) => Math.abs(topCardTransformX(c as HTMLElement)) > 500);
    expect(flying).toHaveLength(0);
  });
});

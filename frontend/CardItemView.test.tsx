// CardItemView.test.tsx — covers the card's *derived display* and its non-drag
// flip, and DOCUMENTS (rather than rewrites) the parts that are hard to test or
// known to be buggy. This file is the canonical example for two patterns:
//
//   • "hard-to-test, documented" — the pointer-drag path (see the skipped drag
//     stub near the bottom), which jsdom can't fully drive.
//   • "skipped desired-behaviour" — the rating-zero known bug, asserted as the
//     CORRECT behaviour and skipped, so fixing the bug turns the test green
//     instead of red. We never assert the current buggy output.
//
// Both front and back faces of the card are always in the DOM (CSS handles the
// visual flip), so we can query back-face text like "IMDb 7.50" without
// simulating the flip. CardItem doesn't read context, but we render it through
// `renderWithRoom` for consistency with the rest of the suite; `setDragX` is a
// throwaway `vi.fn()` since these tests don't drag.
import { fireEvent, screen } from "@testing-library/react";
import CardItemView from "./CardItemView";
import { renderWithRoom } from "./test/renderWithRoom";
import { makeCard, swipeRight, swipeLeft, swipeUnderThreshold } from "./test/fixtures";

// Small helper: render a card with the required props filled in, overriding
// only the card fields a given test cares about.
function renderCard(cardOverrides = {}) {
  return renderWithRoom(
    <CardItemView
      cardItem={makeCard(cardOverrides)}
      setDragX={vi.fn()}
      stackIndex={0}
      zIndex={0}
      onSwipe={vi.fn()}
    />,
  );
}

// Render a card at a given stack depth (0 = top card, see issue #343).
function renderStackCard(stackIndex = 0) {
  return renderWithRoom(
    <CardItemView
      cardItem={makeCard()}
      setDragX={vi.fn()}
      stackIndex={stackIndex}
      zIndex={stackIndex}
      onSwipe={vi.fn()}
    />,
  );
}

describe("CardItemView — derived display (mediaText)", () => {
  it("maps mediaType 'movie' to 'Movie'", () => {
    const { container } = renderCard({ mediaType: "movie", seasonCount: undefined });
    expect(container.querySelector(".media-type")?.textContent).toBe("Movie");
  });

  it("maps mediaType 'tv_show' to 'TV' (backend-confirmed value, not a bug)", () => {
    const { container } = renderCard({ mediaType: "tv_show", seasonCount: undefined });
    expect(container.querySelector(".media-type")?.textContent).toBe("TV");
  });

  it("renders empty media text for any other mediaType", () => {
    const { container } = renderCard({ mediaType: "podcast", seasonCount: undefined });
    expect(container.querySelector(".media-type")?.textContent).toBe("");
  });
});

describe("CardItemView — derived display (seasonsText)", () => {
  // seasonsText is only meaningful behind the `seasonCount !== undefined` guard.
  it("uses the singular 'Season' for a count of 1", () => {
    const { container } = renderCard({ mediaType: "tv_show", seasonCount: 1 });
    expect(container.querySelector(".media-type")?.textContent).toContain("1 Season");
    expect(container.querySelector(".media-type")?.textContent).not.toContain("Seasons");
  });

  it("uses the plural 'Seasons' for a count greater than 1", () => {
    const { container } = renderCard({ mediaType: "tv_show", seasonCount: 2 });
    expect(container.querySelector(".media-type")?.textContent).toContain("2 Seasons");
  });

  it("renders no seasons text when seasonCount is undefined", () => {
    const { container } = renderCard({ mediaType: "tv_show", seasonCount: undefined });
    expect(container.querySelector(".media-type")?.textContent).toBe("TV");
  });
});

// later - combine these tests with flip toggle tests --> is unflipped and not rendered, is flipped and rendered
describe("CardItemView - ActorElements", () => {
  it("does not render ActorElements before the card is flipped", () => {
    renderCard()

    expect(
      screen.queryByTestId("actor-elements")
    ).not.toBeInTheDocument()
  })

  it("renders ActorElements after the card is flipped", async () => {
    const { container } = renderCard()
    const card = container.querySelector(
      ".card-item-container"
    ) as HTMLElement

    fireEvent.click(card)

    expect(
      screen.getByTestId("actor-elements")
    ).toBeInTheDocument()
  })
})

describe("CardItemView — rating formatting", () => {
  it("formats rating with toFixed(2): 7.5 → 'IMDb 7.50'", () => {
    renderCard({ rating: 7.5 });
    expect(screen.getByText("IMDb 7.50")).toBeInTheDocument();
  });
});

describe("CardItemView — poster", () => {
  it("renders the poster with the title as alt text and the apiUrl src", () => {
    const posterUrl = "/proxy?path=/poster.jpg";
    renderCard({ title: "Moana", posterUrl });
    const img = screen.getByAltText("Moana") as HTMLImageElement;
    // src is built via apiUrl(posterUrl).toString(); compute the same way so the
    // assertion is robust to whatever base URL the test env resolves.
    expect(img.getAttribute("src")).toBe(posterUrl);
  });

  it("falls back to the sad image + note when there is no posterUrl", () => {
    renderCard({ title: "Moana", posterUrl: undefined });
    // The image still renders (with the fallback asset) and keeps its alt text…
    expect(screen.getByAltText("Moana")).toBeInTheDocument();
    // …and the "No poster available" note appears only in the no-posterUrl branch.
    expect(screen.getByText("No poster available")).toBeInTheDocument();
  });
});

describe("CardItem — flip toggle (non-drag click)", () => {
  it("toggles the 'flipped' class on the container in both directions", () => {
    const { container } = renderCard();
    const card = container.querySelector(".card-item-container") as HTMLElement;

    // Starts un-flipped.
    expect(card).not.toHaveClass("flipped");

    // A plain click (no drag, so hasDragged is false) flips it…
    fireEvent.click(card);
    expect(card).toHaveClass("flipped");

    // …and clicking again flips it back.
    fireEvent.click(card);
    expect(card).not.toHaveClass("flipped");
  });
});

describe("CardItemView — Watch Trailer label casing", () => {
  // Guards the AC "no all-caps button labels" — case-sensitive on purpose, so a
  // revert to "WATCH TRAILER" fails here (the /watch trailer/i queries elsewhere
  // are case-insensitive and would not catch it).
  it("renders a mixed-case label, never an all-caps one", () => {
    const { container } = renderCard();
    const label = container
      .querySelector("button.watch-trailer")!
      .textContent!.trim();
    expect(label).toBe("Watch Trailer");
  });
});

// Eventually, the Watch Trailer button should also open the trailer div and display the video
// For now, this test just asserts that clicking the button doesn't flip the card

describe("CardItemView - clicking Watch Trailer does not flip the card", () => {
  it("does not toggle the 'flipped' class when the trailer button is clicked", () => {
    const { container } = renderCard()
    const card = container.querySelector(".card-item-container") as HTMLElement
    const trailerButton = screen.getByRole("button", { name: /watch trailer/i })

    // Starts un-flipped.
    expect(card).not.toHaveClass("flipped")

    // Click the card to flip it.
    fireEvent.click(card)
    expect(card).toHaveClass("flipped")

    // Click the trailer button.
    fireEvent.click(trailerButton)

    // The card should not flipped.
    expect(card).toHaveClass("flipped")
  })
})

describe("CardItemView — rating === 0", () => {
  it("shows 'IMDb 0.00' and no stray '0' for a zero rating", () => {
    const { container } = renderCard({ rating: 0 })
    expect(screen.getByText("IMDb 0.00")).toBeInTheDocument()

    const directText = Array.from(
      container.querySelector(".card-item-info")?.childNodes ?? [],
    )
      .filter((n) => n.nodeType === Node.TEXT_NODE)
      .map((n) => n.textContent?.trim())
      .filter(Boolean)
    expect(directText).not.toContain("0")
  })
})

describe("CardItemView - swipe behavior", () => {
  it("calls onSwipe with the correct card and direction - right", async () => {
    const onSwipe = vi.fn()
    const { container } = renderWithRoom(
      <CardItemView
        cardItem={makeCard()}
        setDragX={vi.fn()}
        stackIndex={0}
        zIndex={0}
        onSwipe={onSwipe}
      />,
      { currentRoomCode: "1234" }
    )

    const topCard = container.querySelector(".card-item-container") as HTMLElement
    swipeRight(topCard)

    expect(onSwipe).toHaveBeenCalledWith(
      expect.objectContaining({
        mediaId: "1",
      }),
      "right"
    )
  })

  it("calls onSwipe with the correct card and direction - left", async () => {
    const onSwipe = vi.fn()
    const { container } = renderWithRoom(
      <CardItemView
        cardItem={makeCard()}
        setDragX={vi.fn()}
        stackIndex={0}
        zIndex={0}
        onSwipe={onSwipe}
      />,
      { currentRoomCode: "1234" }
    )

    const topCard = container.querySelector(".card-item-container") as HTMLElement
    swipeLeft(topCard)

    expect(onSwipe).toHaveBeenCalledWith(
      expect.objectContaining({
        mediaId: "1",
      }),
      "left"
    )
  })

  it("does not call onSwipe when the swipe does not pass the threshold", async () => {
    const onSwipe = vi.fn()
    const { container } = renderWithRoom(
      <CardItemView
        cardItem={makeCard()}
        setDragX={vi.fn()}
        stackIndex={0}
        zIndex={0}
        onSwipe={onSwipe}
      />,
      { currentRoomCode: "1234" }
    )

    const topCard = container.querySelector(".card-item-container") as HTMLElement
    swipeUnderThreshold(topCard)

    expect(onSwipe).not.toHaveBeenCalled()
  })
})

describe("CardItemView — stack depth (issue #343)", () => {
  it("treats stackIndex 0 as the interactive top card with no stack styling", () => {
    const { container } = renderStackCard(0)
    const card = container.querySelector(".card-item-container") as HTMLElement
    expect(card.style.pointerEvents).toBe("auto")
    expect(card).not.toHaveClass("stack-back")
    expect(card.style.filter).toBe("")
    expect(card.style.transform).not.toContain("translateY")
    expect(card.style.transform).not.toContain("scale")
  })

  it("marks stackIndex > 0 as non-interactive with the stack-back class", () => {
    const { container } = renderStackCard(1)
    const card = container.querySelector(".card-item-container") as HTMLElement
    expect(card.style.pointerEvents).toBe("none")
    expect(card).toHaveClass("stack-back")
  })

  it("applies depth-ordered offset, scale, and brightness to back cards", () => {
    const { container: c1 } = renderStackCard(1)
    const back1 = c1.querySelector(".card-item-container") as HTMLElement
    expect(back1.style.transform).toContain("translateY(10px)")
    expect(back1.style.transform).toContain("scale(0.96)")
    expect(back1.style.filter).toBe("brightness(0.9)")

    const { container: c2 } = renderStackCard(2)
    const back2 = c2.querySelector(".card-item-container") as HTMLElement
    expect(back2.style.transform).toContain("translateY(20px)")
    expect(back2.style.transform).toContain("scale(0.92)")
    expect(back2.style.filter).toBe("brightness(0.8)")
  })
})

// --- Documented gaps: do NOT rewrite the source to make these testable -------

describe("CardItem — pointer drag (documented, hard to test)", () => {
  // WHY THIS IS SKIPPED, not deleted:
  // The drag gesture relies on the Pointer Capture API
  // (setPointerCapture / releasePointerCapture) and real PointerEvents, which
  // jsdom does not fully implement. test/setup.ts stubs the capture methods so
  // firing pointer events doesn't *crash*, but jsdom still won't reproduce a
  // genuine drag (pointer coordinates, capture semantics, the transition/
  // transform animation), so asserting "card slid off-screen on a 130px drag"
  // here would be testing the stub, not the component.
  //
  // WHAT WOULD MAKE IT TESTABLE LATER (for whoever refactors this):
  //   • extract the pointer math into a pure function (input deltaX → output
  //     position) and unit-test THAT directly, leaving the DOM wiring thin; or
  //   • cover the real gesture with an end-to-end test (Playwright/Cypress) in
  //     a real browser where Pointer Capture actually works.
  it.skip("slides the card off-screen when dragged past the swipe threshold", () => {
    // Intentionally left unimplemented — see the comment above.
  });
});

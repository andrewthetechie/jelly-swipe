import React from "react";

// Entry-modal harnesses for the shared membership-store lifetime tests.
//
// The membership store lives for the whole RoomContextProvider lifetime, so a
// close-then-reopen (or a swap from one entry modal to the other) within one
// render tree keeps the same store instance — exactly what the stale-error
// regression tests need to reproduce.

type ModalRenderer = (onClose: () => void) => React.ReactNode;

/** Mounts the modal, unmounts it on close, and remounts it on "reopen". */
export function ModalReopenHarness({ renderModal }: { renderModal: ModalRenderer }) {
  const [show, setShow] = React.useState(true);
  return (
    <div>
      <button onClick={() => setShow(true)}>reopen</button>
      {show && renderModal(() => setShow(false))}
    </div>
  );
}

/** Closing the first modal opens the second, inside the same provider tree. */
export function ModalSwapHarness({ first, second }: { first: ModalRenderer; second: ModalRenderer }) {
  const [showSecond, setShowSecond] = React.useState(false);
  const close = () => setShowSecond((prev) => !prev);
  return <>{showSecond ? second(close) : first(close)}</>;
}

import { render, screen } from "@testing-library/react";
import FormError from "./FormError";

describe("FormError", () => {
  it("renders the message with role='alert' and class 'form-error'", () => {
    render(<FormError message="Something went wrong" />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveClass("form-error");
    expect(alert).toHaveTextContent("Something went wrong");
  });
});

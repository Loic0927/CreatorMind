import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AiConsentDialog } from "./AiConsentDialog";

afterEach(cleanup);

describe("AiConsentDialog", () => {
  it("explains the Google Gemini data use before accepting", async () => {
    const accept = vi.fn();
    const user = userEvent.setup();
    render(<AiConsentDialog open onAccept={accept} onNotNow={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Review AI data use" })).toBeInTheDocument();
    expect(screen.getByText(/Google Gemini API/i)).toBeInTheDocument();
    expect(screen.getByText(/post media and captions/i)).toBeInTheDocument();
    expect(screen.getByText(/audience comment text/i)).toBeInTheDocument();
    expect(screen.getByText(/performance facts/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Accept" }));
    expect(accept).toHaveBeenCalledOnce();
  });
});

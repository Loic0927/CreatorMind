import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoginScreen } from "./LoginScreen";
import { requestCode, verifyCode } from "@/lib/postbridge";

vi.mock("@/lib/postbridge", () => ({
  requestCode: vi.fn(),
  verifyCode: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LoginScreen", () => {
  it("does not create a new account until legal and AI processing consent are checked", async () => {
    const user = userEvent.setup();
    const onLogin = vi.fn();
    const session = {
      accessToken: "token",
      expiresAt: "2099-01-01T00:00:00Z",
      user: { id: "user-1", email: "new@example.com", ai_processing_consented: true },
    };
    vi.mocked(requestCode).mockResolvedValue({ sent: true, development_code: "123456" });
    vi.mocked(verifyCode).mockResolvedValue(session);

    render(<LoginScreen onLogin={onLogin} />);
    await user.click(screen.getByRole("button", { name: "Create account" }));
    await user.type(screen.getByLabelText("Email"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Email me a code" }));

    expect(await screen.findByLabelText("Verification code")).toHaveValue("123456");
    await user.click(screen.getByRole("button", { name: "Review and create account" }));

    expect(screen.getByRole("dialog", { name: "Privacy, Terms & AI processing" })).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Agree and create account" });
    expect(confirm).toBeDisabled();
    expect(verifyCode).not.toHaveBeenCalled();

    await user.click(screen.getByRole("checkbox", { name: /read and agree to the Privacy Policy/i }));
    expect(confirm).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /agree to the AI processing/i }));
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    await waitFor(() =>
      expect(verifyCode).toHaveBeenCalledWith("new@example.com", "123456", {
        intent: "sign_up",
        privacyTermsAccepted: true,
        aiProcessingConsent: true,
      }),
    );
    expect(onLogin).toHaveBeenCalledWith(session);
  });

  it("uses sign-in intent for an existing account", async () => {
    const user = userEvent.setup();
    const session = {
      accessToken: "token",
      expiresAt: "2099-01-01T00:00:00Z",
      user: { id: "user-1", email: "member@example.com" },
    };
    vi.mocked(requestCode).mockResolvedValue({ sent: true, development_code: "654321" });
    vi.mocked(verifyCode).mockResolvedValue(session);

    render(<LoginScreen onLogin={vi.fn()} />);
    await user.type(screen.getByLabelText("Email"), "member@example.com");
    await user.click(screen.getByRole("button", { name: "Email me a code" }));
    await user.click(await screen.findByRole("button", { name: "Verify and sign in" }));

    expect(verifyCode).toHaveBeenCalledWith("member@example.com", "654321", { intent: "sign_in" });
  });
});

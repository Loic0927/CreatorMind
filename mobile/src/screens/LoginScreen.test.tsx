import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Login } from "../../App";
import { requestLoginCode, verifyLoginCode } from "../services/auth";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn(), maybeCompleteAuthSession: jest.fn() }));
jest.mock("../services/auth", () => ({
  getSession: jest.fn().mockResolvedValue(null),
  logout: jest.fn(),
  requestLoginCode: jest.fn(),
  verifyLoginCode: jest.fn(),
}));

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 44, left: 0, right: 0, bottom: 34 },
};

describe("mobile Login", () => {
  beforeEach(() => jest.clearAllMocks());

  it("requires legal and AI consent before sign-up verification", async () => {
    const onLogin = jest.fn();
    const session = {
      accessToken: "token",
      expiresAt: "2099-01-01T00:00:00Z",
      user: { id: "user-1", email: "new@example.com", ai_processing_consented: true },
    };
    jest.mocked(requestLoginCode).mockResolvedValue({ developmentCode: "123456" });
    jest.mocked(verifyLoginCode).mockResolvedValue(session);
    const view = await render(
      <SafeAreaProvider initialMetrics={metrics}>
        <Login onLogin={onLogin} />
      </SafeAreaProvider>,
    );

    await fireEvent.press(view.getByRole("button", { name: "Create account" }));
    await fireEvent.changeText(view.getByLabelText("Email"), "new@example.com");
    await fireEvent.press(view.getByRole("button", { name: "Email me a code" }));
    expect(requestLoginCode).toHaveBeenCalledWith("new@example.com", "sign_up");
    expect(await view.findByDisplayValue("123456")).toBeTruthy();
    await fireEvent.press(view.getByRole("button", { name: "Review and create account" }));

    const confirm = view.getByRole("button", { name: "Agree and create account" });
    expect(confirm.props.accessibilityState?.disabled ?? confirm.props.disabled).toBeTruthy();
    expect(verifyLoginCode).not.toHaveBeenCalled();

    await fireEvent.press(view.getByRole("checkbox", { name: /read and agree to the Privacy Policy/i }));
    await fireEvent.press(view.getByRole("checkbox", { name: /agree to the AI processing/i }));
    await fireEvent.press(view.getByRole("button", { name: "Agree and create account" }));

    await waitFor(() =>
      expect(verifyLoginCode).toHaveBeenCalledWith("new@example.com", "123456", {
        intent: "sign_up",
        privacyTermsAccepted: true,
        aiProcessingConsent: true,
      }),
    );
    expect(onLogin).toHaveBeenCalledWith(session);
  });

  it("reports an unknown account before showing the verification-code step", async () => {
    const alert = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
    jest.mocked(requestLoginCode).mockRejectedValue(new Error("No account exists for this email. Create one first."));
    const view = await render(
      <SafeAreaProvider initialMetrics={metrics}>
        <Login onLogin={jest.fn()} />
      </SafeAreaProvider>,
    );

    expect(view.queryByText("Back to homepage")).toBeNull();
    expect(view.queryByText(/Welcome back/)).toBeNull();
    await fireEvent.changeText(view.getByLabelText("Email"), "missing@example.com");
    await fireEvent.press(view.getByRole("button", { name: "Email me a code" }));

    await waitFor(() =>
      expect(alert).toHaveBeenCalledWith("Sign in failed", "No account exists for this email. Create one first."),
    );
    expect(requestLoginCode).toHaveBeenCalledWith("missing@example.com", "sign_in");
    expect(view.queryByLabelText("Verification code")).toBeNull();
    expect(verifyLoginCode).not.toHaveBeenCalled();
  });
});

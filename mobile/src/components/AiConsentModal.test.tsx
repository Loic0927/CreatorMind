import { fireEvent, render } from "@testing-library/react-native";
import { AiConsentModal } from "./AiConsentModal";

describe("AiConsentModal", () => {
  it("explains Google Gemini data use and provides a choice", async () => {
    const accept = jest.fn();
    const notNow = jest.fn();
    const view = await render(<AiConsentModal visible onAccept={accept} onNotNow={notNow} />);

    expect(view.getByText(/Google Gemini API/i)).toBeTruthy();
    expect(view.getByText(/post media and captions/i)).toBeTruthy();
    expect(view.getByText(/audience comment text/i)).toBeTruthy();
    expect(view.getByText(/performance facts/i)).toBeTruthy();

    await fireEvent.press(view.getByRole("button", { name: "Accept" }));
    expect(accept).toHaveBeenCalledTimes(1);
    await fireEvent.press(view.getByRole("button", { name: "Not now" }));
    expect(notNow).toHaveBeenCalledTimes(1);
  });
});

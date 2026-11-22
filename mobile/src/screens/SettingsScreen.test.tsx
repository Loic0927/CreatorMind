import { render } from "@testing-library/react-native";
import { SettingsScreen } from "./SettingsScreen";
import { getConnection } from "../services/api";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn(), maybeCompleteAuthSession: jest.fn() }));
jest.mock("../services/api", () => ({
  connectInstagram: jest.fn(),
  deleteAccount: jest.fn(),
  disconnectInstagram: jest.fn(),
  getConnection: jest.fn(),
}));

describe("SettingsScreen", () => {
  it("shows plain legal links at the bottom without an AI processing container", async () => {
    jest.mocked(getConnection).mockResolvedValue({
      connected: false,
      configured: true,
      status: "not_connected",
    });
    const view = await render(
      <SettingsScreen
        email="creator@example.com"
        accessToken="token"
        onLogout={jest.fn()}
        onAccountDeleted={jest.fn()}
      />,
    );

    expect(await view.findByText("Connected accounts")).toBeTruthy();
    expect(view.queryByText("AI processing")).toBeNull();
    expect(view.getByRole("link", { name: "Privacy" })).toBeTruthy();
    expect(view.getByRole("link", { name: "Terms" })).toBeTruthy();
  });
});

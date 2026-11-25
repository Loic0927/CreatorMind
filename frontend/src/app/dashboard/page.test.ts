import { afterEach, describe, expect, it } from "vitest";
import { dashboardLocation } from "./page";

afterEach(() => window.history.replaceState({}, "", "/dashboard"));

describe("dashboardLocation", () => {
  it("restores the selected dashboard tab after a browser refresh", () => {
    window.history.replaceState({}, "", "/dashboard?tab=insights");

    expect(dashboardLocation()).toEqual({ tab: "insights", analyzeId: "" });
  });

  it("restores the selected Analyze post after a browser refresh", () => {
    window.history.replaceState({}, "", "/dashboard?tab=analyze&post=tracked-post-id");

    expect(dashboardLocation()).toEqual({ tab: "analyze", analyzeId: "tracked-post-id" });
  });

  it("moves a legacy Home post detail to Analyze so navigation state stays accurate", () => {
    window.history.replaceState({}, "", "/dashboard?tab=home&view=post&platform=tiktok&post=tiktok-post-id");

    expect(dashboardLocation()).toEqual({
      tab: "analyze",
      analyzeId: "tiktok:tiktok-post-id",
    });
  });
});

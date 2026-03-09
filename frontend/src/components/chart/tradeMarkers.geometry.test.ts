import { describe, expect, it } from "vitest";
import { resolveMarkerGeometry, resolvePaneBounds } from "./tradeMarkers";

describe("resolveMarkerGeometry", () => {
  it("anchors buy markers from candle bottom and sell markers from candle top", () => {
    const buy = resolveMarkerGeometry({
      side: "buy",
      lane: 0,
      priceY: 130,
      bodyTopY: 100,
      bodyBottomY: 140,
      paneTop: 0,
      paneBottom: 300,
    });
    const sell = resolveMarkerGeometry({
      side: "sell",
      lane: 0,
      priceY: 110,
      bodyTopY: 100,
      bodyBottomY: 140,
      paneTop: 0,
      paneBottom: 300,
    });

    expect(buy.placement).toBe("below");
    expect(buy.anchorY).toBe(148);
    expect(sell.placement).toBe("above");
    expect(sell.anchorY).toBe(92);
  });

  it("flips to opposite side when preferred side overflows pane", () => {
    const geometry = resolveMarkerGeometry({
      side: "sell",
      lane: 0,
      priceY: 12,
      bodyTopY: 6,
      bodyBottomY: 20,
      paneTop: 0,
      paneBottom: 200,
    });

    expect(geometry.placement).toBe("below");
    expect(geometry.anchorY).toBe(28);
  });

  it("clamps anchor after flip when pane is too tight", () => {
    const geometry = resolveMarkerGeometry({
      side: "sell",
      lane: 2,
      priceY: 11,
      bodyTopY: 10,
      bodyBottomY: 12,
      paneTop: 0,
      paneBottom: 40,
    });

    expect(geometry.placement).toBe("below");
    expect(geometry.anchorY).toBe(5);
  });

  it("separates lanes with fixed vertical gap", () => {
    const first = resolveMarkerGeometry({
      side: "buy",
      lane: 0,
      priceY: 110,
      bodyTopY: 100,
      bodyBottomY: 120,
      paneTop: 0,
      paneBottom: 300,
    });
    const second = resolveMarkerGeometry({
      side: "buy",
      lane: 1,
      priceY: 110,
      bodyTopY: 100,
      bodyBottomY: 120,
      paneTop: 0,
      paneBottom: 300,
    });

    expect(second.anchorY - first.anchorY).toBe(14);
  });

  it("uses candle body guard so long wicks do not push marker too far", () => {
    const geometry = resolveMarkerGeometry({
      side: "sell",
      lane: 0,
      priceY: 140,
      bodyTopY: 135,
      bodyBottomY: 160,
      paneTop: 0,
      paneBottom: 300,
    });

    // constrained by body-top guard, not full-wick high guard.
    expect(geometry.anchorY).toBe(127);
  });
});

describe("resolvePaneBounds", () => {
  it("uses local pane bounds when y is local and bounding is absolute", () => {
    const bounds = resolvePaneBounds([60, 90, 120], {
      top: 320,
      bottom: 720,
      height: 400,
    });
    expect(bounds).toEqual({ top: 0, bottom: 400 });
  });

  it("uses absolute pane bounds when y is absolute", () => {
    const bounds = resolvePaneBounds([380, 420, 450], {
      top: 320,
      bottom: 720,
      height: 400,
    });
    expect(bounds).toEqual({ top: 320, bottom: 720 });
  });
});

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OverlayChart, endLabel2026, endLabel2018, monthDay } from "../OverlayChart";
import { fixtureDoc } from "./fixture";

describe("OverlayChart", () => {
  it("computes the 2026 end label from the last point of the series", () => {
    const last = fixtureDoc.series_2026[fixtureDoc.series_2026.length - 1];
    expect(endLabel2026(last)).toBe("2026: day 22, -5.9%");
    expect(endLabel2026({ ...last, t: 30, spy: -9.04 })).toBe("2026: day 30, -9.0%");
  });

  it("labels the 2018 end point from its date and value", () => {
    const p72 = fixtureDoc.series_2018.find((p) => p.t === 72)!;
    expect(endLabel2018(p72)).toBe("2018: Jan 4 'patient', -14.0%");
    expect(monthDay("2018-10-11")).toBe("Oct 11");
  });

  it("renders both series, the legend, the end labels and the 2018 event dots", () => {
    const { container } = render(
      <OverlayChart s2018={fixtureDoc.series_2018} s2026={fixtureDoc.series_2026} />,
    );
    expect(screen.getByRole("img")).toBeInTheDocument();
    expect(screen.getByText("2026: day 22, -5.9%")).toBeInTheDocument();
    expect(screen.getByText("2018: Jan 4 'patient', -14.0%")).toBeInTheDocument();
    expect(screen.getByText("2026, from Oct 6")).toBeInTheDocument();
    expect(screen.getByText("2018, from Sep 20")).toBeInTheDocument();
    for (const label of ["200-day break", "-10% low", "reclaims 200-day, fails", "Dec 19 hike", "-20% low"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // the 2026 calendar markers are labeled once, at the top
    expect(screen.getByText(/Dec 9 FOMC \(day 45\).*CR expiry \(day 47\).*Cook hearing \(day 48\)/)).toBeInTheDocument();
    // two series paths, one per year
    const paths = container.querySelectorAll("path");
    expect(paths.length).toBe(2);
    expect(paths[0].getAttribute("stroke")).toBe("#d95926");
    expect(paths[1].getAttribute("stroke")).toBe("#3987e5");
  });

  it("clips the 2018 path at day 72 so the x axis stays on the analog window", () => {
    const { container } = render(
      <OverlayChart s2018={fixtureDoc.series_2018} s2026={fixtureDoc.series_2026} />,
    );
    const d = container.querySelector("path")!.getAttribute("d")!;
    // 10 points at t<=72 in the fixture (the t=80 point is dropped)
    expect(d.split(/[ML]/).filter(Boolean).length).toBe(10);
  });

  it("shows a crosshair tooltip on hover and clears it on leave", () => {
    const { container } = render(
      <OverlayChart s2018={fixtureDoc.series_2018} s2026={fixtureDoc.series_2026} />,
    );
    const svg = container.querySelector("svg")!;
    // jsdom has no layout: stub the bounding box so the x -> day mapping is deterministic
    svg.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 820, height: 400, right: 820, bottom: 400, x: 0, y: 0, toJSON() {} }) as DOMRect;
    // pad.l = 44, innerW = 820 - 44 - 190 = 586; day 22 -> x = 44 + 22/72*586
    fireEvent.mouseMove(svg, { clientX: 44 + (22 / 72) * 586, clientY: 100 });
    expect(screen.getByText("Day 22 from peak")).toBeInTheDocument();
    expect(screen.getByText(/2026\s+-5\.9%\s+Nov 5/)).toBeInTheDocument();
    expect(screen.getByText(/-4\.4% day, AI de-rating/)).toBeInTheDocument();
    fireEvent.mouseLeave(svg);
    expect(screen.queryByText("Day 22 from peak")).not.toBeInTheDocument();
  });

  it("renders an empty state when the 2018 path is too short", () => {
    render(<OverlayChart s2018={[fixtureDoc.series_2018[0]]} s2026={fixtureDoc.series_2026} />);
    expect(screen.getByText(/Not enough analog history/)).toBeInTheDocument();
  });
});

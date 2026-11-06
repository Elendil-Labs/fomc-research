import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { Analog2018View } from "../Analog2018";
import { buildLadder, sideOf } from "../ladder";
import { ES_LADDER, ES_SETTLE, REASONS, SPY_LADDER, TITLE } from "../copy";
import { App } from "../../App";
import { fixtureDoc } from "./fixture";

describe("Analog2018View", () => {
  it("renders the title, the two intro paragraphs and the five reason cards", () => {
    render(<Analog2018View doc={fixtureDoc} />);
    expect(screen.getByRole("heading", { level: 1, name: TITLE })).toBeInTheDocument();
    expect(screen.getByText(/^Bottom line, November 6, 2026:/)).toBeInTheDocument();
    expect(screen.getByText(/^SPY closed Thursday at 733\.00/)).toBeInTheDocument();
    expect(screen.getByText("Five reasons it rhymes, strongest first")).toBeInTheDocument();
    for (const r of REASONS) expect(screen.getByText(r.lead)).toBeInTheDocument();
    expect(REASONS).toHaveLength(5);
    const nums = document.querySelectorAll(".lead-num");
    expect(nums.length).toBe(5);
    expect(Array.from(nums).map((n) => n.textContent)).toEqual(["1", "2", "3", "4", "5"]);
  });

  it("renders the counterarguments, the template, the ladders and the navigation sections", () => {
    render(<Analog2018View doc={fixtureDoc} />);
    expect(screen.getByText("The two strongest arguments that this time is different")).toBeInTheDocument();
    expect(screen.getByText(/^The honest weight:/)).toBeInTheDocument();
    expect(screen.getByText("The 2018 template")).toBeInTheDocument();
    expect(screen.getByText("Levels to be prepared for")).toBeInTheDocument();
    expect(screen.getByText("How to navigate it")).toBeInTheDocument();
    expect(screen.getByText("The analog breaks in the bulls' favor if")).toBeInTheDocument();
    expect(screen.getByText("The analog is confirmed if")).toBeInTheDocument();
    expect(screen.getByText(/^Caveats we owe you\./)).toBeInTheDocument();
    expect(
      screen.getByText("[Disclosure: state the book's exposure to SPY, ES, MES and rate products here, or \"no position\" if none.]"),
    ).toBeInTheDocument();
    expect(screen.getByText("Not investment advice.")).toBeInTheDocument();
    expect(screen.getByText("Jing Xie, Co-Founder, Elendil Labs")).toBeInTheDocument();
  });

  it("inserts the computed 2026 row into the 2018 template at the current day count", () => {
    render(<Analog2018View doc={fixtureDoc} />);
    const here = screen.getByTestId("template-here");
    const cells = within(here).getAllByRole("cell").map((c) => c.textContent);
    expect(cells[0]).toBe("22");
    expect(cells[1]).toMatch(/^2026 is here: 2026-11-05/);
    expect(cells[2]).toBe("-5.9%");
    expect(cells[3]).toBe("0.4% above");
    // sits between day 15 and day 27 of the template
    const rows = Array.from(here.parentElement!.querySelectorAll("tr")).map(
      (r) => r.querySelector("td")!.textContent,
    );
    const i = rows.indexOf("22");
    expect(rows[i - 1]).toBe("15");
    expect(rows[i + 1]).toBe("27");
  });

  it("inserts the current ES settle into the ES ladder between 7490 and 7353", () => {
    render(<Analog2018View doc={fixtureDoc} />);
    const table = screen.getByTestId("es-ladder");
    const prices = Array.from(table.querySelectorAll("tbody tr .lvl-price")).map((e) => e.textContent);
    const i = prices.indexOf("7373");
    expect(i).toBeGreaterThan(0);
    expect(prices[i - 1]).toBe("7490");
    expect(prices[i + 1]).toBe("7353");
    expect(prices[0]).toBe("7800");
    expect(prices[prices.length - 1]).toBe("6933");
    const hereRow = table.querySelector("tbody tr.here")!;
    expect(hereRow.textContent).toContain("ES settle, you are here");
    expect(screen.getByText("What to do")).toBeInTheDocument();
  });

  it("inserts the SPY close into the SPY ladder between 745.9 and the 200-day row", () => {
    render(<Analog2018View doc={fixtureDoc} />);
    const table = screen.getByTestId("spy-ladder");
    const prices = Array.from(table.querySelectorAll("tbody tr .lvl-price")).map((e) => e.textContent);
    const i = prices.indexOf("733.00");
    expect(prices[i - 1]).toBe("745.9");
    expect(prices[i + 1]).toBe("731.8 / 730.2");
  });

  it("renders the pending state when the doc is null", () => {
    render(<Analog2018View doc={null} />);
    expect(screen.getByText(/populates on the next scheduled data run/)).toBeInTheDocument();
    expect(screen.queryByText(/Five reasons it rhymes/)).not.toBeInTheDocument();
  });
});

describe("ladder", () => {
  it("sorts high to low and marks resistance above and support below the current price", () => {
    const rows = buildLadder(ES_LADDER, ES_SETTLE, "here");
    const keys = rows.map((r) => r.key);
    expect(keys).toEqual([...keys].sort((a, b) => b - a));
    expect(rows.filter((r) => r.current)).toHaveLength(1);
    expect(sideOf(rows.find((r) => r.key === 7490)!, ES_SETTLE)).toBe("resistance");
    expect(sideOf(rows.find((r) => r.key === 7353)!, ES_SETTLE)).toBe("support");
    expect(sideOf(rows.find((r) => r.current)!, ES_SETTLE)).toBe("current");
  });

  it("keeps a range row under its upper neighbor using its lower bound", () => {
    const rows = buildLadder(SPY_LADDER, 733, "here");
    const prices = rows.map((r) => r.price);
    expect(prices.indexOf("752 to 756")).toBe(prices.indexOf("758.6") + 1);
    expect(prices.indexOf("729.5 / 725.4")).toBe(prices.indexOf("731.8 / 730.2") + 1);
  });
});

describe("App routing", () => {
  it("routes #analog to the analog tab", async () => {
    // no data server in tests: every loader resolves null and the tab shows its pending state
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
    window.location.hash = "#analog";
    render(<App />);
    const tab = screen.getByRole("tab", { name: /4Q'18/ });
    expect(tab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Event Explorer" })).toHaveAttribute("aria-selected", "false");
    expect(await screen.findByText(/populates on the next scheduled data run/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: TITLE })).toBeInTheDocument();
    vi.unstubAllGlobals();
    window.location.hash = "";
  });
});

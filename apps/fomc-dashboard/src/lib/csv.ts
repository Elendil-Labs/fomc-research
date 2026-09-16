// Minimal CSV utilities. The event-truth CSV has no embedded commas/quotes, so a
// simple split is sufficient and fully tested. We also emit CSV for the evidence
// matrix export, where values CAN contain commas/quotes — hence escapeCsv().

import type { FomcEvent } from "../types";

const STRING_COLS = new Set(["date", "chair", "regime", "action", "ff_target"]);
const BOOL_COLS = new Set(["emergency"]);

function coerce(col: string, raw: string): unknown {
  const v = (raw ?? "").trim();
  if (STRING_COLS.has(col)) return v;
  if (BOOL_COLS.has(col)) return v.toLowerCase() === "true";
  if (v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? v : n;
}

/** Parse the event-truth CSV text into typed rows. */
export function parseEventTruthCsv(text: string): FomcEvent[] {
  const lines = text.replace(/\r\n/g, "\n").trim().split("\n");
  if (lines.length < 2) return [];
  const header = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const cells = line.split(",");
    const row: Record<string, unknown> = {};
    header.forEach((col, i) => {
      row[col] = coerce(col, cells[i] ?? "");
    });
    return row as unknown as FomcEvent;
  });
}

/** Escape a single CSV field per RFC 4180 (quote if it contains , " or newline). */
export function escapeCsv(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

/** Build a CSV document from a header row and rows of fields. */
export function toCsv(header: string[], rows: unknown[][]): string {
  const head = header.map(escapeCsv).join(",");
  const body = rows.map((r) => r.map(escapeCsv).join(",")).join("\n");
  return `${head}\n${body}\n`;
}

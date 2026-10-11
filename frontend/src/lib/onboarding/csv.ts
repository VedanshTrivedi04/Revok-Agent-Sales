/** Splits one CSV line into cells, honouring double quotes and escaped quotes (""). */
export function splitCsvLine(line: string): string[] {
  const cells: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') {
        quoted = false;
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      cells.push(cell.trim());
      cell = "";
    } else {
      cell += ch;
    }
  }
  cells.push(cell.trim());
  return cells;
}

/** Column names from the first non-empty line, without a BOM, blanks removed and de-duplicated. */
export function parseCsvHeader(text: string): string[] {
  const first = text
    .replace(/^﻿/, "")
    .split(/\r?\n/)
    .find((l) => l.trim().length > 0);
  if (!first) return [];
  const seen = new Set<string>();
  return splitCsvLine(first).filter((c) => {
    if (!c || seen.has(c)) return false;
    seen.add(c);
    return true;
  });
}

/** Best-guess column for each usage field so the user only has to confirm. */
export function guessUsageMapping(columns: string[]): Record<string, string> {
  const find = (...needles: string[]) =>
    columns.find((c) => needles.some((n) => c.toLowerCase().replace(/[\s_-]/g, "").includes(n))) ?? "";
  return {
    account_key: find("domain", "accountkey", "account", "company"),
    period_start: find("periodstart", "weekstart", "date", "period"),
    active_users: find("activeusers", "mau", "wau", "dau", "active"),
    seats_used: find("seatsused", "seats"),
    logins: find("logins", "sessions"),
  };
}

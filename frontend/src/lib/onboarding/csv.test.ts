import { describe, expect, it } from "vitest";
import { guessUsageMapping, parseCsvHeader, splitCsvLine } from "./csv";

describe("csv helpers", () => {
  it("splits cells with quotes and escaped quotes", () => {
    expect(splitCsvLine('a,"b,c","say ""hi""",d')).toEqual(["a", "b,c", 'say "hi"', "d"]);
  });

  it("reads the header, ignoring a BOM, blank lines, blanks and duplicates", () => {
    expect(parseCsvHeader("﻿\r\ndomain, week_start ,active_users,,domain\r\nacme.com,2026-10-05,30")).toEqual([
      "domain",
      "week_start",
      "active_users",
    ]);
    expect(parseCsvHeader("")).toEqual([]);
  });

  it("guesses sensible columns", () => {
    expect(guessUsageMapping(["Company Domain", "Week Start", "Active Users", "Seats Used", "Logins"])).toEqual({
      account_key: "Company Domain",
      period_start: "Week Start",
      active_users: "Active Users",
      seats_used: "Seats Used",
      logins: "Logins",
    });
    expect(guessUsageMapping(["x", "y"]).account_key).toBe("");
  });
});

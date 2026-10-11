import React from "react";
import { formatDistanceToNow, format } from "date-fns";
import { toZonedTime } from "date-fns-tz";
import clsx from "clsx";

interface DateTextProps {
  date: string | Date | null | undefined;
  timezone?: string;
  formatStr?: string;
  className?: string;
}

export function DateText({
  date,
  timezone = "UTC",
  formatStr = "MMM d, yyyy",
  className,
}: DateTextProps) {
  if (!date) return <span className="text-slate-400 font-mono">—</span>;

  let formatted: string | null = null;
  let isoString: string | null = null;

  try {
    const parsedDate = typeof date === "string" ? new Date(date) : date;
    const zoned = toZonedTime(parsedDate, timezone);
    formatted = format(zoned, formatStr);
    isoString = parsedDate.toISOString();
  } catch {
    formatted = null;
  }

  if (!formatted || !isoString) {
    return <span className="text-slate-400 font-mono">—</span>;
  }

  return (
    <time dateTime={isoString} className={clsx("font-sans", className)}>
      {formatted}
    </time>
  );
}

interface RelativeTimeProps {
  date: string | Date | null | undefined;
  addSuffix?: boolean;
  className?: string;
}

export function RelativeTime({ date, addSuffix = true, className }: RelativeTimeProps) {
  if (!date) return <span className="text-slate-400 font-mono">—</span>;

  let relative: string | null = null;
  let isoString: string | null = null;
  let localeStr: string | null = null;

  try {
    const parsedDate = typeof date === "string" ? new Date(date) : date;
    relative = formatDistanceToNow(parsedDate, { addSuffix });
    isoString = parsedDate.toISOString();
    localeStr = parsedDate.toLocaleString();
  } catch {
    relative = null;
  }

  if (!relative || !isoString) {
    return <span className="text-slate-400 font-mono">—</span>;
  }

  return (
    <time
      dateTime={isoString}
      title={localeStr ?? undefined}
      className={clsx("text-slate-500 dark:text-slate-400", className)}
    >
      {relative}
    </time>
  );
}


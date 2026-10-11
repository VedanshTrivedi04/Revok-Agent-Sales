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

  try {
    const parsedDate = typeof date === "string" ? new Date(date) : date;
    const zoned = toZonedTime(parsedDate, timezone);
    const formatted = format(zoned, formatStr);

    return (
      <time dateTime={parsedDate.toISOString()} className={clsx("font-sans", className)}>
        {formatted}
      </time>
    );
  } catch {
    return <span className="text-slate-400 font-mono">—</span>;
  }
}

interface RelativeTimeProps {
  date: string | Date | null | undefined;
  addSuffix?: boolean;
  className?: string;
}

export function RelativeTime({ date, addSuffix = true, className }: RelativeTimeProps) {
  if (!date) return <span className="text-slate-400 font-mono">—</span>;

  try {
    const parsedDate = typeof date === "string" ? new Date(date) : date;
    const relative = formatDistanceToNow(parsedDate, { addSuffix });

    return (
      <time
        dateTime={parsedDate.toISOString()}
        title={parsedDate.toLocaleString()}
        className={clsx("text-slate-500 dark:text-slate-400", className)}
      >
        {relative}
      </time>
    );
  } catch {
    return <span className="text-slate-400 font-mono">—</span>;
  }
}

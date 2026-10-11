import React from "react";
import clsx from "clsx";

interface MoneyTextProps {
  amount: number | null | undefined;
  currency?: string;
  compact?: boolean;
  className?: string;
}

export function MoneyText({
  amount,
  currency = "USD",
  compact = false,
  className,
}: MoneyTextProps) {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return <span className={clsx("text-slate-400 font-mono", className)}>—</span>;
  }

  const formatMoney = (val: number, cur: string, isCompact: boolean) => {
    try {
      const formatter = new Intl.NumberFormat(cur === "INR" ? "en-IN" : "en-US", {
        style: "currency",
        currency: cur,
        notation: isCompact ? "compact" : "standard",
        maximumFractionDigits: isCompact ? 1 : 0,
      });
      return formatter.format(val);
    } catch {
      return `${cur} ${val.toLocaleString()}`;
    }
  };

  const formatted = formatMoney(amount, currency, compact);

  return (
    <span className={clsx("font-mono font-semibold tracking-tight", className)}>
      {formatted}
    </span>
  );
}

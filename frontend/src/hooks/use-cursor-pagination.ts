"use client";

import { useState, useCallback } from "react";

interface UseCursorPaginationOptions {
  initialLimit?: number;
}

export function useCursorPagination(options?: UseCursorPaginationOptions) {
  const [limit, setLimit] = useState<number>(options?.initialLimit || 25);
  const [currentCursor, setCurrentCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const setPaginationData = useCallback((next: string | null) => {
    setNextCursor(next);
  }, []);

  const goToNext = useCallback(() => {
    if (!nextCursor) return;
    setCursorHistory((prev) => [...prev, currentCursor || ""]);
    setCurrentCursor(nextCursor);
  }, [nextCursor, currentCursor]);

  const goToPrevious = useCallback(() => {
    if (cursorHistory.length === 0) return;
    const previous = cursorHistory[cursorHistory.length - 1];
    setCursorHistory((prev) => prev.slice(0, -1));
    setCurrentCursor(previous || null);
  }, [cursorHistory]);

  const reset = useCallback(() => {
    setCurrentCursor(null);
    setCursorHistory([]);
    setNextCursor(null);
  }, []);

  return {
    limit,
    setLimit,
    currentCursor,
    nextCursor,
    hasPrevious: cursorHistory.length > 0,
    hasNext: Boolean(nextCursor),
    setPaginationData,
    goToNext,
    goToPrevious,
    reset,
  };
}

"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUp, ChevronRight, LifeBuoy } from "lucide-react";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { DateText } from "../../../components/ui/date-text";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";

type Catalog = components["schemas"]["AssistantCatalog"];
type Question = components["schemas"]["AssistantQuestion"];
type AskIn = components["schemas"]["AssistantAskIn"];
type Answer = components["schemas"]["AssistantAnswer"];
type Row = components["schemas"]["AnswerRow"];

interface Turn {
  id: number;
  asked: string;
  body: AskIn;
  answer?: Answer;
  error?: string;
}

/** Where a record behind an answer lives in the app (most specific link wins). */
function rowHref(row: Row): string | null {
  if (row.card_id) return `/inbox/${row.card_id}`;
  if (row.finding_id) return `/findings/${row.finding_id}`;
  if (row.account_id) return `/accounts/${row.account_id}`;
  return null;
}

function QuestionChips({
  questions,
  onPick,
  disabled,
}: {
  questions: Question[];
  onPick: (q: Question) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {questions.map((q) => (
        <button
          key={q.id}
          type="button"
          disabled={disabled}
          onClick={() => onPick(q)}
          className="px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-700 dark:text-slate-200 hover:border-blue-500 hover:text-blue-700 dark:hover:text-blue-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-blue-500 text-left"
        >
          {q.text}
        </button>
      ))}
    </div>
  );
}

function AnswerRows({ answer }: { answer: Answer }) {
  if (answer.rows.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-lg border border-slate-200 dark:border-slate-800 overflow-hidden">
        {answer.rows.map((row, i) => {
          const href = rowHref(row);
          const body = (
            <>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
                  {row.title}
                </div>
                {row.detail && (
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                    {row.detail}
                  </div>
                )}
              </div>
              {href && (
                <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" aria-hidden="true" />
              )}
            </>
          );
          return (
            <li key={`${row.title}-${i}`}>
              {href ? (
                <Link
                  href={href}
                  className="flex items-center justify-between gap-3 px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
                >
                  {body}
                </Link>
              ) : (
                <div className="flex items-center justify-between gap-3 px-3 py-2">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
      {answer.total > answer.rows.length && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          Showing {answer.rows.length} of {answer.total}.
        </p>
      )}
    </div>
  );
}

function TurnView({
  turn,
  onPick,
  onRetry,
}: {
  turn: Turn;
  onPick: (q: Question) => void;
  onRetry: (turn: Turn) => void;
}) {
  const { answer } = turn;
  return (
    <article className="space-y-2">
      <div className="flex justify-end">
        <p className="max-w-[85%] px-3 py-2 rounded-xl rounded-br-sm bg-blue-600 text-white text-xs">
          {turn.asked}
        </p>
      </div>

      {!answer && !turn.error && (
        <div
          className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2"
          role="status"
          aria-label="Looking up the answer"
        >
          <div className="h-3 w-2/3 rounded bg-slate-200 dark:bg-slate-800 animate-pulse" />
          <div className="h-3 w-1/3 rounded bg-slate-200 dark:bg-slate-800 animate-pulse" />
        </div>
      )}

      {turn.error && (
        <ErrorState
          title="Could not get an answer"
          message={turn.error}
          onRetry={() => onRetry(turn)}
        />
      )}

      {answer && (
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-3">
          <p className="text-sm text-slate-900 dark:text-slate-100 leading-relaxed">{answer.text}</p>
          <AnswerRows answer={answer} />
          {answer.suggestions.length > 0 && (
            <QuestionChips questions={answer.suggestions} onPick={onPick} />
          )}
          {answer.status === "answered" && (
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {answer.basis} As of <DateText date={answer.as_of} formatStr="MMM d, yyyy HH:mm" />{" "}
              UTC.
            </p>
          )}
        </div>
      )}
    </article>
  );
}

export default function HelpPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);

  const catalog = useQuery<Catalog>({
    queryKey: queryKeys.assistantCatalog(),
    queryFn: () => fetchApi<Catalog>("/assistant/catalog"),
    staleTime: 5 * 60 * 1000,
  });
  const questions = catalog.data?.questions ?? [];

  const run = useCallback(async (id: number, body: AskIn) => {
    try {
      // A read: no Idempotency-Key, so asking the same thing again is always answered fresh.
      const answer = await fetchApi<Answer>("/assistant/ask", {
        method: "POST",
        body: JSON.stringify(body),
        idempotencyKey: false,
      });
      setTurns((all) => all.map((t) => (t.id === id ? { ...t, answer, error: undefined } : t)));
    } catch (e) {
      const error = e instanceof Error ? e.message : "Unable to reach backend API";
      setTurns((all) => all.map((t) => (t.id === id ? { ...t, error } : t)));
    }
  }, []);

  const ask = useCallback(
    (asked: string, body: AskIn) => {
      const id = nextId.current++;
      setTurns((all) => [...all, { id, asked, body }]);
      void run(id, body);
    },
    [run]
  );

  const pick = (q: Question) => ask(q.text, { question_id: q.id });
  const retry = (turn: Turn) => {
    setTurns((all) => all.map((t) => (t.id === turn.id ? { ...t, error: undefined } : t)));
    void run(turn.id, turn.body);
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const question = draft.trim();
    if (!question) return;
    setDraft("");
    ask(question, { question });
  };

  useEffect(() => {
    if (turns.length > 0) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  return (
    <PermissionGuard action="view:assistant">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Help
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Ask about accounts, risk, renewals and approvals. Every answer is read from your
            workspace data at the moment you ask.
          </p>
        </div>

        <div className="space-y-5" aria-live="polite">
          {turns.map((turn) => (
            <TurnView key={turn.id} turn={turn} onPick={pick} onRetry={retry} />
          ))}
        </div>

        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-4">
          <form onSubmit={submit} className="flex items-center gap-2">
            <label htmlFor="help-question" className="sr-only">
              Your question
            </label>
            <input
              id="help-question"
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
              autoComplete="off"
              placeholder="Type a question, or pick one below"
              className="flex-1 min-w-0 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            />
            <button
              type="submit"
              disabled={!draft.trim()}
              aria-label="Ask"
              className="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <ArrowUp className="w-4 h-4" aria-hidden="true" />
            </button>
          </form>

          <div className="space-y-2">
            <h2 className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider font-mono">
              Questions you can ask
            </h2>

            {catalog.isLoading && (
              <div className="flex flex-wrap gap-2" role="status" aria-label="Loading questions">
                {[40, 56, 48, 36].map((w) => (
                  <div
                    key={w}
                    className="h-7 rounded-full bg-slate-200 dark:bg-slate-800 animate-pulse"
                    style={{ width: `${w * 4}px` }}
                  />
                ))}
              </div>
            )}

            {catalog.error && !catalog.isLoading && (
              <ErrorState
                title="Failed to load questions"
                message={
                  catalog.error instanceof Error
                    ? catalog.error.message
                    : "Unable to reach backend API"
                }
                onRetry={() => void catalog.refetch()}
              />
            )}

            {!catalog.isLoading && !catalog.error && questions.length === 0 && (
              <EmptyState
                title="No questions available"
                description="The backend did not return any questions the assistant can answer."
                icon={<LifeBuoy className="w-6 h-6" aria-hidden="true" />}
              />
            )}

            {questions.length > 0 && <QuestionChips questions={questions} onPick={pick} />}
          </div>
        </div>

        <div ref={endRef} />
      </div>
    </PermissionGuard>
  );
}

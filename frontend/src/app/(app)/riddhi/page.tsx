"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUp,
  ChevronRight,
  Globe,
  MessageCircleQuestion,
  Mic,
  MicOff,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import { ASSISTANT_NAME } from "../../../lib/assistant";
import { INDIAN_LANGUAGES, useVoiceAssistant } from "../../../lib/use-voice-assistant";
import type { components } from "../../../lib/api/schema";
import { DateText } from "../../../components/ui/date-text";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";

type Catalog = components["schemas"]["AssistantCatalog"];
type Question = components["schemas"]["AssistantQuestion"];
// `params` has a server-side default, which the generated type reports as required.
type AskIn = Omit<components["schemas"]["AssistantAskIn"], "params"> & {
  params?: components["schemas"]["AssistantAskIn"]["params"];
};
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
  isSpeaking,
  onSpeak,
  onStopSpeaking,
}: {
  turn: Turn;
  onPick: (q: Question) => void;
  onRetry: (turn: Turn) => void;
  isSpeaking: boolean;
  onSpeak: (text: string, id: number) => void;
  onStopSpeaking: () => void;
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
          aria-label={`${ASSISTANT_NAME} is looking up the answer`}
        >
          <div className="h-3 w-2/3 rounded bg-slate-200 dark:bg-slate-800 animate-pulse" />
          <div className="h-3 w-1/3 rounded bg-slate-200 dark:bg-slate-800 animate-pulse" />
        </div>
      )}

      {turn.error && (
        <ErrorState
          title={`${ASSISTANT_NAME} could not get an answer`}
          message={turn.error}
          onRetry={() => onRetry(turn)}
        />
      )}

      {answer && (
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider font-mono">
              {ASSISTANT_NAME}
            </div>

            {/* Audio Readout Controls */}
            {isSpeaking ? (
              <button
                type="button"
                onClick={onStopSpeaking}
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 transition-colors"
                title="Stop speaking"
              >
                <span className="flex h-1.5 w-1.5 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-rose-500" />
                </span>
                <Square className="w-3 h-3 fill-current" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onSpeak(answer.text, turn.id)}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-slate-500 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                title="Read aloud"
              >
                <Volume2 className="w-3.5 h-3.5" />
                <span>Speak</span>
              </button>
            )}
          </div>

          {/* A typed question is matched to a catalog question: show which one was answered. */}
          {turn.body.question && answer.interpreted_as && (
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Answered as: <span className="font-medium">{answer.interpreted_as}</span>
            </p>
          )}
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

export default function AssistantPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);

  const {
    isListening,
    isSpeaking,
    speakingTurnId,
    speechError,
    autoSpeak,
    language,
    setLanguage,
    hasSttSupport,
    toggleAutoSpeak,
    speak,
    stopSpeaking,
    startListening,
    stopListening,
  } = useVoiceAssistant();

  const currentLangObj =
    INDIAN_LANGUAGES.find((l) => l.code === language) || INDIAN_LANGUAGES[0];

  const catalog = useQuery<Catalog>({
    queryKey: queryKeys.assistantCatalog(),
    queryFn: () => fetchApi<Catalog>("/assistant/catalog"),
    staleTime: 5 * 60 * 1000,
  });
  const questions = catalog.data?.questions ?? [];

  const run = useCallback(
    async (id: number, body: AskIn) => {
      try {
        // A read: no Idempotency-Key, so asking the same thing again is always answered fresh.
        const answer = await fetchApi<Answer>("/assistant/ask", {
          method: "POST",
          body: JSON.stringify(body),
          idempotencyKey: false,
        });
        setTurns((all) => all.map((t) => (t.id === id ? { ...t, answer, error: undefined } : t)));

        // Speak aloud automatically if auto-speak is enabled
        if (autoSpeak && answer.text) {
          speak(answer.text, id);
        }
      } catch (e) {
        const error = e instanceof Error ? e.message : "Unable to reach backend API";
        setTurns((all) => all.map((t) => (t.id === id ? { ...t, error } : t)));
      }
    },
    [autoSpeak, speak]
  );

  const ask = useCallback(
    (asked: string, body: AskIn) => {
      // Stop ongoing voice playback before starting a new question
      stopSpeaking();
      const id = nextId.current++;
      setTurns((all) => [...all, { id, asked, body }]);
      void run(id, body);
    },
    [run, stopSpeaking]
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

  const handleVoiceInputClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening((recognizedText) => {
        const text = recognizedText.trim();
        if (text) {
          setDraft(text);
          ask(text, { question: text });
        }
      });
    }
  };

  useEffect(() => {
    if (turns.length > 0) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  return (
    <PermissionGuard action="view:assistant">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header with Assistant title, Indian Language Selector and Voice Controls */}
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
              {ASSISTANT_NAME}
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                Voice Enabled
              </span>
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Ask {ASSISTANT_NAME} about accounts, risk, renewals and approvals in your language.
            </p>
          </div>

          {/* Language Selector + Voice Toggle */}
          <div className="flex items-center gap-2">
            {/* Indian Language Selector */}
            <div className="relative inline-flex items-center">
              <Globe className="w-3.5 h-3.5 absolute left-2.5 text-slate-400 pointer-events-none" />
              <select
                aria-label="Select Indian Language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="pl-8 pr-7 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-700 dark:text-slate-200 font-medium hover:border-slate-300 dark:hover:border-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 cursor-pointer appearance-none transition-colors"
              >
                {INDIAN_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
              <ChevronRight
                className="w-3.5 h-3.5 absolute right-2 text-slate-400 pointer-events-none rotate-90"
                aria-hidden="true"
              />
            </div>

            {/* Auto-speak toggle */}
            <button
              type="button"
              onClick={toggleAutoSpeak}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                autoSpeak
                  ? "border-blue-200 dark:border-blue-800 bg-blue-50/70 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300"
                  : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400"
              }`}
              title={autoSpeak ? "Voice answers: Enabled" : "Voice answers: Muted"}
            >
              {autoSpeak ? (
                <>
                  <Volume2 className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                  <span>Voice: On</span>
                </>
              ) : (
                <>
                  <VolumeX className="w-3.5 h-3.5" />
                  <span>Voice: Muted</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Message Turns */}
        <div className="space-y-5" aria-live="polite">
          {turns.map((turn) => (
            <TurnView
              key={turn.id}
              turn={turn}
              onPick={pick}
              onRetry={retry}
              isSpeaking={isSpeaking && speakingTurnId === turn.id}
              onSpeak={speak}
              onStopSpeaking={stopSpeaking}
            />
          ))}
        </div>

        {/* Voice Error Banner */}
        {speechError && (
          <div className="p-3 rounded-lg border border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/50 text-xs text-rose-700 dark:text-rose-300 flex items-center justify-between">
            <span>{speechError}</span>
          </div>
        )}

        {/* Input Box with Voice & Send */}
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-4">
          <form onSubmit={submit} className="flex items-center gap-2">
            <label htmlFor="assistant-question" className="sr-only">
              Your question
            </label>
            <input
              id="assistant-question"
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
              autoComplete="off"
              placeholder={
                isListening
                  ? `Listening in ${currentLangObj.label}... Speak now`
                  : `Ask in ${currentLangObj.label} (or English), or use the mic`
              }
              className={`flex-1 min-w-0 px-3 py-2 rounded-lg border text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 transition-colors ${
                isListening
                  ? "border-rose-400 dark:border-rose-500 bg-rose-50/40 dark:bg-rose-950/20"
                  : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950"
              }`}
            />

            {/* Mic Button */}
            {hasSttSupport && (
              <button
                type="button"
                onClick={handleVoiceInputClick}
                aria-label={isListening ? "Stop listening" : `Speak in ${currentLangObj.label}`}
                title={
                  isListening
                    ? "Stop listening"
                    : `Click to speak (${currentLangObj.label})`
                }
                className={`relative inline-flex items-center justify-center w-9 h-9 rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-rose-500 ${
                  isListening
                    ? "bg-rose-600 text-white hover:bg-rose-700 ring-4 ring-rose-200 dark:ring-rose-950 animate-pulse"
                    : "border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 hover:border-blue-400"
                }`}
              >
                {isListening ? (
                  <MicOff className="w-4 h-4" aria-hidden="true" />
                ) : (
                  <Mic className="w-4 h-4" aria-hidden="true" />
                )}
              </button>
            )}

            {/* Submit Arrow */}
            <button
              type="submit"
              disabled={!draft.trim() || isListening}
              aria-label="Ask"
              className="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <ArrowUp className="w-4 h-4" aria-hidden="true" />
            </button>
          </form>

          {/* Catalog questions chips */}
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
                description={`The backend did not return any questions ${ASSISTANT_NAME} can answer.`}
                icon={<MessageCircleQuestion className="w-6 h-6" aria-hidden="true" />}
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

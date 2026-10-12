"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
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
          className="px-3 py-1.5 rounded-full border border-[#E2ECE5] bg-white text-xs text-[#111C18] hover:border-[#0D3B36] hover:text-[#0D3B36] hover:bg-[#EBF3EF] transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-[#0D3B36] text-left"
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
        <p className="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-br-sm bg-[#0D3B36] text-white text-xs font-medium">
          {turn.asked}
        </p>
      </div>

      {!answer && !turn.error && (
        <div
          className="p-4 rounded-2xl border border-[#E2ECE5] bg-white space-y-2"
          role="status"
          aria-label={`${ASSISTANT_NAME} is looking up the answer`}
        >
          <div className="h-3 w-2/3 rounded bg-[#EBF2EE] animate-pulse" />
          <div className="h-3 w-1/3 rounded bg-[#EBF2EE] animate-pulse" />
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
        <div className="p-5 rounded-2xl border border-[#E2ECE5] bg-white shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <div className="w-5 h-5 rounded-full overflow-hidden bg-[#0D3B36] p-0.5 flex items-center justify-center shrink-0">
                <Image src="/chatbot.png" alt="" width={20} height={20} className="w-full h-full object-contain" />
              </div>
              <span className="text-[10px] font-semibold text-[#0D3B36] uppercase tracking-wider font-mono">
                {ASSISTANT_NAME}
              </span>
              {/* written by the model from the records listed under it, not computed by a query */}
              {answer.generated && (
                <span className="text-[10px] text-[#6A7B76]">· written from your records</span>
              )}
            </div>

            {/* Audio Readout Controls */}
            {isSpeaking ? (
              <button
                type="button"
                onClick={onStopSpeaking}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium text-rose-600 bg-rose-50 hover:bg-rose-100 transition-colors"
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
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium text-[#6A7B76] hover:text-[#0D3B36] hover:bg-[#EBF3EF] transition-colors"
                title="Read aloud"
              >
                <Volume2 className="w-3.5 h-3.5 text-[#0D3B36]" />
                <span>Speak</span>
              </button>
            )}
          </div>

          {/* A typed question is matched to a catalog question: show which one was answered. */}
          {turn.body.question && answer.interpreted_as && (
            <p className="text-[11px] text-[#6A7B76]">
              Answered as: <span className="font-medium text-[#111C18]">{answer.interpreted_as}</span>
            </p>
          )}
          <p className="text-sm text-[#111C18] leading-relaxed">{answer.text}</p>
          <AnswerRows answer={answer} />
          {answer.suggestions.length > 0 && (
            <QuestionChips questions={answer.suggestions} onPick={onPick} />
          )}
          {answer.status !== "unsupported" && answer.basis && (
            <p className="text-[11px] text-[#6A7B76]">
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
        <div className="pb-4 border-b border-[#E2ECE5] flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[#111C18] flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#0D3B36] to-[#0A332E] border border-emerald-400/40 p-0.5 flex items-center justify-center shadow-xs shrink-0 overflow-hidden">
                <Image src="/chatbot.png" alt={ASSISTANT_NAME} width={36} height={36} className="w-full h-full object-contain" priority />
              </div>
              <span>{ASSISTANT_NAME}</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-[#EAF5EE] text-[#0D3B36] border border-[#CDE1D6]">
                Voice Enabled
              </span>
            </h1>
            <p className="text-xs text-[#6A7B76] mt-1">
              Ask {ASSISTANT_NAME} about accounts, risk, renewals and approvals in your language.
            </p>
          </div>

          {/* Language Selector + Voice Toggle */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Indian Language Selector */}
            <div className="relative inline-flex items-center">
              <Globe className="w-3.5 h-3.5 absolute left-2.5 text-[#6A7B76] pointer-events-none" />
              <select
                aria-label="Select Indian Language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="pl-8 pr-7 py-1.5 rounded-xl border border-[#E2ECE5] bg-white text-xs text-[#111C18] font-medium hover:border-[#0D3B36] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0D3B36] cursor-pointer appearance-none transition-colors"
              >
                {INDIAN_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
              <ChevronRight
                className="w-3.5 h-3.5 absolute right-2 text-[#6A7B76] pointer-events-none rotate-90"
                aria-hidden="true"
              />
            </div>

            {/* Auto-speak toggle */}
            <button
              type="button"
              onClick={toggleAutoSpeak}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium transition-colors ${
                autoSpeak
                  ? "border-[#0D3B36] bg-[#EAF5EE] text-[#0D3B36]"
                  : "border-[#E2ECE5] bg-white text-[#6A7B76] hover:border-[#0D3B36] hover:text-[#0D3B36]"
              }`}
              title={autoSpeak ? "Voice answers: Enabled" : "Voice answers: Muted"}
            >
              {autoSpeak ? (
                <>
                  <Volume2 className="w-3.5 h-3.5 text-[#0D3B36]" />
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
          <div className="p-3 rounded-xl border border-rose-200 bg-rose-50 text-xs text-rose-700 flex items-center justify-between">
            <span>{speechError}</span>
          </div>
        )}

        {/* Input Box with Voice & Send */}
        <div className="p-4 rounded-2xl border border-[#E2ECE5] bg-white shadow-xs space-y-4">
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
              className={`flex-1 min-w-0 px-3.5 py-2 rounded-xl border text-xs text-[#111C18] placeholder:text-[#8E9F9A] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0D3B36] transition-colors ${
                isListening
                  ? "border-rose-400 bg-rose-50/40"
                  : "border-[#E2ECE5] bg-[#F5F8F6]"
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
                className={`relative inline-flex items-center justify-center w-9 h-9 rounded-xl transition-colors focus-visible:ring-2 focus-visible:ring-rose-500 ${
                  isListening
                    ? "bg-rose-600 text-white hover:bg-rose-700 ring-4 ring-rose-200 animate-pulse"
                    : "border border-[#E2ECE5] bg-white text-[#6A7B76] hover:text-[#0D3B36] hover:border-[#0D3B36] hover:bg-[#EBF3EF]"
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
              className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-[#0D3B36] text-white hover:bg-[#124B45] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-[#0D3B36]"
            >
              <ArrowUp className="w-4 h-4" aria-hidden="true" />
            </button>
          </form>

          {/* Catalog questions chips */}
          <div className="space-y-2">
            <h2 className="text-[10px] font-semibold text-[#6A7B76] uppercase tracking-wider font-mono">
              Questions you can ask
            </h2>

            {catalog.isLoading && (
              <div className="flex flex-wrap gap-2" role="status" aria-label="Loading questions">
                {[40, 56, 48, 36].map((w) => (
                  <div
                    key={w}
                    className="h-7 rounded-full bg-[#EBF2EE] animate-pulse"
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

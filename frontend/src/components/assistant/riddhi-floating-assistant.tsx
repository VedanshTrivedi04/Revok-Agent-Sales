"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUp,
  ChevronRight,
  Globe,
  Maximize2,
  MessageCircleQuestion,
  Mic,
  MicOff,
  Minimize2,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { fetchApi } from "../../lib/api/client";
import { queryKeys } from "../../lib/api/query-keys";
import { ASSISTANT_NAME } from "../../lib/assistant";
import { INDIAN_LANGUAGES, useVoiceAssistant } from "../../lib/use-voice-assistant";
import type { components } from "../../lib/api/schema";
import { DateText } from "../ui/date-text";
import { EmptyState } from "../ui/empty-state";
import { ErrorState } from "../ui/error-state";
import clsx from "clsx";

type Catalog = components["schemas"]["AssistantCatalog"];
type Question = components["schemas"]["AssistantQuestion"];
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
    <div className="flex flex-wrap gap-1.5">
      {questions.map((q) => (
        <button
          key={q.id}
          type="button"
          disabled={disabled}
          onClick={() => onPick(q)}
          className="px-2.5 py-1 rounded-full border border-[#E2ECE5] dark:border-slate-800 bg-[#F5F8F6] dark:bg-slate-800/80 text-[11px] font-medium text-[#111C18] dark:text-slate-200 hover:border-[#0D3B36] hover:text-[#0D3B36] dark:hover:text-emerald-300 hover:bg-[#EBF3EF] dark:hover:bg-slate-700/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left cursor-pointer"
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
    <div className="space-y-1.5 mt-2">
      <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-white dark:bg-slate-900/60">
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
              {href && <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" aria-hidden="true" />}
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
        <p className="max-w-[85%] px-3.5 py-2 rounded-2xl rounded-br-xs bg-[#0D3B36] text-white text-xs font-medium shadow-xs">
          {turn.asked}
        </p>
      </div>

      {!answer && !turn.error && (
        <div
          className="p-3.5 rounded-2xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900/90 space-y-2 shadow-xs"
          role="status"
          aria-label={`${ASSISTANT_NAME} is looking up the answer`}
        >
          <div className="h-3 w-2/3 rounded bg-[#EBF2EE] dark:bg-slate-800 animate-pulse" />
          <div className="h-3 w-1/3 rounded bg-[#EBF2EE] dark:bg-slate-800 animate-pulse" />
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
        <div className="p-4 rounded-2xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900/90 shadow-xs space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <div className="w-5 h-5 rounded-full overflow-hidden bg-[#0D3B36] p-0.5 flex items-center justify-center shrink-0">
                <Image src="/chatbot.png" alt="" width={20} height={20} className="w-full h-full object-contain" />
              </div>
              <span className="text-[10px] font-bold text-[#0D3B36] dark:text-emerald-400 uppercase tracking-wider font-mono">
                {ASSISTANT_NAME}
              </span>
              {/* written by the model from the records listed under it, not computed by a query */}
              {answer.generated && (
                <span className="text-[10px] text-slate-400 dark:text-slate-500">
                  · written from your records
                </span>
              )}
            </div>

            {isSpeaking ? (
              <button
                type="button"
                onClick={onStopSpeaking}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium text-rose-600 bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 transition-colors cursor-pointer"
                title="Stop speaking"
              >
                <Square className="w-2.5 h-2.5 fill-current" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onSpeak(answer.text, turn.id)}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium text-slate-500 dark:text-slate-400 hover:text-[#0D3B36] dark:hover:text-emerald-300 hover:bg-[#EBF3EF] dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title="Read aloud"
              >
                <Volume2 className="w-3 h-3 text-[#0D3B36] dark:text-emerald-400" />
                <span>Speak</span>
              </button>
            )}
          </div>

          {turn.body.question && answer.interpreted_as && (
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Answered as: <span className="font-semibold text-slate-800 dark:text-slate-200">{answer.interpreted_as}</span>
            </p>
          )}

          <p className="text-xs text-slate-900 dark:text-slate-100 leading-relaxed font-normal">{answer.text}</p>
          <AnswerRows answer={answer} />

          {answer.suggestions.length > 0 && (
            <div className="pt-1">
              <QuestionChips questions={answer.suggestions} onPick={onPick} />
            </div>
          )}

          {answer.status !== "unsupported" && answer.basis && (
            <p className="text-[10px] text-slate-400 dark:text-slate-500 pt-0.5 border-t border-slate-100 dark:border-slate-800">
              {answer.basis} As of <DateText date={answer.as_of} formatStr="MMM d, HH:mm" /> UTC.
            </p>
          )}
        </div>
      )}
    </article>
  );
}

/**
 * Riddhi Chatbot Widget:
 * - Sticky logo button at bottom right
 * - Opens as a sleek floating card ("little bit big")
 * - Fullscreen toggle ("open on full page")
 * - Closes back to sticky logo on click outside
 */
export function RiddhiFloatingAssistant() {
  const [mode, setMode] = useState<"closed" | "compact" | "fullscreen">("closed");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

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
        const answer = await fetchApi<Answer>("/assistant/ask", {
          method: "POST",
          body: JSON.stringify(body),
          idempotencyKey: false,
        });
        setTurns((all) => all.map((t) => (t.id === id ? { ...t, answer, error: undefined } : t)));

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
          setDraft("");
          ask(text, { question: text });
        }
      });
    }
  };

  useEffect(() => {
    if (turns.length > 0) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  // Click outside listener: collapse back to sticky logo button
  useEffect(() => {
    if (mode === "closed") return;

    function handleClickOutside(event: MouseEvent | TouchEvent) {
      // In fullscreen mode, clicking backdrop or close reduces/closes
      if (mode === "compact" && cardRef.current && !cardRef.current.contains(event.target as Node)) {
        setMode("closed");
      }
    }

    // Delay slightly to prevent immediate closing from the opening click
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("touchstart", handleClickOutside);
    }, 50);

    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [mode]);

  return (
    <>
      {/* 1. Sticky Floating Chatbot Trigger Pill (Shown when closed) */}
      {mode === "closed" && (
        <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40">
          <button
            type="button"
            onClick={() => setMode("compact")}
            className="group relative inline-flex items-center gap-2.5 sm:gap-3 pl-2.5 sm:pl-3 pr-3.5 sm:pr-4 py-2 sm:py-2.5 rounded-full bg-gradient-to-r from-[#1E0538] via-[#2E0854] to-[#4A0E78] text-white shadow-[0_8px_30px_rgba(74,14,120,0.65)] hover:shadow-[0_12px_40px_rgba(123,31,162,0.85)] border border-purple-400/40 hover:border-purple-300/80 hover:scale-[1.04] active:scale-95 transition-all duration-300 cursor-pointer select-none overflow-hidden"
            aria-label={`Open Ask ${ASSISTANT_NAME} AI Assistant`}
          >
            {/* Blinking Pulsing Glowing Aura */}
            <span className="absolute -inset-1 rounded-full bg-gradient-to-r from-[#6A0DAD] via-[#9C27B0] to-[#E040FB] blur-md animate-purple-blink pointer-events-none" />

            {/* Reflecting Top Gloss (Glass Specular Highlight) */}
            <span className="absolute inset-x-2 top-0.5 h-[46%] rounded-t-full bg-gradient-to-b from-white/35 via-white/10 to-transparent pointer-events-none z-10" />

            {/* Reflecting Animated Light Sweep (Shimmer Glint) */}
            <span className="absolute inset-0 rounded-full overflow-hidden pointer-events-none z-10">
              <span className="absolute inset-y-0 w-2/3 bg-gradient-to-r from-transparent via-white/45 to-transparent animate-light-sweep" />
            </span>

            {/* Chatbot Avatar */}
            <div className="relative z-20 w-7 h-7 sm:w-8 sm:h-8 shrink-0 flex items-center justify-center">
              <Image
                src="/chatbot.png"
                alt={`${ASSISTANT_NAME} AI`}
                width={34}
                height={34}
                className="w-full h-full object-contain drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)] group-hover:scale-105 transition-transform select-none"
                priority
              />
            </div>

            {/* Text Label + Blinking Live Beacon */}
            <div className="relative z-20 flex items-center gap-1.5">
              <span className="text-white font-semibold text-sm sm:text-[15px] tracking-wide select-none drop-shadow-sm">
                Ask {ASSISTANT_NAME}
              </span>
              {/* Blinking Beacon Dot */}
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-fuchsia-400 opacity-90" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-fuchsia-300 shadow-[0_0_8px_#E040FB]" />
              </span>
            </div>

            {/* Chevron Right Arrow */}
            <ChevronRight
              className="relative z-20 w-4 h-4 sm:w-4.5 sm:h-4.5 text-white/90 group-hover:text-white group-hover:translate-x-0.5 transition-all shrink-0 stroke-[2.5]"
              aria-hidden="true"
            />
          </button>
        </div>
      )}

      {/* 2. Chatbot Card: "Little bit big" floating card OR "Full page" modal */}
      {mode !== "closed" && (
        <>
          {/* Backdrop (Active in fullscreen or dim in compact) */}
          {mode === "fullscreen" && (
            <div
              className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs transition-opacity"
              onClick={() => setMode("closed")}
              aria-hidden="true"
            />
          )}

          <div
            ref={cardRef}
            className={clsx(
              "z-50 bg-white dark:bg-[#090E17] border border-[#DEE5E1] dark:border-slate-800 shadow-2xl flex flex-col overflow-hidden transition-all duration-300 ease-out",
              mode === "compact" &&
                "fixed bottom-3 right-3 sm:bottom-6 sm:right-6 w-[calc(100vw-1.5rem)] sm:w-[440px] md:w-[460px] max-w-[460px] h-[min(620px,calc(100vh-2rem))] max-h-[88vh] rounded-2xl sm:rounded-3xl animate-in fade-in slide-in-from-bottom-5 zoom-in-95",
              mode === "fullscreen" &&
                "fixed inset-0 sm:inset-4 md:inset-6 w-auto h-auto rounded-none sm:rounded-3xl animate-in fade-in zoom-in-95"
            )}
          >
            {/* Header: Assistant Title, Voice Controls, Fullscreen & Close */}
            <div className="px-4 py-3 border-b border-[#E2ECE5] dark:border-slate-800/80 bg-[#FAFBF9] dark:bg-[#0D1522] flex items-center justify-between gap-3 shrink-0">
              {/* Left: Assistant Info */}
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#0D3B36] to-[#0A332E] border border-emerald-400/40 p-0.5 flex items-center justify-center shadow-xs shrink-0 overflow-hidden">
                  <Image
                    src="/chatbot.png"
                    alt={ASSISTANT_NAME}
                    width={32}
                    height={32}
                    className="w-full h-full object-contain"
                  />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-sm font-bold text-[#111C18] dark:text-slate-100 truncate">
                      {ASSISTANT_NAME} AI
                    </h3>
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
                  </div>
                  <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">
                    Voice-Enabled Revenue Agent
                  </p>
                </div>
              </div>

              {/* Right Controls: Language, Audio, Fullscreen & Close */}
              <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
                {/* Language Select Pill */}
                <div className="relative inline-flex items-center">
                  <Globe className="w-3 h-3 absolute left-1.5 sm:left-2 text-slate-500 pointer-events-none" />
                  <select
                    aria-label="Language"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="pl-5 sm:pl-6 pr-4 sm:pr-5 py-1 rounded-full border border-[#E2ECE5] dark:border-slate-700 bg-white dark:bg-slate-800 text-[10px] font-semibold text-slate-800 dark:text-slate-200 cursor-pointer appearance-none focus:outline-none max-w-[84px] sm:max-w-none"
                  >
                    {INDIAN_LANGUAGES.map((l) => (
                      <option key={l.code} value={l.code}>
                        {l.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Auto-speak Toggle */}
                <button
                  type="button"
                  onClick={toggleAutoSpeak}
                  className={clsx(
                    "p-1.5 rounded-full border text-xs transition-colors cursor-pointer",
                    autoSpeak
                      ? "border-[#0D3B36] bg-[#EAF5EE] text-[#0D3B36] dark:bg-emerald-950/60 dark:text-emerald-300"
                      : "border-slate-200 dark:border-slate-700 text-slate-400 hover:text-slate-700"
                  )}
                  title={autoSpeak ? "Voice answers: Enabled" : "Voice answers: Muted"}
                >
                  {autoSpeak ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
                </button>

                {/* Fullscreen / Reduce Screen Button */}
                <button
                  type="button"
                  onClick={() => setMode(mode === "fullscreen" ? "compact" : "fullscreen")}
                  className="p-1.5 rounded-full border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                  title={mode === "fullscreen" ? "Reduce screen" : "Full screen"}
                >
                  {mode === "fullscreen" ? (
                    <Minimize2 className="w-3.5 h-3.5 text-[#0D3B36] dark:text-emerald-400" />
                  ) : (
                    <Maximize2 className="w-3.5 h-3.5 text-slate-700 dark:text-slate-300" />
                  )}
                </button>

                {/* Close to Logo Button */}
                <button
                  type="button"
                  onClick={() => setMode("closed")}
                  className="p-1.5 rounded-full border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                  title="Close to widget"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Scrollable Message History Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#F8FAF9] dark:bg-[#070B11]/50">
              {/* Initial Welcome Greeting when no turns yet */}
              {turns.length === 0 && (
                <div className="space-y-4 py-2">
                  <div className="p-4 rounded-2xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900/90 shadow-2xs space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full overflow-hidden bg-[#0D3B36] p-0.5 flex items-center justify-center shrink-0">
                        <Image src="/chatbot.png" alt="" width={24} height={24} className="w-full h-full object-contain" />
                      </div>
                      <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                        Namaste! I am {ASSISTANT_NAME}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                      Ask me about accounts, ARR at risk, renewals, pending approvals or rules in your preferred language or using voice.
                    </p>
                  </div>

                  {/* Catalog questions chips */}
                  <div className="space-y-2">
                    <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider font-mono">
                      Suggested Questions
                    </span>
                    {catalog.isLoading && (
                      <div className="flex flex-wrap gap-1.5 animate-pulse">
                        <div className="h-6 w-28 bg-slate-200 dark:bg-slate-800 rounded-full" />
                        <div className="h-6 w-36 bg-slate-200 dark:bg-slate-800 rounded-full" />
                      </div>
                    )}
                    {questions.length > 0 && <QuestionChips questions={questions} onPick={pick} />}
                  </div>
                </div>
              )}

              {/* Message Turns */}
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

              {/* Voice Speech Error Banner */}
              {speechError && (
                <div className="p-2.5 rounded-xl border border-rose-200 bg-rose-50 text-[11px] text-rose-700">
                  {speechError}
                </div>
              )}

              <div ref={endRef} />
            </div>

            {/* Bottom Input Form Area */}
            <div className="p-3 border-t border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-[#0D1522] shrink-0">
              <form onSubmit={submit} className="flex items-center gap-2">
                <input
                  type="text"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  maxLength={500}
                  autoComplete="off"
                  placeholder={
                    isListening
                      ? `Listening in ${currentLangObj.label}... Speak now`
                      : `Ask in ${currentLangObj.label} or English...`
                  }
                  className={clsx(
                    "flex-1 min-w-0 px-3.5 py-2 rounded-full border text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0D3B36] transition-colors",
                    isListening
                      ? "border-rose-400 bg-rose-50/40 text-rose-900"
                      : "border-[#DEE5E1] dark:border-slate-700 bg-[#F5F8F6] dark:bg-slate-800/80"
                  )}
                />

                {/* Mic Speech-to-Text Button */}
                {hasSttSupport && (
                  <button
                    type="button"
                    onClick={handleVoiceInputClick}
                    aria-label={isListening ? "Stop listening" : `Speak in ${currentLangObj.label}`}
                    title={isListening ? "Stop listening" : `Click to speak (${currentLangObj.label})`}
                    className={clsx(
                      "w-8 h-8 rounded-full flex items-center justify-center transition-colors cursor-pointer shrink-0",
                      isListening
                        ? "bg-rose-600 text-white hover:bg-rose-700 ring-4 ring-rose-200 animate-pulse"
                        : "border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-[#0D3B36] hover:border-[#0D3B36]"
                    )}
                  >
                    {isListening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                  </button>
                )}

                {/* Send Button */}
                <button
                  type="submit"
                  disabled={!draft.trim() || isListening}
                  aria-label="Send"
                  className="w-8 h-8 rounded-full bg-[#0D3B36] hover:bg-[#124B45] text-white flex items-center justify-center transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer shrink-0 shadow-xs active:scale-95"
                >
                  <ArrowUp className="w-4 h-4" />
                </button>
              </form>
            </div>
          </div>
        </>
      )}
    </>
  );
}

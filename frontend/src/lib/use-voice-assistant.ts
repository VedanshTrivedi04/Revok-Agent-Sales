"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Web Speech API interface augmentations
interface SpeechRecognitionResult {
  readonly length: number;
  [index: number]: {
    readonly transcript: string;
    readonly confidence: number;
  };
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: {
    readonly length: number;
    [index: number]: SpeechRecognitionResult;
  };
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message?: string;
}

interface ISpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: ((this: ISpeechRecognition, ev: Event) => void) | null;
  onresult: ((this: ISpeechRecognition, ev: SpeechRecognitionEvent) => void) | null;
  onerror: ((this: ISpeechRecognition, ev: SpeechRecognitionErrorEvent) => void) | null;
  onend: ((this: ISpeechRecognition, ev: Event) => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => ISpeechRecognition;
    webkitSpeechRecognition?: new () => ISpeechRecognition;
  }
}

export interface SupportedLanguage {
  code: string;
  name: string;
  label: string;
  script?: string;
}

export const INDIAN_LANGUAGES: SupportedLanguage[] = [
  { code: "en-IN", name: "English (India)", label: "English" },
  { code: "hi-IN", name: "हिन्दी (Hindi)", label: "Hindi" },
  { code: "bn-IN", name: "বাংলা (Bengali)", label: "Bengali" },
  { code: "te-IN", name: "తెలుగు (Telugu)", label: "Telugu" },
  { code: "mr-IN", name: "मराठी (Marathi)", label: "Marathi" },
  { code: "ta-IN", name: "தமிழ் (Tamil)", label: "Tamil" },
  { code: "gu-IN", name: "ગુજરાતી (Gujarati)", label: "Gujarati" },
  { code: "kn-IN", name: "ಕನ್ನಡ (Kannada)", label: "Kannada" },
  { code: "ml-IN", name: "മലയാളം (Malayalam)", label: "Malayalam" },
  { code: "pa-IN", name: "ਪੰਜਾਬੀ (Punjabi)", label: "Punjabi" },
  { code: "ur-IN", name: "اردو (Urdu)", label: "Urdu" },
];

/** Strip markdown and format numbers/symbols cleanly for natural speech */
function sanitizeForSpeech(raw: string): string {
  return raw
    .replace(/\bhttps?:\/\/\S+/gi, "") // remove URLs
    .replace(/[*_#`~[\]]/g, "") // remove markdown formatting
    .replace(/\$(\d+)/g, "$1 dollars") // read $ as dollars
    .replace(/\s+/g, " ")
    .trim();
}

const STORAGE_KEY_AUTO_SPEAK = "riddhi_auto_speak";
const STORAGE_KEY_LANG = "riddhi_voice_lang";

export function useVoiceAssistant() {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingTurnId, setSpeakingTurnId] = useState<number | null>(null);
  const [hasSttSupport, setHasSttSupport] = useState(false);
  const [hasTtsSupport, setHasTtsSupport] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [language, setLanguageState] = useState<string>("en-IN");

  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  const onSpeechResultRef = useRef<((text: string) => void) | null>(null);
  const languageRef = useRef<string>("en-IN");

  // Keep ref synchronized
  useEffect(() => {
    languageRef.current = language;
  }, [language]);

  // Check browser support and load preferences on mount
  useEffect(() => {
    if (typeof window === "undefined") return;

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    setHasSttSupport(Boolean(SpeechRec));
    setHasTtsSupport(typeof window.speechSynthesis !== "undefined");

    try {
      const savedAuto = localStorage.getItem(STORAGE_KEY_AUTO_SPEAK);
      if (savedAuto !== null) {
        setAutoSpeak(savedAuto === "true");
      }
      const savedLang = localStorage.getItem(STORAGE_KEY_LANG);
      if (savedLang && INDIAN_LANGUAGES.some((l) => l.code === savedLang)) {
        setLanguageState(savedLang);
        languageRef.current = savedLang;
      }
    } catch {
      // ignore localStorage blocks
    }
  }, []);

  const setLanguage = useCallback((code: string) => {
    setLanguageState(code);
    languageRef.current = code;
    try {
      localStorage.setItem(STORAGE_KEY_LANG, code);
    } catch {
      // ignore
    }
  }, []);

  const toggleAutoSpeak = useCallback(() => {
    setAutoSpeak((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY_AUTO_SPEAK, String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
    setSpeakingTurnId(null);
  }, []);

  const speak = useCallback((text: string, turnId?: number) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    // Cancel any current utterance first
    window.speechSynthesis.cancel();

    const cleanText = sanitizeForSpeech(text);
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    const currentLang = languageRef.current;
    utterance.lang = currentLang;

    // Pick best matching voice for selected language
    const langPrefix = currentLang.split("-")[0]; // e.g. "hi", "en", "te", "ta", etc.
    const voices = window.speechSynthesis.getVoices();

    const matchingVoice =
      voices.find((v) => v.lang.toLowerCase() === currentLang.toLowerCase()) ||
      voices.find((v) => v.lang.toLowerCase().startsWith(langPrefix)) ||
      voices.find(
        (v) =>
          v.name.toLowerCase().includes(langPrefix) ||
          v.lang.startsWith("en-IN") ||
          v.lang.startsWith("en")
      );

    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    utterance.onstart = () => {
      setIsSpeaking(true);
      setSpeakingTurnId(turnId ?? null);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      setSpeakingTurnId(null);
    };

    utterance.onerror = (e) => {
      if (e.error !== "canceled" && e.error !== "interrupted") {
        console.warn("Speech synthesis error:", e.error);
      }
      setIsSpeaking(false);
      setSpeakingTurnId(null);
    };

    window.speechSynthesis.speak(utterance);
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // already stopped
      }
    }
    setIsListening(false);
  }, []);

  const startListening = useCallback(
    (onResult: (text: string) => void) => {
      if (typeof window === "undefined") return;
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        setSpeechError("Speech recognition is not supported in this browser.");
        return;
      }

      // Stop any ongoing speech output so mic doesn't capture Riddhi's own voice
      stopSpeaking();
      setSpeechError(null);
      onSpeechResultRef.current = onResult;

      try {
        if (recognitionRef.current) {
          try {
            recognitionRef.current.abort();
          } catch {
            // ignore
          }
        }

        const instance = new SpeechRec();
        instance.continuous = false;
        instance.interimResults = false;
        instance.lang = languageRef.current; // Dynamic Indian language

        instance.onstart = () => {
          setIsListening(true);
          setSpeechError(null);
        };

        instance.onresult = (e: SpeechRecognitionEvent) => {
          const result = e.results[0]?.[0]?.transcript;
          if (result && onSpeechResultRef.current) {
            onSpeechResultRef.current(result);
          }
        };

        instance.onerror = (e: SpeechRecognitionErrorEvent) => {
          if (e.error === "no-speech") {
            setSpeechError("No speech detected. Please try speaking again.");
          } else if (e.error === "not-allowed") {
            setSpeechError("Microphone permission denied. Please allow microphone access.");
          } else {
            setSpeechError(`Voice error: ${e.error}`);
          }
          setIsListening(false);
        };

        instance.onend = () => {
          setIsListening(false);
        };

        recognitionRef.current = instance;
        instance.start();
      } catch (err) {
        console.error("Failed to start speech recognition:", err);
        setSpeechError("Failed to access microphone.");
        setIsListening(false);
      }
    },
    [stopSpeaking]
  );

  // Clean up any pending speech / recognition on unmount or tab switch
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopSpeaking();
        stopListening();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      stopSpeaking();
      stopListening();
    };
  }, [stopSpeaking, stopListening]);

  return {
    isListening,
    isSpeaking,
    speakingTurnId,
    hasSttSupport,
    hasTtsSupport,
    speechError,
    autoSpeak,
    language,
    setLanguage,
    toggleAutoSpeak,
    speak,
    stopSpeaking,
    startListening,
    stopListening,
  };
}

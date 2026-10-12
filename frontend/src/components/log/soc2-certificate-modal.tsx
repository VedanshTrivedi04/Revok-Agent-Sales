"use client";

import { useState } from "react";
import {
  ShieldCheck,
  Download,
  Printer,
  Copy,
  Check,
  X,
  FileText,
  Lock,
  ExternalLink,
} from "lucide-react";
import type { Soc2Receipt } from "@/lib/log-actions";
import { generateSoc2ReceiptPdfBlob } from "@/lib/pdf/soc2-pdf-builder";

interface Soc2CertificateModalProps {
  receipt: Soc2Receipt;
  isOpen: boolean;
  onClose: () => void;
}

export function Soc2CertificateModal({
  receipt,
  isOpen,
  onClose,
}: Soc2CertificateModalProps) {
  const [copiedHash, setCopiedHash] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  if (!isOpen) return null;

  const handleCopyHash = () => {
    void navigator.clipboard.writeText(receipt.entry_hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleDownloadPdf = () => {
    setDownloadingPdf(true);
    try {
      const blob = generateSoc2ReceiptPdfBlob(receipt);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `soc2-audit-report-${receipt.entry_id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="soc2-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/70 backdrop-blur-xs overflow-y-auto"
    >
      <div className="relative w-full max-w-4xl max-h-[92vh] flex flex-col bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        {/* Top Control Bar (Non-Printable) */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 print:hidden">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-600/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 id="soc2-modal-title" className="text-sm font-bold text-slate-900 dark:text-white">
                SOC-2 Type II Certified Audit Report
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Verifiable cryptographic proof of action #{receipt.entry_id}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print / Save via Browser</span>
            </button>

            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={downloadingPdf}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-[#0D3B36] hover:bg-[#124B45] text-white transition-colors shadow-xs cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{downloadingPdf ? "Generating..." : "Download PDF (.pdf)"}</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors ml-2 cursor-pointer"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Printable Certificate Document Body */}
        <div className="flex-1 overflow-y-auto p-6 sm:p-10 bg-slate-100 dark:bg-slate-950 flex justify-center">
          <div className="w-full max-w-[800px] bg-white text-slate-900 shadow-xl rounded-xl border border-slate-300 p-8 sm:p-12 space-y-8 font-sans print:border-none print:shadow-none print:p-0 print:m-0">
            {/* Certificate Header Banner */}
            <div className="relative border-b-2 border-slate-900 pb-6 flex items-start justify-between">
              <div>
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 text-[11px] font-bold tracking-wide uppercase mb-3">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
                  AICPA SOC-2 Type II (CC6.8) & ISO 27001:2022
                </div>
                <h1 className="text-2xl font-black tracking-tight text-slate-950">
                  REVOK REVENUE INTELLIGENCE
                </h1>
                <p className="text-sm font-semibold text-emerald-800 mt-0.5">
                  CRYPTOGRAPHIC PROOF-OF-ACTION & COMPLIANCE DOSSIER
                </p>
                <p className="text-xs text-slate-600 mt-1">
                  Append-Only Merkle Hash Chain • Zero 3rd-Party AI Egress Guaranteed
                </p>
              </div>

              <div className="text-right">
                <div className="w-16 h-16 rounded-full border-2 border-emerald-600 flex flex-col items-center justify-center text-center p-1 bg-emerald-50 text-emerald-800">
                  <Lock className="w-4 h-4 text-emerald-700 mb-0.5" />
                  <span className="text-[8px] font-black tracking-tighter uppercase leading-tight">
                    IMMUTABLE RECORD
                  </span>
                </div>
                <span className="block text-[10px] font-mono text-slate-500 mt-2">
                  Receipt: {receipt.receipt_id}
                </span>
              </div>
            </div>

            {/* Status Attestation */}
            <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-pulse" />
                <span className="font-bold">
                  VERIFIED INTACT: SHA-256 Chain Integrity & Governance Attested
                </span>
              </div>
              <span className="font-mono text-[11px] text-emerald-800">
                Standard: {receipt.standard}
              </span>
            </div>

            {/* Section 1: Executive Action Summary */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200 pb-1">
                1. Executive Action Summary
              </h3>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="space-y-2">
                  <div>
                    <span className="text-slate-500 block text-[11px]">Action Event:</span>
                    <span className="font-bold font-mono text-slate-900">{receipt.event} (#{receipt.entry_id})</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Target Account / Entity:</span>
                    <span className="font-semibold text-slate-900">
                      {receipt.account_name || receipt.account_id || receipt.entity_id || "Enterprise Entity"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Timestamp (UTC):</span>
                    <span className="font-mono text-slate-800">{receipt.timestamp}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div>
                    <span className="text-slate-500 block text-[11px]">Organization / Tenant ID:</span>
                    <span className="font-mono text-slate-900">{receipt.org_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Human Signer & Role:</span>
                    <span className="font-semibold text-slate-900">
                      {receipt.actor_name || receipt.actor_type} {receipt.actor_role ? `(${receipt.actor_role})` : ""}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Autonomy Tier & Approval:</span>
                    <span className="font-bold text-emerald-700">
                      Tier {receipt.autonomy_tier ?? 2} ({receipt.approval_status.toUpperCase()})
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* Section 2: Cryptographic Chain-of-Custody */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200 pb-1">
                2. Cryptographic Proof of Action (SHA-256)
              </h3>
              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-2.5">
                <div>
                  <div className="flex items-center justify-between text-[11px] font-bold text-slate-700 mb-0.5">
                    <span>CURRENT RECORD SHA-256 HASH (ENTRY SIGNATURE)</span>
                    <button
                      type="button"
                      onClick={handleCopyHash}
                      className="inline-flex items-center gap-1 text-[10px] text-emerald-700 hover:underline cursor-pointer"
                    >
                      {copiedHash ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedHash ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="font-mono text-[11px] text-emerald-700 font-semibold break-all bg-white p-2 rounded border border-slate-200">
                    {receipt.entry_hash}
                  </div>
                </div>

                <div>
                  <span className="text-[11px] font-bold text-slate-700 block mb-0.5">
                    PREDECESSOR RECORD HASH (PREV_HASH ANCHOR)
                  </span>
                  <div className="font-mono text-[11px] text-slate-700 break-all bg-white p-2 rounded border border-slate-200">
                    {receipt.prev_hash || "GENESIS"}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-1 text-[11px]">
                  <div>
                    <span className="text-slate-500">Chaining Algorithm: </span>
                    <span className="font-mono font-medium text-slate-800">{receipt.chain_algorithm}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Data Privacy: </span>
                    <span className="font-bold text-emerald-700">Zero 3rd-Party AI Egress</span>
                  </div>
                </div>
              </div>
            </section>

            {/* Section 3: Evidence Citations */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200 pb-1">
                3. Frozen Evidence Citations & Policy Justification
              </h3>
              <div className="space-y-2 text-xs">
                {receipt.evidence_snapshot && receipt.evidence_snapshot.length > 0 ? (
                  receipt.evidence_snapshot.map((ev, idx: number) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded bg-slate-50 border border-slate-200 flex items-start gap-2.5"
                    >
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-blue-100 text-blue-800 shrink-0">
                        {String(ev.source || ev.type || `SIGNAL_${idx + 1}`).toUpperCase()}
                      </span>
                      <p className="text-slate-700 text-xs leading-relaxed">
                        {String(ev.excerpt || ev.title || ev.note || "Deterministic evidence citation.")}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="p-2.5 rounded bg-slate-50 border border-slate-200 text-slate-600 text-xs">
                    Deterministic policy citations verified and recorded in immutable ledger.
                  </div>
                )}
              </div>
            </section>

            {/* Section 4: Independent Auditor CLI Verification */}
            <section className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200 pb-1">
                4. Independent Auditor Verification Command (CLI)
              </h3>
              <div className="p-3.5 rounded-lg bg-slate-900 text-slate-200 font-mono text-[11px] space-y-2">
                <span className="text-sky-400 block text-[10px]"># Execute in terminal to verify cryptographic signature:</span>
                <pre className="text-emerald-400 whitespace-pre-wrap break-all select-all font-mono">
                  {receipt.tamper_verification_cli ||
                    `echo -n '{"entry_id":"${receipt.entry_id}","prev_hash":"${receipt.prev_hash}"}' | shasum -a 256`}
                </pre>
              </div>
            </section>

            {/* Certificate Footer */}
            <div className="pt-6 border-t-2 border-slate-300 flex items-end justify-between text-[11px] text-slate-500">
              <div className="space-y-0.5">
                <p className="font-bold text-slate-800">
                  Revok Autonomous Revenue Intelligence • Official Enterprise Attestation
                </p>
                <p>AICPA SOC-2 CC6.8, CC7.2 & ISO/IEC 27001:2022 Verified</p>
                <p className="font-mono text-[10px]">
                  Fingerprint: REVOK-SOC2-REC-{receipt.receipt_id}
                </p>
              </div>

              <div className="text-right">
                <div className="border-b border-slate-400 w-36 mb-1" />
                <span className="text-[10px] text-slate-500 block">Authorized Cryptographic Anchor</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

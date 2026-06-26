"use client";

import * as React from "react";
import { Search, X, ExternalLink, RotateCcw } from "lucide-react";
import type { Record_ } from "@/lib/types";
import { Card, SentimentBadge, Chip } from "@/components/ui";
import { driverColor, fmtReach } from "@/lib/format";

function uniq(records: Record_[], key: keyof Record_): string[] {
  return Array.from(new Set(records.map((r) => String(r[key] ?? "")).filter(Boolean))).sort();
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-700 outline-none focus:border-brand focus:ring-1 focus:ring-brand"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function Explorer({ records }: { records: Record_[] }) {
  const [q, setQ] = React.useState("");
  const [driver, setDriver] = React.useState("");
  const [sub, setSub] = React.useState("");
  const [sentiment, setSentiment] = React.useState("");
  const [channel, setChannel] = React.useState("");
  const [selected, setSelected] = React.useState<Record_ | null>(null);

  const drivers = React.useMemo(() => uniq(records, "driver"), [records]);
  const subs = React.useMemo(
    () => uniq(driver ? records.filter((r) => r.driver === driver) : records, "sub_driver"),
    [records, driver]
  );
  const sentiments = ["Positive", "Neutral", "Negative"];
  const channels = React.useMemo(() => uniq(records, "channel"), [records]);

  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    return records
      .filter((r) => (driver ? r.driver === driver : true))
      .filter((r) => (sub ? r.sub_driver === sub : true))
      .filter((r) => (sentiment ? r.sentiment === sentiment : true))
      .filter((r) => (channel ? r.channel === channel : true))
      .filter((r) =>
        needle
          ? `${r.Title ?? ""} ${r.text} ${r.source}`.toLowerCase().includes(needle)
          : true
      )
      .sort((a, b) => (b.reach ?? 0) - (a.reach ?? 0));
  }, [records, q, driver, sub, sentiment, channel]);

  const reset = () => {
    setQ("");
    setDriver("");
    setSub("");
    setSentiment("");
    setChannel("");
  };

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <label className="flex flex-col gap-1 text-xs">
              <span className="font-medium text-slate-500">Search</span>
              <div className="relative">
                <Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search title, content, source…"
                  className="w-full rounded-md border border-slate-200 bg-white py-1.5 pl-8 pr-2 text-sm outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                />
              </div>
            </label>
          </div>
          <div className="lg:col-span-2">
            <Select label="Driver" value={driver} onChange={(v) => { setDriver(v); setSub(""); }} options={drivers} />
          </div>
          <div className="lg:col-span-3">
            <Select label="Sub-driver" value={sub} onChange={setSub} options={subs} />
          </div>
          <div className="lg:col-span-1">
            <Select label="Sentiment" value={sentiment} onChange={setSentiment} options={sentiments} />
          </div>
          <div className="lg:col-span-2">
            <Select label="Channel" value={channel} onChange={setChannel} options={channels} />
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span>
            <span className="font-mono font-semibold text-slate-800">{filtered.length}</span> of{" "}
            {records.length} mentions
          </span>
          <button
            onClick={reset}
            className="inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </button>
        </div>
      </Card>

      {/* Table */}
      <Card className="overflow-hidden">
        <div className="max-h-[62vh] overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">Date</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Mention</th>
                <th className="px-3 py-2 font-medium">Driver</th>
                <th className="px-3 py-2 font-medium">Sub-driver</th>
                <th className="px-3 py-2 font-medium">Sentiment</th>
                <th className="px-3 py-2 text-right font-medium">Reach</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.record_id}
                  onClick={() => setSelected(r)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(r);
                    }
                  }}
                  tabIndex={0}
                  role="button"
                  aria-label={`Open mention from ${r.source}`}
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50 focus:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand"
                >
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                    {r.date ? r.date.slice(0, 10) : "—"}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-600">{r.source}</td>
                  <td className="max-w-[360px] px-3 py-2">
                    <p className="truncate text-slate-800">{r.Title || r.text}</p>
                  </td>
                  <td className="px-3 py-2">
                    <Chip color={driverColor(r.driver)}>{r.driver}</Chip>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">{r.sub_driver}</td>
                  <td className="px-3 py-2">
                    <SentimentBadge sentiment={r.sentiment} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-xs text-slate-600">
                    {fmtReach(r.reach)}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-10 text-center text-sm text-slate-400">
                    No mentions match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {selected && <DetailDrawer record={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-0.5 text-sm text-slate-700">{children}</div>
    </div>
  );
}

function DetailDrawer({ record: r, onClose }: { record: Record_; onClose: () => void }) {
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <div className="flex items-center gap-2">
            <SentimentBadge sentiment={r.sentiment} />
            <Chip color={driverColor(r.driver)}>{r.driver}</Chip>
          </div>
          <button
            onClick={onClose}
            className="cursor-pointer rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-auto px-4 py-4">
          {r.Title && <h3 className="text-base font-semibold text-slate-900">{r.Title}</h3>}
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{r.text}</p>

          <div className="grid grid-cols-2 gap-3 border-t border-slate-100 pt-3">
            <Field label="Source">{r.source}</Field>
            <Field label="Tier / Channel">{r.source_tier} · {r.channel}</Field>
            <Field label="Date">{r.date ? r.date.slice(0, 10) : "—"}</Field>
            <Field label="Reach">{fmtReach(r.reach)}</Field>
            <Field label="Sub-driver">{r.sub_driver}</Field>
            <Field label="Emotion">{r.emotion}</Field>
            <Field label="Theme">{r.theme}</Field>
            <Field label="Brand salience">{r.brand_salience}</Field>
            <Field label="Confidence">
              {r.sentiment_confidence != null ? r.sentiment_confidence.toFixed(2) : "—"}
            </Field>
            <Field label="Classified by">{r.classification_source}</Field>
          </div>

          {(r.people_mentioned || r.competitors_mentioned || r.keyphrases) && (
            <div className="space-y-2 border-t border-slate-100 pt-3">
              {r.people_mentioned && <Field label="People">{r.people_mentioned}</Field>}
              {r.competitors_mentioned && <Field label="Competitors">{r.competitors_mentioned}</Field>}
              {r.keyphrases && <Field label="Keyphrases">{r.keyphrases}</Field>}
            </div>
          )}
        </div>

        {r.url && (
          <div className="border-t border-slate-100 px-4 py-3">
            <a
              href={r.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline"
            >
              <ExternalLink className="h-4 w-4" /> View original
            </a>
          </div>
        )}
      </aside>
    </div>
  );
}

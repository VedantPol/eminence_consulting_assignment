"use client";

import * as React from "react";
import { LayoutDashboard, Search, Lightbulb, ShieldCheck } from "lucide-react";
import type { Insights, Record_ } from "@/lib/types";
import Overview, { type Drill } from "@/components/Overview";
import Explorer from "@/components/Explorer";
import InsightsView from "@/components/Insights";

type Tab = "overview" | "explorer" | "insights";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "explorer", label: "Content Explorer", icon: Search },
  { id: "insights", label: "Insights", icon: Lightbulb },
];

export default function Dashboard({
  insights,
  records,
}: {
  insights: Insights;
  records: Record_[];
}) {
  const [tab, setTab] = React.useState<Tab>("overview");
  const c = insights.counts;
  const rhs = insights.reputation_health_score;

  // deep-linkable tabs: read #hash on mount, keep it in sync on change
  React.useEffect(() => {
    const h = window.location.hash.replace("#", "") as Tab;
    if (h === "overview" || h === "explorer" || h === "insights") setTab(h);
  }, []);
  const selectTab = (t: Tab) => {
    setTab(t);
    if (typeof window !== "undefined") window.history.replaceState(null, "", `#${t}`);
  };

  // click a chart segment in Overview → jump to the Explorer with that filter
  const [explorerInit, setExplorerInit] = React.useState<Drill & { nonce: number }>({ nonce: 0 });
  const drill = (d: Drill) => {
    setExplorerInit({ ...d, nonce: Date.now() });
    selectTab("explorer");
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-sm font-semibold leading-tight text-slate-900">
                Reputation Intelligence
              </h1>
              <p className="text-xs text-slate-500">
                {insights.brand} · {c.final_relevant} mentions analyzed
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">
              Reputation Health{" "}
              <span className="font-mono font-semibold text-slate-900">
                {rhs.score}/100
              </span>{" "}
              · {rhs.band}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="mx-auto max-w-7xl px-3">
          <nav className="flex gap-1">
            {TABS.map((t) => {
              const Icon = t.icon;
              const active = tab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => selectTab(t.id)}
                  className={`flex cursor-pointer items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
                    active
                      ? "border-brand text-brand"
                      : "border-transparent text-slate-500 hover:text-slate-800"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {t.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Body */}
      <main className="mx-auto max-w-7xl px-5 py-6">
        {tab === "overview" && <Overview insights={insights} onDrill={drill} />}
        {tab === "explorer" && <Explorer records={records} init={explorerInit} />}
        {tab === "insights" && <InsightsView insights={insights} />}
      </main>

      <footer className="mx-auto max-w-7xl px-5 pb-8 pt-2 text-xs text-slate-400">
        Generated from an automated cleaning → classification → intelligence
        pipeline (FinBERT · DeBERTa zero-shot · Claude Sonnet 4.6). Static data,
        no backend.
      </footer>
    </div>
  );
}

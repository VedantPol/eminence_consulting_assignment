"use client";

import * as React from "react";
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Users,
  Quote,
  CheckCircle2,
} from "lucide-react";
import type { Insights, SubDriverRow } from "@/lib/types";
import { Card, CardHeader, SentimentBadge } from "@/components/ui";
import { netColor, fmtNet, fmtReach } from "@/lib/format";
import { DriverSentimentStacked } from "@/components/charts";

function NetBar({ value }: { value: number }) {
  // map [-1,1] to a centered bar
  const pct = Math.min(Math.abs(value), 1) * 50;
  const color = netColor(value);
  return (
    <div className="relative h-2 w-full rounded-full bg-slate-100">
      <div className="absolute left-1/2 top-0 h-full w-px bg-slate-300" />
      <div
        className="absolute top-0 h-full rounded-full"
        style={{
          background: color,
          width: `${pct}%`,
          left: value >= 0 ? "50%" : `${50 - pct}%`,
        }}
      />
    </div>
  );
}

function DriverList({ rows, positive }: { rows: SubDriverRow[]; positive: boolean }) {
  const filtered = rows
    .filter((r) => (positive ? r.net_sentiment > 0.02 : r.net_sentiment < -0.02))
    .sort((a, b) => (positive ? b.net_sentiment - a.net_sentiment : a.net_sentiment - b.net_sentiment))
    .slice(0, 6);
  if (filtered.length === 0)
    return <p className="px-4 py-6 text-center text-sm text-slate-400">None.</p>;
  return (
    <ul className="divide-y divide-slate-100">
      {filtered.map((r) => (
        <li key={r.sub_driver} className="px-4 py-2.5">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-slate-700">{r.sub_driver}</span>
            <span className="font-mono text-xs font-semibold" style={{ color: netColor(r.net_sentiment) }}>
              {fmtNet(r.net_sentiment)}
            </span>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <NetBar value={r.net_sentiment} />
            <span className="whitespace-nowrap text-[11px] text-slate-400">
              {r.mentions} mentions
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

function findings(ins: Insights): string[] {
  const out: string[] = [];
  const rhs = ins.reputation_health_score;
  out.push(
    `Reputation Health is ${rhs.score}/100 (${rhs.band}), with overall net sentiment ${fmtNet(
      ins.net_sentiment_overall
    )} and ${ins.share_of_voice.share_of_voice_pct}% share of voice versus ${
      Object.keys(ins.share_of_voice.competitor_mentions).length
    } competitors named.`
  );
  const drivers = [...ins.driver_breakdown].sort((a, b) => a.net_sentiment - b.net_sentiment);
  const worst = drivers[0];
  const best = drivers[drivers.length - 1];
  if (best) out.push(`${best.driver} is the strongest driver (net ${fmtNet(best.net_sentiment)}, ${best.mentions} mentions).`);
  if (worst) out.push(`${worst.driver} is the weakest driver (net ${fmtNet(worst.net_sentiment)}); all negative coverage concentrates here.`);
  const worstTheme = [...ins.themes].sort((a, b) => a.net_sentiment - b.net_sentiment)[0];
  if (worstTheme) out.push(`"${worstTheme.label}" is the most negative theme (net ${fmtNet(worstTheme.net_sentiment)}, ${worstTheme.size} mentions) — the priority for response.`);
  const cv = ins.classification_validation as any;
  if (cv?.driver_accuracy_zeroshot_pct)
    out.push(`Classification validated against a Claude Sonnet 4.6 silver-gold reference: ${cv.driver_accuracy_zeroshot_pct}% driver accuracy (macro-F1 ${cv.driver_macro_f1_zeroshot}).`);
  return out;
}

export default function InsightsView({ insights }: { insights: Insights }) {
  const f = findings(insights);
  return (
    <div className="space-y-4">
      {/* Key findings */}
      <Card>
        <CardHeader title="Key findings" subtitle="Auto-generated from the classified dataset" />
        <ul className="space-y-2 px-4 py-4">
          {f.map((t, i) => (
            <li key={i} className="flex gap-2.5 text-sm text-slate-700">
              <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand" />
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </Card>

      {/* Positive / Negative drivers */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Positive reputation drivers"
            right={<TrendingUp className="h-4 w-4 text-pos" />}
          />
          <DriverList rows={insights.sub_driver_breakdown} positive />
        </Card>
        <Card>
          <CardHeader
            title="Negative reputation drivers"
            right={<TrendingDown className="h-4 w-4 text-neg" />}
          />
          <DriverList rows={insights.sub_driver_breakdown} positive={false} />
        </Card>
      </div>

      {/* Heatmap + spokespeople */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Where sentiment concentrates" subtitle="Driver × sentiment" />
          <div className="px-3 pb-4 pt-4">
            <DriverSentimentStacked matrix={insights.driver_x_sentiment} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Spokesperson sentiment" right={<Users className="h-4 w-4 text-slate-400" />} />
          <ul className="divide-y divide-slate-100">
            {insights.spokesperson_sentiment.slice(0, 6).map((s) => (
              <li key={s.person} className="flex items-center justify-between px-4 py-2 text-sm">
                <span className="text-slate-700">{s.person}</span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">{s.mentions}×</span>
                  <span className="font-mono text-xs font-semibold" style={{ color: netColor(s.net_sentiment) }}>
                    {fmtNet(s.net_sentiment)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Risk queue */}
      <Card className="overflow-hidden">
        <CardHeader
          title="Risk queue"
          subtitle="Negative, reach-weighted mentions for the attention queue"
          right={<AlertTriangle className="h-4 w-4 text-accent" />}
        />
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">Sub-driver</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Mention</th>
                <th className="px-3 py-2 text-right font-medium">Reach</th>
                <th className="px-3 py-2 text-right font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {insights.risk_queue.slice(0, 8).map((r) => (
                <tr key={r.record_id} className="border-t border-slate-100">
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-600">{r.sub_driver}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">{r.source}</td>
                  <td className="max-w-[360px] px-3 py-2">
                    <p className="truncate text-slate-700">{r.snippet}</p>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-xs text-slate-500">
                    {fmtReach(r.reach)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right">
                    <span className="font-mono text-xs font-semibold text-neg">
                      {r.risk_score.toFixed(2)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Quotable mentions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <QuoteCard title="Top positive mentions" rows={insights.top_positive_mentions} positive />
        <QuoteCard title="Top negative mentions" rows={insights.top_negative_mentions} positive={false} />
      </div>
    </div>
  );
}

function QuoteCard({
  title,
  rows,
  positive,
}: {
  title: string;
  rows: Insights["top_positive_mentions"];
  positive: boolean;
}) {
  const color = positive ? "#22C55E" : "#EF4444";
  return (
    <Card>
      <CardHeader title={title} right={<Quote className="h-4 w-4" style={{ color }} />} />
      <ul className="space-y-3 px-4 py-4">
        {rows.slice(0, 4).map((m) => (
          <li key={m.record_id} className="border-l-2 pl-3" style={{ borderColor: color }}>
            <p className="text-sm text-slate-700">{m.snippet}</p>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
              <span>{m.source}</span>
              <span>·</span>
              <span>{m.sub_driver}</span>
              <span>·</span>
              <span className="font-mono">reach {fmtReach(m.reach)}</span>
              {m.url && (
                <a href={m.url} target="_blank" rel="noreferrer" className="text-brand hover:underline">
                  view
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

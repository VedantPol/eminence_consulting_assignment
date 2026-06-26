"use client";

import * as React from "react";
import type { Insights } from "@/lib/types";
import { Card, CardHeader, StatCard } from "@/components/ui";
import { SENTIMENT_COLORS, fmtNet } from "@/lib/format";
import {
  ReputationGauge,
  SentimentDonut,
  DriverBar,
  SubDriverBar,
  ThemesBar,
  TemporalArea,
} from "@/components/charts";

export type Drill = {
  driver?: string;
  sub_driver?: string;
  sentiment?: string;
  theme?: string;
};

export default function Overview({
  insights,
  onDrill,
}: {
  insights: Insights;
  onDrill: (d: Drill) => void;
}) {
  const c = insights.counts;
  const rhs = insights.reputation_health_score;
  const sov = insights.share_of_voice;
  const sentDist = insights.distributions.sentiment;
  const cv = insights.classification_validation as any;

  const worstTheme = [...insights.themes].sort(
    (a, b) => a.net_sentiment - b.net_sentiment
  )[0];

  return (
    <div className="space-y-4">
      {/* headline */}
      <Card className="border-l-4 border-l-brand p-4">
        <p className="text-sm text-slate-700">
          <span className="font-semibold text-slate-900">
            Reputation Health {rhs.score}/100 ({rhs.band}).
          </span>{" "}
          Overall net sentiment {fmtNet(insights.net_sentiment_overall)} across{" "}
          {c.final_relevant} mentions; share of voice {sov.share_of_voice_pct}%.
          {worstTheme && (
            <>
              {" "}
              Key risk theme:{" "}
              <span className="font-medium text-neg">
                {worstTheme.label} ({fmtNet(worstTheme.net_sentiment)})
              </span>
              .
            </>
          )}
        </p>
      </Card>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Mentions analyzed"
          value={c.final_relevant}
          sub={`${c.raw} raw · ${c.duplicates_removed} dupes · ${c.irrelevant_removed} off-topic removed`}
        />
        <StatCard
          label="Net sentiment"
          value={fmtNet(insights.net_sentiment_overall)}
          sub={`${sentDist.Positive?.count ?? 0} pos · ${sentDist.Negative?.count ?? 0} neg`}
          accent="#22C55E"
        />
        <StatCard
          label="Share of voice"
          value={`${sov.share_of_voice_pct}%`}
          sub={`vs ${Object.keys(sov.competitor_mentions).length} competitors`}
          accent="#F59E0B"
        />
        <StatCard
          label="Driver accuracy"
          value={cv?.driver_accuracy_zeroshot_pct ? `${cv.driver_accuracy_zeroshot_pct}%` : "—"}
          sub={cv?.driver_macro_f1_zeroshot ? `macro-F1 ${cv.driver_macro_f1_zeroshot} vs Claude` : "validated"}
          accent="#7C3AED"
        />
      </div>

      {/* Row A: gauge / sentiment / time */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Reputation Health Score" subtitle="Composite 0–100 index" />
          <div className="px-4 pb-2 pt-4">
            <ReputationGauge score={rhs.score} band={rhs.band} />
            <div className="mt-1 flex flex-wrap justify-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
              {Object.entries(rhs.components).map(([k, v]) => (
                <span key={k}>
                  {k.replace(/_/g, " ")}{" "}
                  <span className="font-mono text-slate-700">{v}</span>
                </span>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Sentiment distribution" subtitle="Click a segment to explore" />
          <div className="px-4 pb-4 pt-2">
            <SentimentDonut dist={sentDist} onSelect={(s) => onDrill({ sentiment: s })} />
            <div className="mt-1 flex justify-center gap-4 text-xs">
              {["Positive", "Neutral", "Negative"].map((s) => (
                <span key={s} className="inline-flex items-center gap-1.5 text-slate-600">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: SENTIMENT_COLORS[s] }}
                  />
                  {s} <span className="font-mono text-slate-800">{sentDist[s]?.count ?? 0}</span>
                </span>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Mentions over time" subtitle="Monthly volume" />
          <div className="px-2 pb-3 pt-3">
            <TemporalArea rows={insights.temporal} />
          </div>
        </Card>
      </div>

      {/* Row B: driver / sub-driver */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Reputation drivers" subtitle="3-driver framework · click to explore" />
          <div className="px-3 pb-4 pt-4">
            <DriverBar rows={insights.driver_breakdown} onSelect={(d) => onDrill({ driver: d })} />
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Sub-parameter distribution" subtitle="8 sub-drivers · click to explore" />
          <div className="px-3 pb-4 pt-4">
            <SubDriverBar
              rows={insights.sub_driver_breakdown}
              onSelect={(s) => onDrill({ sub_driver: s })}
            />
          </div>
        </Card>
      </div>

      {/* Row C: themes */}
      <Card>
        <CardHeader
          title="Top discussion themes"
          subtitle="Named by Claude Sonnet 4.6 · bar colour = net sentiment · click to explore"
        />
        <div className="px-3 pb-4 pt-4">
          <ThemesBar themes={insights.themes} onSelect={(t) => onDrill({ theme: t })} />
        </div>
      </Card>
    </div>
  );
}

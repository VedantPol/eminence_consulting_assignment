"use client";

import * as React from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  AreaChart,
  Area,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  LabelList,
  CartesianGrid,
} from "recharts";
import {
  SENTIMENT_COLORS,
  driverColor,
  netColor,
} from "@/lib/format";
import type { DriverRow, SubDriverRow, ThemeRow, TemporalRow } from "@/lib/types";

const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  fontSize: 12,
  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
};

/* --- Reputation Health gauge (semicircle) ------------------------------- */
export function ReputationGauge({ score, band }: { score: number; band: string }) {
  const color = score >= 70 ? "#22C55E" : score >= 55 ? "#3B82F6" : score >= 45 ? "#F59E0B" : "#EF4444";
  const data = [{ name: "score", value: score, fill: color }];
  return (
    <div className="relative h-[150px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          innerRadius="78%"
          outerRadius="100%"
          data={data}
          startAngle={180}
          endAngle={0}
          barSize={18}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar background={{ fill: "#EEF2F7" }} dataKey="value" cornerRadius={10} isAnimationActive={false} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-x-0 bottom-2 flex flex-col items-center">
        <span className="font-mono text-4xl font-semibold text-slate-900">
          {score.toFixed(1)}
        </span>
        <span className="text-xs font-medium" style={{ color }}>
          {band} · /100
        </span>
      </div>
    </div>
  );
}

/* --- Sentiment donut ----------------------------------------------------- */
export function SentimentDonut({
  dist,
  onSelect,
}: {
  dist: Record<string, { count: number; pct: number }>;
  onSelect?: (sentiment: string) => void;
}) {
  const order = ["Positive", "Neutral", "Negative"];
  const data = order
    .filter((k) => dist[k])
    .map((k) => ({ name: k, value: dist[k].count, pct: dist[k].pct }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={52}
          outerRadius={80}
          paddingAngle={2}
          stroke="none"
          isAnimationActive={false}
          onClick={(d: any) => onSelect?.(d?.name)}
          className={onSelect ? "cursor-pointer" : undefined}
        >
          {data.map((d) => (
            <Cell key={d.name} fill={SENTIMENT_COLORS[d.name]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(v: number, _n, p: any) => [`${v} (${p.payload.pct}%)`, p.payload.name]}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

/* --- Driver distribution (horizontal bar, colored by driver) ------------- */
export function DriverBar({ rows, onSelect }: { rows: DriverRow[]; onSelect?: (d: string) => void }) {
  const data = [...rows].sort((a, b) => a.mentions - b.mentions);
  return (
    <ResponsiveContainer width="100%" height={150}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ left: 8, right: 28 }}
        onClick={(s: any) => s?.activeLabel && onSelect?.(s.activeLabel)}
        className={onSelect ? "cursor-pointer" : undefined}
      >
        <CartesianGrid horizontal={false} stroke="#f1f5f9" />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="driver"
          width={150}
          tick={{ fontSize: 11, fill: "#475569" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f8fafc" }} />
        <Bar dataKey="mentions" radius={[0, 5, 5, 0]} barSize={22} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.driver} fill={driverColor(d.driver)} />
          ))}
          <LabelList dataKey="mentions" position="right" style={{ fontSize: 11, fill: "#334155" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- Sub-driver distribution (horizontal bar, colored by parent) --------- */
export function SubDriverBar({ rows, onSelect }: { rows: SubDriverRow[]; onSelect?: (s: string) => void }) {
  const data = [...rows].sort((a, b) => a.mentions - b.mentions);
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 30)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ left: 8, right: 28 }}
        onClick={(s: any) => s?.activeLabel && onSelect?.(s.activeLabel)}
        className={onSelect ? "cursor-pointer" : undefined}
      >
        <CartesianGrid horizontal={false} stroke="#f1f5f9" />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="sub_driver"
          width={210}
          tick={{ fontSize: 11, fill: "#475569" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          cursor={{ fill: "#f8fafc" }}
          formatter={(v: number, _n, p: any) => [`${v} mentions · net ${p.payload.net_sentiment}`, p.payload.driver]}
        />
        <Bar dataKey="mentions" radius={[0, 5, 5, 0]} barSize={18} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.sub_driver} fill={driverColor(d.driver)} />
          ))}
          <LabelList dataKey="mentions" position="right" style={{ fontSize: 11, fill: "#334155" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- Themes (horizontal bar, colored by net sentiment) ------------------- */
export function ThemesBar({ themes, onSelect }: { themes: ThemeRow[]; onSelect?: (t: string) => void }) {
  const data = [...themes].sort((a, b) => a.size - b.size);
  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 32)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ left: 8, right: 30 }}
        onClick={(s: any) => s?.activeLabel && onSelect?.(s.activeLabel)}
        className={onSelect ? "cursor-pointer" : undefined}
      >
        <CartesianGrid horizontal={false} stroke="#f1f5f9" />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={210}
          tick={{ fontSize: 11, fill: "#475569" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          cursor={{ fill: "#f8fafc" }}
          formatter={(v: number, _n, p: any) => [`${v} mentions · net ${p.payload.net_sentiment}`, p.payload.label]}
        />
        <Bar dataKey="size" radius={[0, 5, 5, 0]} barSize={18} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.theme_id} fill={netColor(d.net_sentiment)} />
          ))}
          <LabelList dataKey="size" position="right" style={{ fontSize: 11, fill: "#334155" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- Mentions over time (area) ------------------------------------------ */
export function TemporalArea({ rows }: { rows: TemporalRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={190}>
      <AreaChart data={rows} margin={{ left: -16, right: 12, top: 6 }}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#f1f5f9" />
        <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="mentions" stroke="#2563EB" strokeWidth={2} fill="url(#g)" isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* --- Driver x sentiment (stacked horizontal bar) ------------------------- */
export function DriverSentimentStacked({
  matrix,
}: {
  matrix: Record<string, Record<string, number>>;
}) {
  const data = Object.entries(matrix).map(([driver, m]) => ({
    driver,
    Positive: m.Positive ?? 0,
    Neutral: m.Neutral ?? 0,
    Negative: m.Negative ?? 0,
  }));
  return (
    <ResponsiveContainer width="100%" height={170}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid horizontal={false} stroke="#f1f5f9" />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="driver"
          width={150}
          tick={{ fontSize: 11, fill: "#475569" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f8fafc" }} />
        {(["Positive", "Neutral", "Negative"] as const).map((s, i, arr) => (
          <Bar
            key={s}
            dataKey={s}
            stackId="a"
            fill={SENTIMENT_COLORS[s]}
            barSize={22}
            isAnimationActive={false}
            radius={i === arr.length - 1 ? [0, 5, 5, 0] : 0}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

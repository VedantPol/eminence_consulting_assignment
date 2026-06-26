// Shared colors + formatting helpers.

export const SENTIMENT_COLORS: Record<string, string> = {
  Positive: "#22C55E",
  Neutral: "#94A3B8",
  Negative: "#EF4444",
};

export const DRIVER_COLORS: Record<string, string> = {
  "Brand Perception": "#2563EB",
  "User Experience": "#7C3AED",
  "Responsible Business Practices": "#0D9488",
};

export function sentimentColor(s: string): string {
  return SENTIMENT_COLORS[s] ?? "#94A3B8";
}

export function driverColor(d: string): string {
  return DRIVER_COLORS[d] ?? "#1E40AF";
}

// diverging color for a net-sentiment value in [-1, 1]
export function netColor(v: number): string {
  if (v > 0.05) return "#22C55E";
  if (v < -0.05) return "#EF4444";
  return "#94A3B8";
}

export function fmtReach(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(0) + "K";
  return String(n);
}

export function fmtPct(n: number): string {
  return `${n > 0 ? "+" : ""}${(n * 100).toFixed(0)}%`;
}

export function fmtNet(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;
}

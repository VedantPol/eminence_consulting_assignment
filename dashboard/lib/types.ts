// Minimal types for the fields the dashboard reads from the pipeline output.

export interface DistEntry { count: number; pct: number }
export type Dist = Record<string, DistEntry>;

export interface DriverRow {
  driver: string;
  mentions: number;
  net_sentiment: number;
  positive: number;
  neutral: number;
  negative: number;
  avg_reach: number | null;
}

export interface SubDriverRow {
  sub_driver: string;
  driver: string;
  mentions: number;
  net_sentiment: number;
  positive: number;
  negative: number;
}

export interface ThemeRow {
  theme_id: number;
  label: string;
  description: string | null;
  size: number;
  net_sentiment: number;
  dominant_driver: string | null;
  top_sentiment: string | null;
}

export interface MentionRow {
  record_id: number;
  source: string;
  driver: string;
  sub_driver: string;
  reach: number | null;
  date: string | null;
  snippet: string;
  url: string;
}

export interface RiskRow {
  record_id: number;
  date: string | null;
  source: string;
  source_tier: string;
  driver: string;
  sub_driver: string;
  sentiment: string;
  risk_score: number;
  reach: number | null;
  snippet: string;
  url: string;
}

export interface SpokespersonRow {
  person: string;
  mentions: number;
  net_sentiment: number;
  positive: number;
  negative: number;
}

export interface TemporalRow { month: string; mentions: number; net_sentiment: number }

export interface Insights {
  brand: string;
  counts: Record<string, number>;
  reputation_health_score: {
    score: number;
    band: string;
    components: Record<string, number>;
    weights: Record<string, number>;
  };
  share_of_voice: {
    brand: string;
    brand_mentions: number;
    share_of_voice_pct: number;
    competitor_mentions: Record<string, number>;
  };
  distributions: Record<string, Dist>;
  net_sentiment_overall: number;
  driver_breakdown: DriverRow[];
  sub_driver_breakdown: SubDriverRow[];
  driver_x_sentiment: Record<string, Record<string, number>>;
  channel_x_sentiment: Record<string, Record<string, number>>;
  themes: ThemeRow[];
  temporal: TemporalRow[];
  spokesperson_sentiment: SpokespersonRow[];
  top_positive_mentions: MentionRow[];
  top_negative_mentions: MentionRow[];
  risk_queue: RiskRow[];
  sentiment_validation: { agreement_pct: number; n_compared: number } & Record<string, unknown>;
  classification_validation: Record<string, unknown>;
  low_confidence_records: number;
}

export interface Record_ {
  record_id: number;
  date: string | null;
  source: string;
  source_tier: string;
  channel: string;
  url: string;
  Title: string | null;
  text: string;
  driver: string;
  sub_driver: string;
  sentiment: string;
  sentiment_confidence: number | null;
  emotion: string;
  theme: string;
  brand_salience: string;
  reach: number | null;
  risk_flag: boolean;
  classification_source: string;
  people_mentioned: string;
  competitors_mentioned: string;
  keyphrases: string;
}

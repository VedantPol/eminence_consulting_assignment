import insightsData from "@/data/insights.json";
import recordsData from "@/data/classified.json";
import type { Insights, Record_ } from "@/lib/types";
import Dashboard from "@/components/Dashboard";

// Static data is inlined at build time — no backend, no fetch.
const insights = insightsData as unknown as Insights;
const records = recordsData as unknown as Record_[];

export default function Page() {
  return <Dashboard insights={insights} records={records} />;
}

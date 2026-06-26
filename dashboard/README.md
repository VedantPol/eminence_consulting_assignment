# Reputation Intelligence Dashboard (Part 2)

A Next.js dashboard for the ICICI Prudential AMC reputation-intelligence dataset
produced by the Part 1 pipeline. **No backend** — it reads the pre-computed
`insights.json` + `classified.json` as static data, so it deploys to Vercel as a
plain static-rendered app.

## Stack
Next.js 14 (App Router) · TypeScript · Tailwind CSS · Recharts · Lucide icons.

## Run locally
```bash
cd dashboard
npm install
npm run dev        # http://localhost:3000
```

## The three sections (per the assignment)
- **Overview** — total mentions, Reputation Health gauge, sentiment / driver /
  sub-parameter distributions, top discussion themes, mentions over time.
- **Content Explorer** — search + filter by driver, sub-driver, sentiment and
  channel; click any row to read the original content and all metadata.
- **Insights** — key findings, positive vs negative reputation drivers,
  driver × sentiment concentration, risk queue, spokesperson sentiment, and the
  top quotable positive/negative mentions.

## Data
`data/insights.json` and `data/classified.json` are copied from the pipeline's
`outputs/`. To refresh after re-running Part 1:
```bash
cp ../outputs/insights.json   data/insights.json
cp ../outputs/classified.json data/classified.json
```

## Deploy to Vercel
1. Push the repo to GitHub.
2. Vercel → New Project → import the repo.
3. **Set Root Directory to `dashboard`** (the app lives in a subfolder).
4. Deploy — framework auto-detected as Next.js. Done.

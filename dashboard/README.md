# Dashboard (Part 2)

A Next.js dashboard for the reputation dataset from Part 1. It reads the pre-computed
`insights.json` and `classified.json` as static files, so there is no backend and it deploys to
Vercel as a static-rendered app.

Built with Next.js 14, TypeScript, Tailwind, and Recharts.

## Run

```bash
npm install
npm run dev      # http://localhost:3000
```

## The three views

- **Overview** — total mentions, a Reputation Health gauge, sentiment / driver / sub-parameter
  distributions, named themes, and volume over time. Click any chart to drill into the Explorer with
  that filter applied.
- **Content Explorer** — search and filter by driver, sub-driver, sentiment, channel, theme, and date
  range; click a row to read the original text and open the source; export the filtered set to CSV.
- **Insights** — key findings, strongest and weakest drivers, where sentiment concentrates, a
  reach-weighted risk queue, spokesperson sentiment, and the most-quoted positive and negative mentions.

## Data

`data/insights.json` and `data/classified.json` come from the pipeline's `outputs/`. To refresh:

```bash
cp ../outputs/insights.json   data/insights.json
cp ../outputs/classified.json data/classified.json
```

## Deploy on Vercel

Import the repository, set the **root directory to `dashboard`**, and deploy. Next.js is detected
automatically; there are no environment variables to set.

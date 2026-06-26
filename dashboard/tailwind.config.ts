import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // BFSI / consulting palette (from the design system)
        navy: "#1E3A8A",
        brand: { DEFAULT: "#1E40AF", light: "#3B82F6" },
        accent: "#F59E0B",
        canvas: "#F8FAFC",
        // sentiment
        pos: "#22C55E",
        neu: "#94A3B8",
        neg: "#EF4444",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;

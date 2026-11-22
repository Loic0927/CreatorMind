import type { Config } from "tailwindcss";

// Palette: semantic Ice Sea tokens backed by CSS custom properties.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--color-canvas) / <alpha-value>)",
        sidebar: "rgb(var(--color-sidebar) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        field: "rgb(var(--color-field) / <alpha-value>)",
        subtle: "rgb(var(--color-subtle) / <alpha-value>)",
        line: "rgb(var(--color-line) / <alpha-value>)",
        "line-strong": "rgb(var(--color-line-strong) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        "ink-soft": "rgb(var(--color-ink-soft) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        primary: "rgb(var(--color-primary) / <alpha-value>)",
        "primary-hover": "rgb(var(--color-primary-hover) / <alpha-value>)",
        selected: "rgb(var(--color-selected) / <alpha-value>)",
        "selected-ink": "rgb(var(--color-selected-ink) / <alpha-value>)",
        sky: "rgb(var(--color-sky) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        "danger-line": "rgb(var(--color-danger-line) / <alpha-value>)",
        "danger-bg": "rgb(var(--color-danger-bg) / <alpha-value>)",
      },
      backgroundImage: {
        "canvas-gradient": "linear-gradient(180deg, #E4F0FD 0%, #F2F1FA 100%)",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(10, 30, 68, 0.08)",
        float: "0 8px 24px rgba(10, 30, 68, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;

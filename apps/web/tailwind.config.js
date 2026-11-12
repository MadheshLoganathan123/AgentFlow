/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        app: {
          bg: "#090D16",
          secondary: "#0D1320",
          nav: "#0B1020",
          card: "#111827",
          cardSecondary: "#151E2E",
          panel: "#192338",
        },
        border: {
          default: "#253249",
          subtle: "#1D293B",
          active: "#3B82F6",
        },
        accent: {
          primary: "#3B82F6",
          secondary: "#60A5FA",
          purple: "#A78BFA",
          emerald: "#10B981",
          amber: "#F59E0B",
          rose: "#EF4444",
        },
        content: {
          primary: "#F1F5F9",
          secondary: "#94A3B8",
          muted: "#64748B",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: {
        "dark-sm": "0 1px 2px 0 rgba(0, 0, 0, 0.5)",
        "dark-md": "0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -2px rgba(0, 0, 0, 0.3)",
        "dark-lg": "0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.3)",
      },
    },
  },
  plugins: [],
};

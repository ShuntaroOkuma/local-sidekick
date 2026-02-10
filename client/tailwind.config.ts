import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        focused: "#22c55e",
        drowsy: "#ef4444",
        distracted: "#eab308",
        away: "#6b7280",
        idle: "#9ca3af",
      },
    },
  },
  plugins: [],
};

export default config;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        slate: { 950: "#020617" },
      },
      boxShadow: {
        glow: "0 0 40px rgba(56, 189, 248, 0.12)",
        card: "0 4px 24px rgba(0,0,0,0.45)",
      },
    },
  },
  plugins: [],
};

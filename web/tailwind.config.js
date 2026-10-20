/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#0c0b09", 900: "#141210", 800: "#1d1a16", 700: "#2a2620", 600: "#3a342b" },
        gold: { 300: "#e8d3a0", 400: "#d8b86e", 500: "#c9a24c", 600: "#a8843a" },
        parchment: "#ece4d3",
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', "Georgia", "serif"],
        body: ['"EB Garamond"', "Georgia", "serif"],
        ui: ['"Inter"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

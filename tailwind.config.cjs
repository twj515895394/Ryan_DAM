module.exports = {
  content: ["./index.html", "./apps/web/src/**/*.{vue,ts}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F5F5F7",
        ink: "#1D1D1F",
        muted: "#6E6E73",
        line: "#E5E5EA",
        accent: "#2563EB"
      },
      boxShadow: { soft: "0 18px 50px rgba(20, 25, 40, 0.06)" }
    }
  },
  plugins: []
};

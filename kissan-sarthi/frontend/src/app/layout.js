import "./globals.css";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";

export const metadata = {
  title: "Kissan Sarthi (किसान सारथी) — AI Smart Farming & Stubble Care",
  description:
    "AI-powered farming assistant for Indian farmers. Enter farm details, track crops with AI growth analysis, diagnose crop diseases from photos, and calculate post-harvest stubble pollution savings.",
  keywords: [
    "kissan sarthi",
    "farmer assistant",
    "crop disease diagnosis",
    "stubble management",
    "stop stubble burning",
    "agriculture ai",
    "indian farming",
    "krishi salahkar",
  ],
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <meta name="theme-color" content="#166534" />
      </head>
      <body>
        <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
          <Navbar />
          <main style={{ flex: 1 }}>{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}

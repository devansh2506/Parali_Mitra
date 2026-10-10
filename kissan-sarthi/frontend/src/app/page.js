"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  Sprout, 
  MapPin, 
  Wheat, 
  Stethoscope, 
  Recycle, 
  ArrowRight, 
  CheckCircle2, 
  Wind, 
  TrendingUp, 
  ShieldCheck, 
  Sun, 
  CloudRain, 
  Sparkles,
  Award
} from "lucide-react";
import { api } from "@/lib/api";

export default function HomePage() {
  const [stats, setStats] = useState({
    total_pledges: 142,
    total_acres_saved: 1250,
    total_co2_saved_kg: 2680000,
    total_pm25_saved_kg: 8400,
    equivalent_trees: 121800,
  });

  useEffect(() => {
    // Fetch real impact summary from backend
    api.getImpactSummary()
      .then((data) => {
        if (data && data.total_acres_saved > 0) {
          setStats(data);
        }
      })
      .catch(() => {
        // Fallback default demo metrics
      });
  }, []);

  return (
    <div style={{ paddingBottom: "4rem" }}>
      {/* ── Hero Section ── */}
      <section style={{
        position: "relative",
        overflow: "hidden",
        padding: "4.5rem 0 3.5rem",
        background: "linear-gradient(180deg, rgba(236, 253, 245, 0.7) 0%, rgba(245, 250, 246, 0.2) 100%)",
        borderBottom: "1px solid rgba(22, 163, 74, 0.12)"
      }}>
        {/* Soft eco ambient circles */}
        <div style={{
          position: "absolute",
          top: "-10%",
          right: "5%",
          width: "450px",
          height: "450px",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(74, 222, 128, 0.18) 0%, rgba(255,255,255,0) 70%)",
          filter: "blur(40px)",
          pointerEvents: "none"
        }} />
        <div style={{
          position: "absolute",
          bottom: "0%",
          left: "-5%",
          width: "380px",
          height: "380px",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(250, 204, 21, 0.15) 0%, rgba(255,255,255,0) 70%)",
          filter: "blur(40px)",
          pointerEvents: "none"
        }} />

        <div className="container" style={{ position: "relative", zIndex: 1 }}>
          <div style={{ maxWidth: "850px", margin: "0 auto", textAlign: "center" }}>
            {/* Top Tagline Badge */}
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              background: "#ffffff",
              border: "1px solid rgba(22, 163, 74, 0.25)",
              boxShadow: "var(--shadow-sm)",
              borderRadius: "var(--radius-full)",
              padding: "0.45rem 1.1rem",
              fontSize: "0.85rem",
              fontWeight: 600,
              color: "var(--primary-800)",
              marginBottom: "1.5rem"
            }}>
              <Sprout size={16} color="var(--primary-600)" />
              <span>भारत के अन्नदाताओं के लिए समर्पित AI कृषि सारथी</span>
              <span className="badge badge-gold" style={{ fontSize: "0.72rem" }}>
                100% Eco-Friendly
              </span>
            </div>

            {/* Main Headline */}
            <h1 style={{
              fontSize: "clamp(2.3rem, 5vw, 3.75rem)",
              fontWeight: 800,
              letterSpacing: "-0.03em",
              lineHeight: 1.15,
              marginBottom: "1.25rem",
              color: "var(--primary-950)"
            }}>
              Smart Farming from Sowing to Stubble: <br />
              <span className="gradient-text">Kissan Sarthi</span>
            </h1>

            {/* Subtitle */}
            <p style={{
              fontSize: "clamp(1.05rem, 2vw, 1.25rem)",
              color: "var(--text-body)",
              lineHeight: 1.6,
              marginBottom: "2.25rem",
              maxWidth: "720px",
              margin: "0 auto 2.25rem"
            }}>
              Enter your farm land details, track your sown crops with AI growth forecasting,
              diagnose crop diseases instantly with photo scan, and protect our environment by converting harvest stubble into wealth!
            </p>

            {/* Hero Action Buttons */}
            <div style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "1rem",
              justifyContent: "center",
              marginBottom: "3rem"
            }}>
              <Link href="/farms/new" id="hero-btn-add-farm" className="btn btn-primary btn-lg">
                <MapPin size={20} />
                <span>Register Your Farm</span>
                <ArrowRight size={18} />
              </Link>

              <Link href="/health" id="hero-btn-diagnose" className="btn btn-secondary btn-lg">
                <Stethoscope size={20} color="var(--primary-700)" />
                <span>Diagnose Crop Health</span>
              </Link>

              <Link href="/stubble" id="hero-btn-stubble" className="btn btn-accent btn-lg">
                <Recycle size={20} />
                <span>Stubble & Pollution Calculator</span>
              </Link>
            </div>

            {/* Live Eco Impact Counter Card */}
            <div className="glass-panel" style={{
              padding: "1.5rem 2rem",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "1.5rem",
              textAlign: "center"
            }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem", color: "var(--primary-700)", marginBottom: "0.25rem" }}>
                  <Award size={18} />
                  <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>Clean Air Pledges</span>
                </div>
                <div className="metric-value">{stats.total_pledges.toLocaleString()}+</div>
                <div className="metric-label">Farmers Committed</div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem", color: "var(--primary-700)", marginBottom: "0.25rem" }}>
                  <Wind size={18} />
                  <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>CO₂ Emissions Saved</span>
                </div>
                <div className="metric-value" style={{ color: "var(--primary-600)" }}>
                  {(stats.total_co2_saved_kg / 1000).toFixed(0)} <span style={{ fontSize: "1.2rem" }}>Tons</span>
                </div>
                <div className="metric-label">Pollution Prevented</div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem", color: "var(--earth-700)", marginBottom: "0.25rem" }}>
                  <Leaf size={18} />
                  <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>Acres Protected</span>
                </div>
                <div className="metric-value" style={{ color: "var(--earth-700)" }}>
                  {stats.total_acres_saved.toLocaleString()} <span style={{ fontSize: "1.2rem" }}>Acres</span>
                </div>
                <div className="metric-label">Zero-Burn Farmland</div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem", color: "var(--gold-600)", marginBottom: "0.25rem" }}>
                  <Sparkles size={18} />
                  <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>Tree Benefit Eqv.</span>
                </div>
                <div className="metric-value" style={{ color: "var(--gold-600)" }}>
                  {(stats.equivalent_trees || (stats.total_co2_saved_kg / 22)).toFixed(0).toLocaleString()}
                </div>
                <div className="metric-label">Trees Saved Equivalent</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 4 Step Farmer Journey Section ── */}
      <section style={{ padding: "4.5rem 0" }}>
        <div className="container">
          <div style={{ textAlign: "center", maxWidth: "700px", margin: "0 auto 3.5rem" }}>
            <span className="badge badge-green" style={{ marginBottom: "0.75rem" }}>
              आसान 4 चरण • Easy 4 Steps
            </span>
            <h2 style={{ fontSize: "2.3rem", color: "var(--primary-950)", marginBottom: "0.75rem" }}>
              How Kissan Sarthi Guides Your Farming
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: "1.05rem" }}>
              A complete end-to-end intelligent ecosystem built specifically to solve practical farming challenges in India.
            </p>
          </div>

          <div className="grid-2" style={{ gap: "2rem" }}>
            {/* Step 1: Farm Registration */}
            <div className="eco-card" style={{ position: "relative", overflow: "hidden" }}>
              <div style={{
                position: "absolute",
                top: "1.25rem",
                right: "1.25rem",
                fontSize: "3rem",
                fontWeight: 900,
                color: "rgba(22, 163, 74, 0.08)",
                lineHeight: 1
              }}>
                01
              </div>
              <div style={{
                width: "3.2rem",
                height: "3.2rem",
                borderRadius: "var(--radius-md)",
                background: "var(--primary-100)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--primary-700)",
                marginBottom: "1.25rem"
              }}>
                <MapPin size={26} />
              </div>
              <h3 style={{ fontSize: "1.4rem", marginBottom: "0.5rem", color: "var(--primary-950)" }}>
                1. Register Farm Land Details
              </h3>
              <p style={{ color: "var(--text-body)", fontSize: "0.95rem", marginBottom: "1.25rem" }}>
                Enter your farm location (State, District, Village), total area in acres, field dimensions,
                soil type (Alluvial, Black cotton, Red, Desert, etc.), and irrigation source.
              </p>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--primary-600)" />
                  Categorized Indian soil identification & irrigation mapping
                </li>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--primary-600)" />
                  Plot dimension tracking & multi-field support
                </li>
              </ul>
              <Link href="/farms/new" className="btn btn-secondary btn-sm" id="step1-btn">
                <span>Add Farm Land</span>
                <ArrowRight size={16} />
              </Link>
            </div>

            {/* Step 2: Crops & AI Growth Care */}
            <div className="eco-card" style={{ position: "relative", overflow: "hidden" }}>
              <div style={{
                position: "absolute",
                top: "1.25rem",
                right: "1.25rem",
                fontSize: "3rem",
                fontWeight: 900,
                color: "rgba(234, 179, 8, 0.12)",
                lineHeight: 1
              }}>
                02
              </div>
              <div style={{
                width: "3.2rem",
                height: "3.2rem",
                borderRadius: "var(--radius-md)",
                background: "var(--gold-100)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--earth-700)",
                marginBottom: "1.25rem"
              }}>
                <Wheat size={26} />
              </div>
              <h3 style={{ fontSize: "1.4rem", marginBottom: "0.5rem", color: "var(--primary-950)" }}>
                2. Add Crops & Get AI Analysis
              </h3>
              <p style={{ color: "var(--text-body)", fontSize: "0.95rem", marginBottom: "1.25rem" }}>
                Select sown crops (Wheat, Paddy, Mustard, Cotton, etc.), variety, and sowing date.
                Get instant AI harvest date prediction, stage-wise care calendar, fertilizer dosage, and pest risk forecasts.
              </p>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--earth-700)" />
                  AI harvest date & yield prediction (quintals/acre)
                </li>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--earth-700)" />
                  Week-by-week fertilizer & irrigation schedule
                </li>
              </ul>
              <Link href="/crops" className="btn btn-secondary btn-sm" id="step2-btn">
                <span>View Crop Analysis</span>
                <ArrowRight size={16} />
              </Link>
            </div>

            {/* Step 3: Crop Health Doctor */}
            <div className="eco-card" style={{ position: "relative", overflow: "hidden" }}>
              <div style={{
                position: "absolute",
                top: "1.25rem",
                right: "1.25rem",
                fontSize: "3rem",
                fontWeight: 900,
                color: "rgba(2, 132, 199, 0.1)",
                lineHeight: 1
              }}>
                03
              </div>
              <div style={{
                width: "3.2rem",
                height: "3.2rem",
                borderRadius: "var(--radius-md)",
                background: "var(--sky-100)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--sky-700)",
                marginBottom: "1.25rem"
              }}>
                <Stethoscope size={26} />
              </div>
              <h3 style={{ fontSize: "1.4rem", marginBottom: "0.5rem", color: "var(--primary-950)" }}>
                3. Photo Scan & Crop Doctor
              </h3>
              <p style={{ color: "var(--text-body)", fontSize: "0.95rem", marginBottom: "1.25rem" }}>
                Noticed yellow leaves, fungal spots, or pest attacks? Take a photo with your mobile,
                and our AI plant pathologist diagnoses the disease with immediate organic and safe chemical remedies.
              </p>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--sky-700)" />
                  Multimodal vision disease identification with severity alert
                </li>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--sky-700)" />
                  Dual remedies: Bio/Organic solutions + chemical dosage
                </li>
              </ul>
              <Link href="/health" className="btn btn-secondary btn-sm" id="step3-btn">
                <span>Scan Crop Photo</span>
                <ArrowRight size={16} />
              </Link>
            </div>

            {/* Step 4: Stubble Management & Clean Air */}
            <div className="eco-card" style={{ position: "relative", overflow: "hidden" }}>
              <div style={{
                position: "absolute",
                top: "1.25rem",
                right: "1.25rem",
                fontSize: "3rem",
                fontWeight: 900,
                color: "rgba(16, 185, 129, 0.12)",
                lineHeight: 1
              }}>
                04
              </div>
              <div style={{
                width: "3.2rem",
                height: "3.2rem",
                borderRadius: "var(--radius-md)",
                background: "var(--primary-100)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--primary-700)",
                marginBottom: "1.25rem"
              }}>
                <Recycle size={26} />
              </div>
              <h3 style={{ fontSize: "1.4rem", marginBottom: "0.5rem", color: "var(--primary-950)" }}>
                4. Harvest Stubble: Wealth from Waste
              </h3>
              <p style={{ color: "var(--text-body)", fontSize: "0.95rem", marginBottom: "1.25rem" }}>
                Post-harvest, calculate exact toxic air pollution (CO₂, PM2.5) prevented by not burning stubble.
                Explore profitable alternatives: Pusa bio-decomposer, mushroom farming, bio-pellets, and take the Eco Pledge!
              </p>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.88rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--primary-600)" />
                  Live carbon & particulate pollution prevention calculator
                </li>
                <li style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} color="var(--primary-600)" />
                  Profitable eco-alternatives + Official Eco Pledge Certificate
                </li>
              </ul>
              <Link href="/stubble" className="btn btn-primary btn-sm" id="step4-btn">
                <span>Stubble Calculator</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Eco Mission Showcase ── */}
      <section style={{
        padding: "4rem 0",
        background: "linear-gradient(135deg, #14532d 0%, #166534 100%)",
        color: "#ffffff"
      }}>
        <div className="container">
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "2.5rem",
            alignItems: "center"
          }}>
            <div>
              <span className="badge" style={{ background: "rgba(250, 204, 21, 0.2)", color: "#fef08a", border: "1px solid rgba(250, 204, 21, 0.4)", marginBottom: "1rem" }}>
                🌱 पर्यावरण रक्षा • Protecting Our Mother Earth
              </span>
              <h2 style={{ fontSize: "2.2rem", color: "#ffffff", marginBottom: "1rem" }}>
                Why Burning Crop Stubble Harms the Farmer Most
              </h2>
              <p style={{ color: "#dcfce7", fontSize: "1rem", lineHeight: 1.6, marginBottom: "1.5rem" }}>
                When paddy or wheat straw is burned, temperatures reach 300°C to 400°C in the top 3 inches of soil.
                This destroys essential bacteria, earthworms, and nitrogen, requiring extra expensive chemical fertilizers next season.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
                  <div style={{ background: "rgba(255,255,255,0.15)", borderRadius: "50%", padding: "0.3rem" }}>
                    <ShieldCheck size={18} color="#4ade80" />
                  </div>
                  <div>
                    <strong style={{ color: "#ffffff" }}>Preserves Soil Organic Carbon (SOC):</strong>
                    <span style={{ color: "#bbf7d0", fontSize: "0.9rem", display: "block" }}>
                      Mulching stubble back into soil increases organic matter by up to 0.4% in 3 years.
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
                  <div style={{ background: "rgba(255,255,255,0.15)", borderRadius: "50%", padding: "0.3rem" }}>
                    <TrendingUp size={18} color="#facc15" />
                  </div>
                  <div>
                    <strong style={{ color: "#ffffff" }}>Extra Income Potential:</strong>
                    <span style={{ color: "#bbf7d0", fontSize: "0.9rem", display: "block" }}>
                      Paddy straw can earn ₹1,500 to ₹2,500 per ton from pellet manufacturers and mushroom growers.
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="glass-panel" style={{
              background: "rgba(255, 255, 255, 0.12)",
              borderColor: "rgba(255, 255, 255, 0.25)",
              color: "#ffffff",
              padding: "2.25rem"
            }}>
              <h3 style={{ fontSize: "1.35rem", color: "#fef08a", marginBottom: "1rem" }}>
                🌾 Quick Farmer Stubble Facts:
              </h3>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "1rem", fontSize: "0.95rem" }}>
                <li style={{ borderBottom: "1px solid rgba(255,255,255,0.15)", paddingBottom: "0.75rem" }}>
                  <strong style={{ color: "#ffffff" }}>1 Ton of Paddy Straw contains:</strong>
                  <div style={{ color: "#bbf7d0", fontSize: "0.88rem", marginTop: "0.2rem" }}>
                    5.5 kg Nitrogen, 2.3 kg Phosphorus, 25 kg Potassium, and 1.2 kg Sulphur — all destroyed if burned!
                  </div>
                </li>
                <li style={{ borderBottom: "1px solid rgba(255,255,255,0.15)", paddingBottom: "0.75rem" }}>
                  <strong style={{ color: "#ffffff" }}>Pusa Bio-Decomposer:</strong>
                  <div style={{ color: "#bbf7d0", fontSize: "0.88rem", marginTop: "0.2rem" }}>
                    Decomposes stubble inside the soil within 20–25 days at a fraction of chemical fertilizer cost.
                  </div>
                </li>
                <li>
                  <strong style={{ color: "#ffffff" }}>Government Machinery Subsidies:</strong>
                  <div style={{ color: "#bbf7d0", fontSize: "0.88rem", marginTop: "0.2rem" }}>
                    Up to 50% subsidy for individual farmers and 80% for Custom Hiring Centers (CHCs) on Happy Seeders & Super SMS.
                  </div>
                </li>
              </ul>
              <div style={{ marginTop: "1.75rem" }}>
                <Link href="/stubble" className="btn btn-accent" style={{ width: "100%" }}>
                  <Recycle size={18} />
                  <span>Join Clean Air Movement</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function Leaf(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
    </svg>
  );
}

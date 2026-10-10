"use client";

import Link from "next/link";
import { Sprout, PhoneCall, ShieldCheck, HeartHandshake, Leaf, Wind } from "lucide-react";

export default function Footer() {
  return (
    <footer style={{
      background: "linear-gradient(180deg, rgba(240, 253, 244, 0.6) 0%, #062e16 100%)",
      borderTop: "1px solid rgba(22, 163, 74, 0.2)",
      marginTop: "5rem",
      paddingTop: "4rem",
      paddingBottom: "2.5rem",
      color: "#e2f1e6"
    }}>
      <div className="container">
        {/* Banner Card: Clean Air & Farmer First */}
        <div className="glass-panel" style={{
          background: "linear-gradient(135deg, rgba(20, 83, 45, 0.92) 0%, rgba(22, 101, 52, 0.88) 100%)",
          borderColor: "rgba(74, 222, 128, 0.3)",
          color: "#ffffff",
          padding: "2rem 2.5rem",
          marginBottom: "3.5rem",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1.5rem"
        }}>
          <div style={{ maxWidth: "600px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <span className="badge" style={{ background: "rgba(250, 204, 21, 0.2)", color: "#fef08a", border: "1px solid rgba(250, 204, 21, 0.4)" }}>
                <Wind size={14} /> स्वच्छ हवा अभियान • Clean Air Mission
              </span>
            </div>
            <h3 style={{ fontSize: "1.5rem", color: "#ffffff", marginBottom: "0.5rem" }}>
              पराली मत जलाएं, मिट्टी और हवा दोनों बचाएं! 🌾
            </h3>
            <p style={{ color: "#bbf7d0", fontSize: "0.95rem" }}>
              Every acre saved from burning prevents 2,000+ kg of toxic CO₂ and saves crucial soil microbes that boost your next harvest yield.
            </p>
          </div>
          <div>
            <Link href="/stubble" className="btn btn-accent btn-lg" id="footer-btn-stubble">
              <Leaf size={18} />
              <span>Calculate Your Pollution Saved</span>
            </Link>
          </div>
        </div>

        {/* 4 Column Footer Links */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "2.5rem",
          marginBottom: "3rem"
        }}>
          {/* Brand Info */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1rem" }}>
              <div style={{
                width: "2.2rem",
                height: "2.2rem",
                borderRadius: "10px",
                background: "var(--primary-500)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff"
              }}>
                <Sprout size={20} />
              </div>
              <span style={{ fontFamily: "var(--font-heading)", fontSize: "1.3rem", fontWeight: 800, color: "#ffffff" }}>
                Kissan Sarthi
              </span>
            </div>
            <p style={{ fontSize: "0.88rem", color: "#a7d7b5", lineHeight: 1.6, marginBottom: "1rem" }}>
              Empowering India’s farming community with artificial intelligence, crop diagnosis, precision care schedules, and sustainable post-harvest practices.
            </p>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <ShieldCheck size={16} color="#4ade80" />
              <span style={{ fontSize: "0.8rem", color: "#bbf7d0" }}>100% Free for all Indian Farmers</span>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h4 style={{ color: "#ffffff", fontSize: "1rem", marginBottom: "1.2rem", letterSpacing: "0.02em" }}>
              Application Modules
            </h4>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.65rem", fontSize: "0.9rem" }}>
              <li>
                <Link href="/farms" style={{ color: "#c6ebd1", transition: "color 0.2s" }}>
                  🏡 Farm Land Registration & Overview
                </Link>
              </li>
              <li>
                <Link href="/crops" style={{ color: "#c6ebd1", transition: "color 0.2s" }}>
                  🌾 Crop Sowing & Growth Stage AI
                </Link>
              </li>
              <li>
                <Link href="/health" style={{ color: "#c6ebd1", transition: "color 0.2s" }}>
                  🩺 AI Plant Pathology & Disease Doctor
                </Link>
              </li>
              <li>
                <Link href="/stubble" style={{ color: "#c6ebd1", transition: "color 0.2s" }}>
                  ♻️ Stubble Management & Eco Alternatives
                </Link>
              </li>
            </ul>
          </div>

          {/* Eco Alternatives */}
          <div>
            <h4 style={{ color: "#ffffff", fontSize: "1rem", marginBottom: "1.2rem" }}>
              Stubble Eco Solutions
            </h4>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.65rem", fontSize: "0.9rem", color: "#c6ebd1" }}>
              <li>🍂 Pusa Bio-Decomposer Spray</li>
              <li>🚜 In-situ Mulching & Happy Seeder</li>
              <li>🍄 Paddy Straw Mushroom Farming</li>
              <li>🔥 Bio-Pellets & Power Plant Co-firing</li>
              <li>🐄 Silage & Nutritive Animal Fodder</li>
            </ul>
          </div>

          {/* Support & Helplines */}
          <div>
            <h4 style={{ color: "#ffffff", fontSize: "1rem", marginBottom: "1.2rem" }}>
              Support & Emergency
            </h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.9rem", fontSize: "0.88rem" }}>
              <div style={{
                background: "rgba(255, 255, 255, 0.08)",
                padding: "0.85rem 1rem",
                borderRadius: "var(--radius-md)",
                border: "1px solid rgba(74, 222, 128, 0.2)"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#facc15", fontWeight: 700 }}>
                  <PhoneCall size={16} /> Kisan Call Center (Toll Free)
                </div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "#ffffff", marginTop: "0.2rem" }}>
                  1800-180-1551
                </div>
                <div style={{ fontSize: "0.75rem", color: "#a7d7b5", marginTop: "0.15rem" }}>
                  Available 6:00 AM to 10:00 PM (All 22 Languages)
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#a7d7b5", fontSize: "0.82rem" }}>
                <HeartHandshake size={16} color="#4ade80" />
                <span>Dedicated to the prosperity of Annadatas</span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div style={{
          borderTop: "1px solid rgba(74, 222, 128, 0.15)",
          paddingTop: "1.5rem",
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "1rem",
          fontSize: "0.82rem",
          color: "#8fc29e"
        }}>
          <p>© 2026 Kissan Sarthi (किसान सारथी). Made with 💚 for Sustainable Agriculture.</p>
          <p>Eco-friendly Farming • Zero Stubble Burning • AI Plant Care</p>
        </div>
      </div>
    </footer>
  );
}

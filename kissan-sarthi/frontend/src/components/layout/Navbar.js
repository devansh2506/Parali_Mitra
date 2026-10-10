"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { 
  Sprout, 
  MapPin, 
  Wheat, 
  Stethoscope, 
  Recycle, 
  PlusCircle, 
  Menu, 
  X,
  PhoneCall,
  Sparkles
} from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { href: "/farms", label: "My Farms", labelHi: "खेत", icon: MapPin },
    { href: "/crops", label: "Crops & AI Care", labelHi: "फसलें", icon: Wheat },
    { href: "/health", label: "Crop Doctor", labelHi: "फसल डॉक्टर", icon: Stethoscope },
    { href: "/stubble", label: "Stubble & Clean Air", labelHi: "पराली प्रबंधन", icon: Recycle },
  ];

  const isActive = (href) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header style={{
      position: "sticky",
      top: 0,
      zIndex: 50,
      background: "rgba(255, 255, 255, 0.88)",
      backdropFilter: "blur(16px)",
      WebkitBackdropFilter: "blur(16px)",
      borderBottom: "1px solid rgba(22, 163, 74, 0.18)",
      boxShadow: "0 4px 20px -2px rgba(20, 83, 45, 0.05)"
    }}>
      <div className="container" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: "4.5rem"
      }}>
        {/* Brand Logo */}
        <Link href="/" id="nav-brand-logo" style={{
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
          textDecoration: "none"
        }}>
          <div style={{
            width: "2.75rem",
            height: "2.75rem",
            borderRadius: "14px",
            background: "linear-gradient(135deg, #166534 0%, #16a34a 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            boxShadow: "0 4px 14px rgba(22, 163, 74, 0.35)"
          }}>
            <Sprout size={26} strokeWidth={2.4} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{
                fontFamily: "var(--font-heading)",
                fontSize: "1.35rem",
                fontWeight: 800,
                letterSpacing: "-0.02em",
                color: "var(--primary-950)"
              }}>
                Kissan Sarthi
              </span>
              <span className="badge badge-gold" style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem" }}>
                AI 🌱
              </span>
            </div>
            <p style={{
              fontSize: "0.75rem",
              color: "var(--text-muted)",
              fontWeight: 500,
              marginTop: "-2px"
            }}>
              किसान सारथी • Eco-Smart Agriculture
            </p>
          </div>
        </Link>

        {/* Desktop Nav Items */}
        <nav style={{
          display: "none",
          alignItems: "center",
          gap: "0.5rem"
        }} className="desktop-nav">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const active = isActive(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                id={`nav-link-${link.href.replace("/", "")}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.45rem",
                  padding: "0.55rem 0.95rem",
                  borderRadius: "var(--radius-full)",
                  fontSize: "0.9rem",
                  fontWeight: active ? 700 : 500,
                  color: active ? "var(--primary-900)" : "var(--text-body)",
                  background: active ? "var(--primary-100)" : "transparent",
                  border: active ? "1px solid var(--primary-300)" : "1px solid transparent",
                  transition: "all 0.18s ease"
                }}
              >
                <Icon size={18} color={active ? "var(--primary-700)" : "var(--text-muted)"} />
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* CTA & Actions */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "0.75rem"
        }}>
          <Link
            href="/farms/new"
            id="nav-btn-add-farm"
            className="btn btn-primary btn-sm"
            style={{ display: "none" }}
          >
            <PlusCircle size={16} />
            <span>Add Farm</span>
          </Link>

          <Link
            href="/health"
            id="nav-btn-quick-diagnose"
            className="btn btn-secondary btn-sm"
            style={{ display: "none" }}
          >
            <Sparkles size={16} color="var(--primary-600)" />
            <span>AI Doctor</span>
          </Link>

          {/* Toll Free Helpline Badge */}
          <a
            href="tel:18001801551"
            title="Kisan Call Center: 1800-180-1551"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              background: "var(--gold-100)",
              border: "1px solid var(--earth-300)",
              borderRadius: "var(--radius-full)",
              padding: "0.35rem 0.75rem",
              fontSize: "0.78rem",
              fontWeight: 600,
              color: "var(--earth-900)",
              textDecoration: "none"
            }}
          >
            <PhoneCall size={14} color="var(--earth-700)" />
            <span>Kisan Helpline 1800-180-1551</span>
          </a>

          {/* Mobile Menu Button */}
          <button
            id="mobile-nav-toggle"
            aria-label="Toggle navigation menu"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "2.5rem",
              height: "2.5rem",
              background: "var(--primary-50)",
              border: "1px solid var(--border-light)",
              borderRadius: "var(--radius-md)",
              cursor: "pointer",
              color: "var(--primary-900)"
            }}
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Nav Overlay */}
      {mobileMenuOpen && (
        <div style={{
          background: "#ffffff",
          borderTop: "1px solid var(--border-light)",
          padding: "1rem 1.25rem 1.5rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem"
        }}>
          {navLinks.map((link) => {
            const Icon = link.icon;
            const active = isActive(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.75rem 1rem",
                  borderRadius: "var(--radius-md)",
                  fontWeight: active ? 700 : 500,
                  color: active ? "var(--primary-900)" : "var(--text-body)",
                  background: active ? "var(--primary-100)" : "transparent"
                }}
              >
                <Icon size={20} color={active ? "var(--primary-700)" : "var(--text-muted)"} />
                <span>{link.label}</span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                  {link.labelHi}
                </span>
              </Link>
            );
          })}
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
            <Link
              href="/farms/new"
              onClick={() => setMobileMenuOpen(false)}
              className="btn btn-primary"
              style={{ flex: 1 }}
            >
              <PlusCircle size={16} />
              <span>Add Farm</span>
            </Link>
            <Link
              href="/health"
              onClick={() => setMobileMenuOpen(false)}
              className="btn btn-secondary"
              style={{ flex: 1 }}
            >
              <Stethoscope size={16} />
              <span>Diagnose</span>
            </Link>
          </div>
        </div>
      )}

      {/* Responsive Styles for Desktop Navigation */}
      <style jsx>{`
        @media (min-width: 860px) {
          .desktop-nav {
            display: flex !important;
          }
          #mobile-nav-toggle {
            display: none !important;
          }
          #nav-btn-add-farm {
            display: inline-flex !important;
          }
          #nav-btn-quick-diagnose {
            display: inline-flex !important;
          }
        }
      `}</style>
    </header>
  );
}

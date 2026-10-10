"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { 
  Recycle, 
  Wind, 
  TreePine, 
  Award, 
  CheckCircle2, 
  DollarSign, 
  Layers, 
  Flame, 
  ShieldCheck, 
  Leaf, 
  Sparkles, 
  ArrowRight, 
  Printer, 
  Heart, 
  TrendingUp,
  FileCheck2,
  Calendar
} from "lucide-react";
import { api } from "@/lib/api";

function StubbleContent() {
  const searchParams = useSearchParams();
  const preselectedCropId = searchParams.get("crop_id") || "";
  const initialArea = searchParams.get("area") || "5";

  const [crops, setCrops] = useState([]);
  const [selectedCropId, setSelectedCropId] = useState(preselectedCropId);
  const [areaAcres, setAreaAcres] = useState(initialArea);

  const [calculating, setCalculating] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [chosenAlternative, setChosenAlternative] = useState("Pusa Bio-Decomposer Microbial Spray");

  const [pledging, setPledging] = useState(false);
  const [pledgeCertificate, setPledgeCertificate] = useState(null);
  const [impactSummary, setImpactSummary] = useState(null);
  const [error, setError] = useState(null);

  const certificateRef = useRef(null);

  useEffect(() => {
    // Load crops and impact summary
    api.getCrops()
      .then((data) => {
        setCrops(data);
        if (!preselectedCropId && data.length > 0) {
          setSelectedCropId(data[0].id);
        }
      })
      .catch(() => {});

    api.getImpactSummary()
      .then((res) => setImpactSummary(res))
      .catch(() => {});
  }, [preselectedCropId]);

  const handleRunAnalysis = async (e) => {
    if (e) e.preventDefault();
    if (!selectedCropId) {
      setError("Please select a crop.");
      return;
    }
    if (!areaAcres || Number(areaAcres) <= 0) {
      setError("Please enter a valid stubble acreage.");
      return;
    }

    try {
      setError(null);
      setCalculating(true);
      const res = await api.analyzeStubble(selectedCropId, parseFloat(areaAcres));
      setAnalysisResult(res);
      if (res?.analysis?.eco_alternatives?.[0]?.method) {
        setChosenAlternative(res.analysis.eco_alternatives[0].method);
      }
    } catch (err) {
      setError(err.message || "Failed to analyze stubble");
    } finally {
      setCalculating(false);
    }
  };

  // Run on mount if crop is available
  useEffect(() => {
    if (selectedCropId && !analysisResult) {
      handleRunAnalysis();
    }
  }, [selectedCropId]);

  const handleTakePledge = async () => {
    try {
      setPledging(true);
      const cert = await api.recordPledge(selectedCropId, parseFloat(areaAcres), chosenAlternative);
      setPledgeCertificate(cert);
      // Refresh community impact
      api.getImpactSummary().then((res) => setImpactSummary(res)).catch(() => {});
    } catch (err) {
      alert("Error recording pledge: " + err.message);
    } finally {
      setPledging(false);
    }
  };

  const handlePrintCertificate = () => {
    window.print();
  };

  const pollution = analysisResult?.analysis?.pollution_if_burned || {
    co2_kg: Math.round(Number(areaAcres || 1) * 2225),
    pm25_kg: Math.round(Number(areaAcres || 1) * 7),
    pm10_kg: Math.round(Number(areaAcres || 1) * 9.5),
    equivalent_trees_needed: Math.round(Number(areaAcres || 1) * 101),
  };

  const alternatives = analysisResult?.analysis?.eco_alternatives || [
    {
      method: "Pusa Bio-Decomposer Microbial Spray",
      description: "ICAR-developed capsule & spray technology that turns crop stubble into rich organic manure directly inside the soil in 20-25 days.",
      benefits: ["Increases soil fertility & organic carbon", "Eliminates need for burning", "Zero diesel/machinery requirement"],
      estimated_cost: "₹300 - ₹500 per acre",
      estimated_revenue: "Saves ₹2,500 in chemical fertilizer costs",
      difficulty: "easy",
      time_required: "20-25 days",
      government_schemes: ["Subsidized by state agriculture departments", "Free distribution in key districts"],
    },
    {
      method: "In-Situ Mulching with Happy Seeder / Super SMS",
      description: "Direct sowing of wheat into standing paddy stubble without tilling or burning. Retains soil moisture and suppress weeds.",
      benefits: ["Saves 15-20 days of field preparation time", "Saves ₹1,800 to ₹2,500/acre in tractor diesel", "Protects soil moisture"],
      estimated_cost: "Custom hiring: ₹1,200 - ₹1,500 per acre",
      estimated_revenue: "Increases wheat yield by 1.5 - 2 quintals/acre",
      difficulty: "easy",
      time_required: "Direct single pass sowing",
      government_schemes: ["50% subsidy on individual machinery", "80% subsidy for CHCs"],
    },
    {
      method: "Commercial Bio-Pellets & Biomass Power Supply",
      description: "Baling crop straw and supplying to thermal power plants and boiler industries for green power generation under government co-firing mandates.",
      benefits: ["Guaranteed buyback price", "Removes straw completely from field", "Direct cash income for farmer"],
      estimated_cost: "Baling cost ₹800/acre",
      estimated_revenue: "₹1,500 to ₹2,200 per ton (approx ₹3,500 - ₹5,000 per acre)",
      difficulty: "medium",
      time_required: "3-5 days after harvesting",
      government_schemes: ["Govt 5% Biomass Co-firing Mandate in coal power plants"],
    },
    {
      method: "Paddy Straw Mushroom Cultivation",
      description: "Use high-silica crop straw as bed substrate for growing gourmet oyster and paddy straw mushrooms, yielding harvest in 15 days.",
      benefits: ["High-value cash crop from waste", "Zero field space required (indoor/shed)", "Post-mushroom spent substrate makes premium compost"],
      estimated_cost: "₹2,000 for 50 straw bundles & spawn",
      estimated_revenue: "₹15,000 to ₹25,000 per shed cycle",
      difficulty: "medium",
      time_required: "15-20 days per harvest",
      government_schemes: ["National Horticulture Mission mushroom subsidy"],
    },
    {
      method: "Cattle Fodder Enrichment & Silage",
      description: "Urea-molasses treatment of straw to increase crude protein from 3.5% to 7.5%, making it highly digestible for milch cattle.",
      benefits: ["Addresses dry fodder shortage", "Increases milk yield in buffaloes/cows", "Saves purchase of costly dry fodder"],
      estimated_cost: "₹400 per quintal treated",
      estimated_revenue: "Saves ₹6,000 in fodder costs per milch animal",
      difficulty: "easy",
      time_required: "21 days curing",
      government_schemes: ["National Livestock Mission"],
    },
  ];

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "5rem" }}>
      {/* ── Page Header ── */}
      <div style={{ marginBottom: "2.5rem", textAlign: "center", maxWidth: "800px", margin: "0 auto 2.5rem" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span className="badge badge-green">
            <Recycle size={14} /> चरण 4 • Step 4: Stubble Management & Clean Air
          </span>
        </div>
        <h1 style={{ fontSize: "2.4rem", color: "var(--primary-950)", marginBottom: "0.5rem" }}>
          Harvest Stubble: Save Air, Soil & Wealth
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "1.05rem" }}>
          Don&apos;t burn the golden leftover straw! Calculate exactly how much toxic pollution you can save, explore profitable alternatives, and receive your official Clean Air Eco-Warrior Certificate.
        </p>
      </div>

      {/* ── Community Aggregate Counter ── */}
      {impactSummary && (
        <div className="glass-panel" style={{
          padding: "1.25rem 2rem",
          marginBottom: "2.5rem",
          background: "linear-gradient(135deg, rgba(240, 253, 244, 0.8) 0%, rgba(254, 249, 195, 0.5) 100%)",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-around",
          gap: "1.5rem",
          textAlign: "center"
        }}>
          <div>
            <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--primary-900)" }}>
              {impactSummary.total_pledges} Farmers
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--primary-700)", fontWeight: 600 }}>
              Swachh Hawa Pledges Taken
            </div>
          </div>

          <div>
            <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--earth-700)" }}>
              {impactSummary.total_acres_saved} Acres
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--earth-700)", fontWeight: 600 }}>
              Farmland Kept Fire-Free
            </div>
          </div>

          <div>
            <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--primary-600)" }}>
              {(impactSummary.total_co2_saved_kg / 1000).toFixed(0)} Tons
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--primary-600)", fontWeight: 600 }}>
              CO₂ Emissions Prevented
            </div>
          </div>

          <div>
            <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--gold-600)" }}>
              {impactSummary.total_pm25_saved_kg} kg
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--gold-600)", fontWeight: 600 }}>
              PM2.5 Smog Dust Saved
            </div>
          </div>
        </div>
      )}

      {/* ── Calculator Input Form ── */}
      <div className="eco-card" style={{ padding: "2rem", marginBottom: "2.5rem" }}>
        <h3 style={{ fontSize: "1.25rem", color: "var(--primary-950)", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Flame size={20} color="var(--danger-500)" />
          Calculate Your Farm&apos;s Stubble Impact
        </h3>

        <form onSubmit={handleRunAnalysis} style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1.25rem",
          alignItems: "flex-end"
        }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="stubble-crop-select">
              Select Harvested Crop
            </label>
            <select
              id="stubble-crop-select"
              value={selectedCropId}
              onChange={(e) => setSelectedCropId(e.target.value)}
              className="form-select"
            >
              {crops.length > 0 ? (
                crops.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.crop_name} ({c.area_acres} Acres) — {c.current_stage}
                  </option>
                ))
              ) : (
                <option value="demo">Paddy / Rice (5.0 Acres)</option>
              )}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="stubble-area-input">
              Harvested Area with Stubble (Acres)
            </label>
            <input
              type="number"
              id="stubble-area-input"
              step="0.5"
              min="0.5"
              value={areaAcres}
              onChange={(e) => setAreaAcres(e.target.value)}
              className="form-input"
            />
          </div>

          <div>
            <button
              type="submit"
              id="btn-calc-pollution"
              disabled={calculating}
              className="btn btn-primary"
              style={{ width: "100%", padding: "0.75rem 1.25rem" }}
            >
              {calculating ? "Calculating..." : "Calculate Pollution Saved"}
            </button>
          </div>
        </form>
      </div>

      {/* ── Visual Pollution & Environment Savings Display ── */}
      <div style={{ marginBottom: "3.5rem" }}>
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <span className="badge badge-gold" style={{ marginBottom: "0.5rem" }}>
            💨 प्रदूषण निवारण • Pollution Prevented
          </span>
          <h2 style={{ fontSize: "2rem", color: "var(--primary-950)" }}>
            Environmental Impact of NOT Burning on {areaAcres} Acres
          </h2>
        </div>

        <div className="grid-4" style={{ gap: "1.25rem" }}>
          {/* CO2 Saved */}
          <div className="eco-card" style={{
            background: "linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%)",
            border: "2px solid var(--primary-300)",
            textAlign: "center",
            padding: "1.75rem 1rem"
          }}>
            <div style={{
              width: "3rem",
              height: "3rem",
              borderRadius: "50%",
              background: "var(--primary-100)",
              color: "var(--primary-700)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 0.75rem"
            }}>
              <Wind size={24} />
            </div>
            <div style={{ fontSize: "2.2rem", fontWeight: 800, color: "var(--primary-900)", lineHeight: 1.1 }}>
              {(pollution.co2_kg / 1000).toFixed(1)} Tons
            </div>
            <div style={{ fontSize: "0.85rem", color: "var(--primary-700)", fontWeight: 700, marginTop: "0.25rem" }}>
              CO₂ Emissions Saved
            </div>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
              Prevents {pollution.co2_kg.toLocaleString()} kg of greenhouse gases from heating the atmosphere.
            </p>
          </div>

          {/* PM2.5 Dust Saved */}
          <div className="eco-card" style={{
            background: "linear-gradient(135deg, #fef9c3 0%, #ffffff 100%)",
            border: "2px solid var(--earth-300)",
            textAlign: "center",
            padding: "1.75rem 1rem"
          }}>
            <div style={{
              width: "3rem",
              height: "3rem",
              borderRadius: "50%",
              background: "var(--gold-100)",
              color: "var(--earth-700)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 0.75rem"
            }}>
              <ShieldCheck size={24} />
            </div>
            <div style={{ fontSize: "2.2rem", fontWeight: 800, color: "var(--earth-900)", lineHeight: 1.1 }}>
              {pollution.pm25_kg} kg
            </div>
            <div style={{ fontSize: "0.85rem", color: "var(--earth-700)", fontWeight: 700, marginTop: "0.25rem" }}>
              PM2.5 Smog Dust Prevented
            </div>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
              Saves children & seniors in neighboring villages from severe asthma and bronchitis.
            </p>
          </div>

          {/* Tree Equivalent */}
          <div className="eco-card" style={{
            background: "linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%)",
            border: "2px solid #86efac",
            textAlign: "center",
            padding: "1.75rem 1rem"
          }}>
            <div style={{
              width: "3rem",
              height: "3rem",
              borderRadius: "50%",
              background: "var(--primary-100)",
              color: "var(--primary-800)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 0.75rem"
            }}>
              <TreePine size={24} />
            </div>
            <div style={{ fontSize: "2.2rem", fontWeight: 800, color: "var(--primary-900)", lineHeight: 1.1 }}>
              {pollution.equivalent_trees_needed.toLocaleString()}
            </div>
            <div style={{ fontSize: "0.85rem", color: "var(--primary-800)", fontWeight: 700, marginTop: "0.25rem" }}>
              Trees Absorption Eqv.
            </div>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
              Equals the carbon absorption of an entire grove of growing mature trees for a year!
            </p>
          </div>

          {/* Soil Microbial Health Saved */}
          <div className="eco-card" style={{
            background: "linear-gradient(135deg, #eff6ff 0%, #ffffff 100%)",
            border: "2px solid #bfdbfe",
            textAlign: "center",
            padding: "1.75rem 1rem"
          }}>
            <div style={{
              width: "3rem",
              height: "3rem",
              borderRadius: "50%",
              background: "#dbeafe",
              color: "#1d4ed8",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 0.75rem"
            }}>
              <Leaf size={24} />
            </div>
            <div style={{ fontSize: "2.2rem", fontWeight: 800, color: "#1e3a8a", lineHeight: 1.1 }}>
              100%
            </div>
            <div style={{ fontSize: "0.85rem", color: "#1d4ed8", fontWeight: 700, marginTop: "0.25rem" }}>
              Soil Microbes Protected
            </div>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
              Prevents the 400°C inferno from burning earthworms, nitrogen bacteria, and organic carbon.
            </p>
          </div>
        </div>
      </div>

      {/* ── Eco-Friendly Alternatives: Turning Waste into Wealth ── */}
      <div style={{ marginBottom: "4rem" }}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <span className="badge badge-green" style={{ marginBottom: "0.5rem" }}>
            ♻️ विकल्प • Profitable Alternatives
          </span>
          <h2 style={{ fontSize: "2rem", color: "var(--primary-950)" }}>
            5 Smart Alternatives to Stubble Burning
          </h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Turn crop leftovers into soil fertility, animal nutrition, or direct cash earnings.
          </p>
        </div>

        <div className="grid-2" style={{ gap: "1.5rem" }}>
          {alternatives.map((alt, idx) => {
            const isSelected = chosenAlternative === alt.method;
            return (
              <div
                key={idx}
                className="eco-card"
                style={{
                  border: isSelected ? "2px solid var(--primary-600)" : "1px solid var(--border-light)",
                  background: isSelected ? "#f9fefb" : "#ffffff",
                  display: "flex",
                  flexDirection: "column",
                  position: "relative"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.75rem" }}>
                  <h3 style={{ fontSize: "1.25rem", color: "var(--primary-950)" }}>
                    {idx + 1}. {alt.method}
                  </h3>
                  <span className={`badge ${alt.difficulty === 'easy' ? 'badge-green' : 'badge-gold'}`}>
                    {alt.difficulty?.toUpperCase()}
                  </span>
                </div>

                <p style={{ color: "var(--text-body)", fontSize: "0.92rem", lineHeight: 1.5, marginBottom: "1rem" }}>
                  {alt.description}
                </p>

                {/* Benefits */}
                <div style={{ marginBottom: "1rem" }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--primary-800)", marginBottom: "0.35rem" }}>
                    Key Advantages:
                  </div>
                  <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                    {alt.benefits?.map((b, i) => (
                      <li key={i} style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.85rem", color: "var(--text-body)" }}>
                        <CheckCircle2 size={15} color="var(--primary-600)" />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Financial Economics */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "0.75rem",
                  background: "var(--surface-muted)",
                  padding: "0.75rem 1rem",
                  borderRadius: "var(--radius-md)",
                  fontSize: "0.85rem",
                  marginBottom: "1.25rem"
                }}>
                  <div>
                    <span style={{ color: "var(--text-muted)", display: "block" }}>Est. Cost:</span>
                    <strong style={{ color: "var(--text-main)" }}>{alt.estimated_cost}</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--primary-700)", display: "block" }}>Financial Return:</span>
                    <strong style={{ color: "var(--primary-800)" }}>{alt.estimated_revenue}</strong>
                  </div>
                </div>

                {/* Choice Radio Button */}
                <div style={{ marginTop: "auto", borderTop: "1px solid var(--border-light)", paddingTop: "0.85rem" }}>
                  <button
                    type="button"
                    onClick={() => setChosenAlternative(alt.method)}
                    className={`btn ${isSelected ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                    style={{ width: "100%" }}
                  >
                    {isSelected ? "✓ Selected for Eco Pledge" : "Select this Method for Pledge"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Government Subsidies Info Card ── */}
      <div className="glass-panel" style={{
        padding: "2rem",
        marginBottom: "3.5rem",
        background: "linear-gradient(135deg, rgba(234, 179, 8, 0.1) 0%, rgba(34, 197, 94, 0.1) 100%)",
        border: "1.5px solid rgba(234, 179, 8, 0.3)"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
          <Award size={22} color="var(--earth-700)" />
          <h3 style={{ fontSize: "1.3rem", color: "var(--earth-900)" }}>
            Government Subsidies for Stubble Management (CRM Scheme)
          </h3>
        </div>
        <p style={{ color: "var(--text-body)", fontSize: "0.95rem", lineHeight: 1.6, marginBottom: "1rem" }}>
          Under the Central Sector Scheme on Crop Residue Management (CRM) in Punjab, Haryana, UP, and Rajasthan:
        </p>
        <div className="grid-3" style={{ gap: "1rem", fontSize: "0.9rem" }}>
          <div style={{ background: "#ffffff", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-light)" }}>
            <strong style={{ color: "var(--primary-800)", display: "block", marginBottom: "0.25rem" }}>
              50% Individual Subsidy:
            </strong>
            Provided to individual farmers purchasing Happy Seeder, Super Straw Management System (SMS), Mulcher, or Paddy Straw Chopper.
          </div>
          <div style={{ background: "#ffffff", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-light)" }}>
            <strong style={{ color: "var(--earth-700)", display: "block", marginBottom: "0.25rem" }}>
              80% CHC Subsidy:
            </strong>
            Cooperative societies, FPOs, and Panchayats establishing Custom Hiring Centers (CHCs) get up to 80% financial assistance.
          </div>
          <div style={{ background: "#ffffff", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-light)" }}>
            <strong style={{ color: "var(--sky-700)", display: "block", marginBottom: "0.25rem" }}>
              Free Pusa Decomposer:
            </strong>
            Bio-decomposer solutions are being sprayed for free by multiple state governments across hundreds of thousands of hectares.
          </div>
        </div>
      </div>

      {/* ── Take the No-Burn Eco Pledge ── */}
      <div style={{ textAlign: "center", marginBottom: "4rem" }}>
        <div className="glass-panel" style={{
          padding: "2.5rem",
          maxWidth: "760px",
          margin: "0 auto",
          background: "linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(240, 253, 244, 0.9) 100%)",
          border: "2px solid var(--primary-400)",
          boxShadow: "var(--shadow-glow)"
        }}>
          <span className="badge badge-gold" style={{ marginBottom: "0.75rem" }}>
            🤝 स्वच्छ हवा प्रतिज्ञा • Clean Air Pledge
          </span>
          <h2 style={{ fontSize: "2rem", color: "var(--primary-950)", marginBottom: "0.75rem" }}>
            Take the &quot;No Stubble Burning&quot; Farmer Pledge
          </h2>
          <p style={{ color: "var(--text-body)", fontSize: "0.98rem", marginBottom: "1.5rem" }}>
            Commit to adopting <strong>{chosenAlternative}</strong> on your {areaAcres} acres of land.
            Help us protect our air, preserve precious soil nutrients, and generate an official Eco-Warrior Certificate!
          </p>

          <button
            onClick={handleTakePledge}
            disabled={pledging}
            id="btn-take-eco-pledge"
            className="btn btn-primary btn-lg"
            style={{ fontSize: "1.1rem", padding: "0.9rem 2.2rem" }}
          >
            <Heart size={20} color="#fca5a5" fill="#fca5a5" />
            <span>{pledging ? "Generating Certificate..." : "I Pledge Not to Burn Stubble 🌱"}</span>
          </button>
        </div>
      </div>

      {/* ── Generated Official Eco Certificate ── */}
      {pledgeCertificate && (
        <div ref={certificateRef} style={{ maxWidth: "800px", margin: "0 auto 4rem" }}>
          <div style={{
            background: "#ffffff",
            border: "8px double #15803d",
            borderRadius: "var(--radius-lg)",
            padding: "3rem 2.5rem",
            boxShadow: "var(--shadow-lg)",
            textAlign: "center",
            position: "relative"
          }}>
            {/* Header Stamp */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
              <div style={{ textAlign: "left" }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 700 }}>
                  CERTIFICATE ID: {pledgeCertificate.certificate_id?.slice(0, 8).toUpperCase() || "KS-2026-ECO"}
                </span>
                <div style={{ fontSize: "0.75rem", color: "var(--primary-700)" }}>
                  Verified by Kissan Sarthi AI Mission
                </div>
              </div>
              <div style={{
                width: "3.5rem",
                height: "3.5rem",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #15803d 0%, #16a34a 100%)",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 800,
                fontSize: "1.5rem",
                boxShadow: "0 4px 10px rgba(22, 163, 74, 0.4)"
              }}>
                🌱
              </div>
            </div>

            <span className="badge badge-gold" style={{ fontSize: "0.85rem", padding: "0.3rem 1rem", marginBottom: "1rem" }}>
              🏆 किसान गौरव प्रमाण पत्र • ECO-WARRIOR FARMER CERTIFICATE
            </span>

            <h2 style={{
              fontFamily: "var(--font-heading)",
              fontSize: "2.2rem",
              color: "var(--primary-950)",
              marginTop: "0.5rem",
              marginBottom: "0.5rem"
            }}>
              Certificate of Environmental Stewardship
            </h2>

            <p style={{ fontSize: "1rem", color: "var(--text-muted)", marginBottom: "1.75rem" }}>
              This honor is proudly awarded to:
            </p>

            <div style={{
              fontSize: "2rem",
              fontWeight: 800,
              color: "var(--primary-900)",
              borderBottom: "2px solid var(--primary-300)",
              display: "inline-block",
              paddingBottom: "0.25rem",
              marginBottom: "1.5rem"
            }}>
              {pledgeCertificate.farmer_name || "Progressive Annadata"}
            </div>

            <p style={{
              fontSize: "1.05rem",
              color: "var(--text-body)",
              maxWidth: "640px",
              margin: "0 auto 2rem",
              lineHeight: 1.7
            }}>
              for exemplifying true leadership and taking a solemn pledge to protect the air and soil of India by adopting{" "}
              <strong style={{ color: "var(--primary-800)" }}>{pledgeCertificate.farmer_choice || chosenAlternative}</strong> on{" "}
              <strong>{pledgeCertificate.stubble_area_acres || areaAcres} Acres</strong> of farmland at{" "}
              <strong>{pledgeCertificate.farm_name || "Green Valley Farm"}</strong>.
            </p>

            {/* Impact Metric Chips */}
            <div style={{
              display: "flex",
              justifyContent: "center",
              flexWrap: "wrap",
              gap: "1.5rem",
              marginBottom: "2.5rem",
              background: "var(--primary-50)",
              padding: "1.25rem",
              borderRadius: "var(--radius-md)",
              border: "1px dashed var(--primary-300)"
            }}>
              <div>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block" }}>CO₂ Saved</span>
                <strong style={{ fontSize: "1.3rem", color: "var(--primary-800)" }}>
                  {pledgeCertificate.co2_saved_kg?.toLocaleString()} kg
                </strong>
              </div>
              <div>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block" }}>PM2.5 Smog Prevented</span>
                <strong style={{ fontSize: "1.3rem", color: "var(--earth-800)" }}>
                  {pledgeCertificate.pm25_saved_kg} kg
                </strong>
              </div>
              <div>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block" }}>Equivalent Trees</span>
                <strong style={{ fontSize: "1.3rem", color: "var(--gold-600)" }}>
                  {pledgeCertificate.equivalent_trees || Math.round((pledgeCertificate.co2_saved_kg || 2000) / 22)}
                </strong>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", borderTop: "1px solid var(--border-light)", paddingTop: "1.5rem" }}>
              <div style={{ textAlign: "left", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                <div>Date: {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}</div>
                <div>Status: Certified Fire-Free Field</div>
              </div>

              <button
                onClick={handlePrintCertificate}
                id="btn-print-certificate"
                className="btn btn-secondary btn-sm"
              >
                <Printer size={16} />
                <span>Print Certificate</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function StubblePage() {
  return (
    <Suspense fallback={<div className="container" style={{ padding: "4rem 0" }}>Loading Stubble Center...</div>}>
      <StubbleContent />
    </Suspense>
  );
}

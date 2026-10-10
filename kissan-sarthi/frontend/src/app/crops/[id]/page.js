"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Wheat, 
  ArrowLeft, 
  MapPin, 
  Calendar, 
  Sparkles, 
  Clock, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle2, 
  Leaf, 
  Droplets, 
  Stethoscope, 
  Recycle, 
  RefreshCw, 
  ShieldCheck, 
  Sun,
  Layers,
  Sprout
} from "lucide-react";
import { api } from "@/lib/api";

export default function CropDetailPage({ params }) {
  const resolvedParams = use(params);
  const cropId = resolvedParams.id;
  const router = useRouter();

  const [crop, setCrop] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  const fetchCropData = async () => {
    try {
      setLoading(true);
      const cropData = await api.getCrop(cropId);
      setCrop(cropData);

      // Check if analysis is already cached
      if (cropData.analysis_result) {
        try {
          const parsed = JSON.parse(cropData.analysis_result);
          setAnalysis(parsed);
        } catch {
          // parse error
        }
      } else {
        // Automatically trigger analysis if not yet run
        triggerAnalysis();
      }
    } catch (err) {
      setError(err.message || "Failed to load crop details");
    } finally {
      setLoading(false);
    }
  };

  const triggerAnalysis = async () => {
    try {
      setAnalyzing(true);
      const res = await api.analyzeCrop(cropId);
      if (res && res.analysis) {
        setAnalysis(res.analysis);
      }
    } catch (err) {
      console.error("AI Analysis error:", err);
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    fetchCropData();
  }, [cropId]);

  if (loading) {
    return (
      <div className="container" style={{ padding: "5rem 0", textAlign: "center" }}>
        <p style={{ color: "var(--text-muted)" }}>Loading crop details and AI analysis...</p>
      </div>
    );
  }

  if (error || !crop) {
    return (
      <div className="container" style={{ padding: "4rem 0" }}>
        <div style={{
          background: "var(--danger-50)",
          border: "1px solid var(--danger-100)",
          padding: "1.5rem",
          borderRadius: "var(--radius-md)",
          color: "var(--danger-700)"
        }}>
          <h3>Crop Not Found</h3>
          <p>{error || "Unable to load crop record."}</p>
          <Link href="/crops" className="btn btn-secondary" style={{ marginTop: "1rem" }}>
            Return to Crops
          </Link>
        </div>
      </div>
    );
  }

  // Calculate approximate days to harvest
  let daysToHarvest = null;
  if (analysis?.estimated_harvest_date) {
    const harvestDate = new Date(analysis.estimated_harvest_date);
    const today = new Date();
    const diffTime = harvestDate - today;
    daysToHarvest = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  }

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "5rem" }}>
      {/* Back button */}
      <div style={{ marginBottom: "1.5rem" }}>
        <Link href="/crops" style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.4rem",
          color: "var(--text-muted)",
          fontSize: "0.9rem",
          fontWeight: 600
        }}>
          <ArrowLeft size={16} />
          <span>Back to All Crops</span>
        </Link>
      </div>

      {/* ── Crop Header Banner ── */}
      <div className="glass-panel" style={{
        padding: "2rem 2.5rem",
        marginBottom: "2rem",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1.5rem"
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.5rem" }}>
            <span className="badge badge-gold">
              <Wheat size={14} /> {crop.crop_type} Season
            </span>
            <span className="badge badge-green">
              {crop.current_stage || "Active Growth"}
            </span>
          </div>

          <h1 style={{ fontSize: "2.2rem", color: "var(--primary-950)", marginBottom: "0.25rem" }}>
            {crop.crop_name} {crop.variety && `(${crop.variety})`}
          </h1>

          <div style={{ display: "flex", flexWrap: "wrap", gap: "1.25rem", color: "var(--text-muted)", fontSize: "0.9rem", marginTop: "0.5rem" }}>
            <div>
              Area Sown: <strong style={{ color: "var(--text-main)" }}>{crop.area_acres} Acres</strong>
            </div>
            {crop.sowing_date && (
              <div>
                Sowing Date: <strong style={{ color: "var(--text-main)" }}>{crop.sowing_date}</strong>
              </div>
            )}
            <div>
              Status: <span style={{ textTransform: "capitalize", fontWeight: 600, color: "var(--primary-700)" }}>{crop.status}</span>
            </div>
          </div>
        </div>

        {/* Quick Cross-Module Action Buttons */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          <button
            onClick={triggerAnalysis}
            disabled={analyzing}
            className="btn btn-secondary btn-sm"
            id="btn-refresh-analysis"
          >
            <RefreshCw size={14} className={analyzing ? "spin" : ""} />
            <span>{analyzing ? "Analyzing..." : "Re-run AI Analysis"}</span>
          </button>

          <Link
            href={`/health?crop_id=${crop.id}`}
            id="btn-crop-doctor-link"
            className="btn btn-primary btn-sm"
          >
            <Stethoscope size={16} />
            <span>Check Crop Health (Photo)</span>
          </Link>

          <Link
            href={`/stubble?crop_id=${crop.id}&area=${crop.area_acres}`}
            id="btn-crop-stubble-link"
            className="btn btn-accent btn-sm"
          >
            <Recycle size={16} />
            <span>Stubble Savings</span>
          </Link>
        </div>
      </div>

      {analyzing && !analysis && (
        <div className="glass-panel" style={{ textAlign: "center", padding: "4rem 2rem", marginBottom: "2rem" }}>
          <div style={{
            display: "inline-block",
            width: "3rem",
            height: "3rem",
            border: "3px solid var(--primary-200)",
            borderTopColor: "var(--primary-600)",
            borderRadius: "50%",
            animation: "spin 1s linear infinite"
          }} />
          <h3 style={{ fontSize: "1.3rem", color: "var(--primary-900)", marginTop: "1.25rem" }}>
            AI Agricultural Advisor is analyzing your crop...
          </h3>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Calculating approx harvest date, care calendar, fertilizer schedule, and pest alerts based on soil and climate.
          </p>
        </div>
      )}

      {analysis && (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          {/* ── Key Highlights Row (Harvest Time + Expected Yield) ── */}
          <div className="grid-3">
            {/* Approx Harvest Time Card */}
            <div className="eco-card" style={{
              background: "linear-gradient(135deg, #fefce8 0%, #ffffff 100%)",
              border: "1.5px solid #fef08a"
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--earth-700)", marginBottom: "0.5rem" }}>
                <Clock size={20} />
                <span style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase" }}>
                  Approx Harvest Time
                </span>
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--earth-900)", lineHeight: 1.2 }}>
                {analysis.estimated_harvest_date || crop.expected_harvest_date || "110-130 Days"}
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--earth-700)", marginTop: "0.4rem", fontWeight: 600 }}>
                {daysToHarvest !== null && daysToHarvest > 0
                  ? `⏳ Approx. ${daysToHarvest} days remaining until harvest`
                  : daysToHarvest !== null && daysToHarvest <= 0
                  ? "🌾 Harvest Window Active!"
                  : "Estimated based on sowing date & season"}
              </div>
            </div>

            {/* Estimated Yield */}
            <div className="eco-card" style={{
              background: "linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%)",
              border: "1.5px solid var(--primary-200)"
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--primary-700)", marginBottom: "0.5rem" }}>
                <TrendingUp size={20} />
                <span style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase" }}>
                  Estimated Yield
                </span>
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--primary-900)", lineHeight: 1.2 }}>
                {analysis.estimated_yield_per_acre || "18-24 Quintals/Acre"}
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--primary-700)", marginTop: "0.4rem" }}>
                Total expected: <strong>{((parseFloat(analysis.estimated_yield_per_acre) || 20) * (crop.area_acres || 1)).toFixed(0)} Quintals</strong>
              </div>
            </div>

            {/* Growth Stage Assessment */}
            <div className="eco-card" style={{
              background: "linear-gradient(135deg, #f0f9ff 0%, #ffffff 100%)",
              border: "1.5px solid #bae6fd"
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--sky-700)", marginBottom: "0.5rem" }}>
                <Sprout size={20} />
                <span style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase" }}>
                  Current Growth Health
                </span>
              </div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--sky-900)", lineHeight: 1.3, marginBottom: "0.3rem" }}>
                {analysis.growth_stage_assessment?.slice(0, 75) || "Active Healthy Vegetative Phase"}...
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--sky-700)" }}>
                Stage: <strong>{crop.current_stage}</strong>
              </div>
            </div>
          </div>

          {/* ── Health Overview ── */}
          {analysis.crop_health_overview && (
            <div className="glass-panel" style={{ padding: "1.75rem 2rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                <Sparkles size={18} color="var(--primary-600)" />
                <h3 style={{ fontSize: "1.25rem", color: "var(--primary-950)" }}>
                  Krishi AI Overview & Assessment
                </h3>
              </div>
              <p style={{ color: "var(--text-body)", fontSize: "0.98rem", lineHeight: 1.6 }}>
                {analysis.crop_health_overview}
              </p>
              {analysis.growth_stage_assessment && (
                <div style={{
                  marginTop: "1rem",
                  background: "var(--primary-50)",
                  padding: "0.85rem 1rem",
                  borderRadius: "var(--radius-md)",
                  fontSize: "0.9rem",
                  color: "var(--primary-900)"
                }}>
                  <strong>Growth Stage Action:</strong> {analysis.growth_stage_assessment}
                </div>
              )}
            </div>
          )}

          {/* ── Things to be Taken Care Of (Care Instructions) ── */}
          {analysis.care_instructions && analysis.care_instructions.length > 0 && (
            <div className="eco-card">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.25rem" }}>
                <CheckCircle2 size={20} color="var(--primary-600)" />
                <h3 style={{ fontSize: "1.35rem", color: "var(--primary-950)" }}>
                  Things to be Taken Care Of (Stage-wise Care Checklist)
                </h3>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {analysis.care_instructions.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "1rem",
                      background: "var(--surface-muted)",
                      padding: "1rem 1.25rem",
                      borderRadius: "var(--radius-md)",
                      borderLeft: "4px solid var(--primary-600)"
                    }}
                  >
                    <div style={{
                      width: "1.75rem",
                      height: "1.75rem",
                      borderRadius: "50%",
                      background: "var(--primary-100)",
                      color: "var(--primary-800)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 700,
                      fontSize: "0.85rem",
                      flexShrink: 0
                    }}>
                      {idx + 1}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "0.5rem", marginBottom: "0.25rem" }}>
                        <h4 style={{ fontSize: "1.05rem", color: "var(--primary-950)" }}>
                          {item.task}
                        </h4>
                        <span className="badge badge-green" style={{ fontSize: "0.75rem" }}>
                          {item.timing || item.stage}
                        </span>
                      </div>
                      <p style={{ fontSize: "0.9rem", color: "var(--text-body)", lineHeight: 1.5 }}>
                        {item.details}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Weekly Fertilizer & Nutrient Schedule ── */}
          {analysis.fertilizer_schedule && analysis.fertilizer_schedule.length > 0 && (
            <div className="eco-card">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.25rem" }}>
                <Droplets size={20} color="var(--earth-700)" />
                <h3 style={{ fontSize: "1.35rem", color: "var(--primary-950)" }}>
                  Week-by-Week Fertilizer & Nutrition Schedule
                </h3>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "0.9rem",
                  textAlign: "left"
                }}>
                  <thead>
                    <tr style={{ background: "var(--earth-100)", borderBottom: "2px solid var(--earth-300)" }}>
                      <th style={{ padding: "0.75rem 1rem", color: "var(--earth-900)" }}>Week</th>
                      <th style={{ padding: "0.75rem 1rem", color: "var(--earth-900)" }}>Fertilizer / Nutrient</th>
                      <th style={{ padding: "0.75rem 1rem", color: "var(--earth-900)" }}>Quantity per Acre</th>
                      <th style={{ padding: "0.75rem 1rem", color: "var(--earth-900)" }}>Application Method</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.fertilizer_schedule.map((row, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid var(--border-light)",
                          background: idx % 2 === 0 ? "#ffffff" : "var(--surface-muted)"
                        }}
                      >
                        <td style={{ padding: "0.75rem 1rem", fontWeight: 700, color: "var(--primary-800)" }}>
                          Week {row.week}
                        </td>
                        <td style={{ padding: "0.75rem 1rem", fontWeight: 600 }}>
                          {row.fertilizer}
                        </td>
                        <td style={{ padding: "0.75rem 1rem" }}>
                          {row.quantity_per_acre}
                        </td>
                        <td style={{ padding: "0.75rem 1rem", color: "var(--text-muted)" }}>
                          {row.method}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Pest & Disease Risk Alerts ── */}
          {analysis.pest_risk_alerts && analysis.pest_risk_alerts.length > 0 && (
            <div className="eco-card" style={{ borderLeft: "4px solid var(--danger-500)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.25rem" }}>
                <AlertTriangle size={20} color="var(--danger-500)" />
                <h3 style={{ fontSize: "1.35rem", color: "var(--primary-950)" }}>
                  Pest & Disease Risk Alerts
                </h3>
              </div>
              <div className="grid-2">
                {analysis.pest_risk_alerts.map((pest, idx) => {
                  const isHigh = pest.risk_level?.toLowerCase() === "high";
                  return (
                    <div
                      key={idx}
                      style={{
                        background: isHigh ? "var(--danger-50)" : "var(--surface-muted)",
                        border: `1px solid ${isHigh ? "var(--danger-100)" : "var(--border-light)"}`,
                        borderRadius: "var(--radius-md)",
                        padding: "1rem"
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                        <h4 style={{ fontSize: "1.05rem", color: "var(--primary-950)" }}>
                          {pest.pest}
                        </h4>
                        <span className={`badge ${isHigh ? 'badge-danger' : 'badge-gold'}`}>
                          Risk: {pest.risk_level}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-body)", marginBottom: "0.4rem" }}>
                        <strong>Prevention:</strong> {pest.prevention}
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                        <strong>Treatment:</strong> {pest.treatment}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Organic Alternatives & Weather ── */}
          <div className="grid-2">
            {analysis.organic_alternatives && (
              <div className="eco-card">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <Leaf size={18} color="var(--primary-600)" />
                  <h4 style={{ fontSize: "1.15rem", color: "var(--primary-950)" }}>
                    Eco & Organic Alternatives
                  </h4>
                </div>
                <p style={{ fontSize: "0.9rem", color: "var(--text-body)", lineHeight: 1.5 }}>
                  {analysis.organic_alternatives}
                </p>
              </div>
            )}

            {analysis.weather_considerations && (
              <div className="eco-card">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <Sun size={18} color="var(--earth-500)" />
                  <h4 style={{ fontSize: "1.15rem", color: "var(--primary-950)" }}>
                    Weather & Regional Guidance
                  </h4>
                </div>
                <p style={{ fontSize: "0.9rem", color: "var(--text-body)", lineHeight: 1.5 }}>
                  {analysis.weather_considerations}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

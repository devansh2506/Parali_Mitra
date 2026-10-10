"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { 
  Stethoscope, 
  UploadCloud, 
  Camera, 
  AlertTriangle, 
  CheckCircle2, 
  Leaf, 
  ShieldCheck, 
  PhoneCall, 
  ArrowLeft, 
  RefreshCw, 
  Clock, 
  Info,
  Sparkles
} from "lucide-react";
import { api } from "@/lib/api";

const COMMON_SYMPTOMS = [
  "Yellowing of leaves (पत्तियों का पीलापन)",
  "Brown / Black spots (भूरे या काले धब्बे)",
  "Wilting / Drooping plant (मुरझाना)",
  "White powdery residue (सफेद फफूंद)",
  "Holes / insect chewing (कीड़ों द्वारा कटी पत्तियां)",
  "Curling or deformed leaves (पत्तियों का मुड़ना)",
  "Stem borer / Rotting at base (तने का सड़ना)",
  "Stunted plant growth (पौधे का रुक जाना)",
];

function HealthDoctorContent() {
  const searchParams = useSearchParams();
  const preselectedCropId = searchParams.get("crop_id") || "";

  const [crops, setCrops] = useState([]);
  const [selectedCropId, setSelectedCropId] = useState(preselectedCropId);
  const [selectedSymptoms, setSelectedSymptoms] = useState([]);
  const [customSymptomText, setCustomSymptomText] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosisResult, setDiagnosisResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  const fileInputRef = useRef(null);

  useEffect(() => {
    // Load crops for selector
    api.getCrops()
      .then((data) => {
        setCrops(data);
        if (!preselectedCropId && data.length > 0) {
          setSelectedCropId(data[0].id);
        }
      })
      .catch(() => {});
  }, [preselectedCropId]);

  useEffect(() => {
    // Load history when crop changes
    if (selectedCropId) {
      api.getHealthHistory(selectedCropId)
        .then((records) => setHistory(records || []))
        .catch(() => setHistory([]));
    }
  }, [selectedCropId]);

  const handleImageChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
      setError(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) {
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
      setError(null);
    }
  };

  const toggleSymptom = (sym) => {
    if (selectedSymptoms.includes(sym)) {
      setSelectedSymptoms(selectedSymptoms.filter((s) => s !== sym));
    } else {
      setSelectedSymptoms([...selectedSymptoms, sym]);
    }
  };

  const handleSubmitDiagnosis = async (e) => {
    e.preventDefault();
    setError(null);

    if (!selectedCropId) {
      setError("Please select a crop to diagnose.");
      return;
    }
    if (!imageFile) {
      setError("Please upload or capture a photo of the affected plant or leaves.");
      return;
    }

    try {
      setDiagnosing(true);
      const formData = new FormData();
      formData.append("crop_id", selectedCropId);
      formData.append("image", imageFile);

      const allSymptoms = [...selectedSymptoms];
      if (customSymptomText.trim()) {
        allSymptoms.push(customSymptomText.trim());
      }
      if (allSymptoms.length > 0) {
        formData.append("symptoms_reported", allSymptoms.join(", "));
      }

      const res = await api.checkHealth(formData);
      setDiagnosisResult(res);

      // Refresh history
      api.getHealthHistory(selectedCropId)
        .then((records) => setHistory(records || []))
        .catch(() => {});
    } catch (err) {
      setError(err.message || "Diagnosis failed. Please try again.");
    } finally {
      setDiagnosing(false);
    }
  };

  const activeDiagnosis = diagnosisResult?.diagnosis;

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "5rem" }}>
      {/* Header */}
      <div style={{ marginBottom: "2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span className="badge badge-blue">
            <Stethoscope size={14} /> चरण 3 • Step 3: AI Crop Doctor
          </span>
        </div>
        <h1 style={{ fontSize: "2.2rem", color: "var(--primary-950)", marginBottom: "0.4rem" }}>
          AI Plant Pathology & Crop Doctor
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
          Upload a clear photo of your affected plant leaf, stem, or fruit. Our AI detects diseases, pest attacks, and nutrient deficiencies with organic & safe treatments.
        </p>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: diagnosisResult ? "1fr 1.25fr" : "1fr",
        gap: "2rem",
        alignItems: "start"
      }}>
        {/* ── Left Column: Upload Form ── */}
        <div className="glass-panel" style={{ padding: "2rem" }}>
          <form onSubmit={handleSubmitDiagnosis}>
            {/* Crop Selector */}
            <div className="form-group" style={{ marginBottom: "1.5rem" }}>
              <label className="form-label" htmlFor="health-crop-select">
                Select Affected Crop *
              </label>
              {crops.length === 0 ? (
                <div style={{
                  background: "var(--primary-50)",
                  padding: "0.85rem",
                  borderRadius: "var(--radius-md)",
                  fontSize: "0.88rem"
                }}>
                  No crops found.{" "}
                  <Link href="/crops/new" style={{ color: "var(--primary-700)", fontWeight: 700 }}>
                    Please add a crop first.
                  </Link>
                </div>
              ) : (
                <select
                  id="health-crop-select"
                  value={selectedCropId}
                  onChange={(e) => setSelectedCropId(e.target.value)}
                  className="form-select"
                >
                  {crops.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.crop_name} {c.variety ? `(${c.variety})` : ""} — Stage: {c.current_stage}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Photo Upload Zone */}
            <div className="form-group" style={{ marginBottom: "1.5rem" }}>
              <label className="form-label">
                Upload Affected Crop Photo *
                <span className="form-hint">(Clear close-up of leaf or stem)</span>
              </label>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: "2px dashed var(--border-light)",
                  borderRadius: "var(--radius-md)",
                  padding: "2rem 1.5rem",
                  textAlign: "center",
                  cursor: "pointer",
                  background: imagePreview ? "#fafffb" : "#ffffff",
                  transition: "all 0.2s ease"
                }}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="image/*"
                  onChange={handleImageChange}
                  style={{ display: "none" }}
                  id="crop-photo-input"
                />

                {imagePreview ? (
                  <div>
                    <img
                      src={imagePreview}
                      alt="Crop Preview"
                      style={{
                        maxHeight: "220px",
                        maxWidth: "100%",
                        borderRadius: "var(--radius-md)",
                        objectFit: "contain",
                        margin: "0 auto 1rem",
                        boxShadow: "var(--shadow-sm)"
                      }}
                    />
                    <p style={{ fontSize: "0.85rem", color: "var(--primary-700)", fontWeight: 600 }}>
                      Click or drag to replace photo
                    </p>
                  </div>
                ) : (
                  <div>
                    <div style={{
                      width: "3.5rem",
                      height: "3.5rem",
                      borderRadius: "50%",
                      background: "var(--sky-100)",
                      color: "var(--sky-700)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 1rem"
                    }}>
                      <Camera size={28} />
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "1rem", color: "var(--primary-950)", marginBottom: "0.25rem" }}>
                      Click to upload or take photo
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      PNG, JPG, WebP supported (Max 10MB)
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Symptoms Checklist */}
            <div className="form-group" style={{ marginBottom: "1.5rem" }}>
              <label className="form-label" style={{ marginBottom: "0.5rem" }}>
                Observed Symptoms (Select any that apply)
              </label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem" }}>
                {COMMON_SYMPTOMS.map((sym) => {
                  const active = selectedSymptoms.includes(sym);
                  return (
                    <button
                      type="button"
                      key={sym}
                      onClick={() => toggleSymptom(sym)}
                      style={{
                        padding: "0.4rem 0.75rem",
                        borderRadius: "var(--radius-full)",
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        border: active ? "1.5px solid var(--primary-600)" : "1px solid var(--border-light)",
                        background: active ? "var(--primary-100)" : "#ffffff",
                        color: active ? "var(--primary-900)" : "var(--text-body)",
                        cursor: "pointer",
                        transition: "all 0.15s ease"
                      }}
                    >
                      {active ? "✓ " : "+ "}
                      {sym}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Additional Text */}
            <div className="form-group" style={{ marginBottom: "2rem" }}>
              <label className="form-label" htmlFor="custom-symptom-text">
                Additional Observations
                <span className="form-hint">(When did it start, weather etc.)</span>
              </label>
              <input
                type="text"
                id="custom-symptom-text"
                placeholder="e.g. Started after 2 days of heavy rain, spreading rapidly..."
                value={customSymptomText}
                onChange={(e) => setCustomSymptomText(e.target.value)}
                className="form-input"
              />
            </div>

            {error && (
              <div style={{
                background: "var(--danger-50)",
                border: "1px solid var(--danger-100)",
                color: "var(--danger-700)",
                padding: "0.85rem",
                borderRadius: "var(--radius-md)",
                marginBottom: "1.5rem",
                fontSize: "0.88rem"
              }}>
                ⚠️ {error}
              </div>
            )}

            <button
              type="submit"
              id="btn-run-diagnosis"
              disabled={diagnosing || !imageFile}
              className="btn btn-primary btn-lg"
              style={{ width: "100%" }}
            >
              {diagnosing ? (
                <>
                  <RefreshCw size={18} className="spin" />
                  <span>Analyzing Photo with Plant Pathology AI...</span>
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  <span>Diagnose Crop Health Now</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* ── Right Column: AI Health Diagnosis Report ── */}
        {diagnosisResult && activeDiagnosis && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Diagnosis Main Banner */}
            <div className="eco-card" style={{
              borderLeft: `6px solid ${
                diagnosisResult.severity === "critical"
                  ? "var(--danger-500)"
                  : diagnosisResult.severity === "high"
                  ? "var(--earth-500)"
                  : "var(--primary-500)"
              }`
            }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                <div>
                  <span className={`badge ${
                    diagnosisResult.severity === 'critical' ? 'badge-danger' : 'badge-gold'
                  }`} style={{ marginBottom: "0.35rem" }}>
                    Severity: {diagnosisResult.severity?.toUpperCase()}
                  </span>
                  <h2 style={{ fontSize: "1.6rem", color: "var(--primary-950)" }}>
                    {activeDiagnosis.disease_or_pest_name || activeDiagnosis.identified_issue}
                  </h2>
                  {activeDiagnosis.scientific_name && (
                    <div style={{ fontStyle: "italic", color: "var(--text-muted)", fontSize: "0.88rem" }}>
                      Scientific: {activeDiagnosis.scientific_name}
                    </div>
                  )}
                </div>

                {activeDiagnosis.confidence && (
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--primary-800)" }}>
                      {(activeDiagnosis.confidence * 100).toFixed(0)}%
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Confidence</div>
                  </div>
                )}
              </div>

              {activeDiagnosis.identified_issue && (
                <p style={{ color: "var(--text-body)", fontSize: "0.95rem", lineHeight: 1.5, marginBottom: "1rem" }}>
                  {activeDiagnosis.identified_issue}
                </p>
              )}

              {/* Immediate Emergency Action */}
              {activeDiagnosis.immediate_actions && activeDiagnosis.immediate_actions.length > 0 && (
                <div style={{
                  background: "var(--danger-50)",
                  border: "1px solid var(--danger-100)",
                  borderRadius: "var(--radius-md)",
                  padding: "0.85rem 1rem",
                  marginBottom: "1rem"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--danger-700)", fontWeight: 700, fontSize: "0.9rem", marginBottom: "0.35rem" }}>
                    <AlertTriangle size={16} /> Immediate Action Required:
                  </div>
                  <ul style={{ listStyle: "disc", paddingLeft: "1.25rem", fontSize: "0.88rem", color: "var(--danger-700)" }}>
                    {activeDiagnosis.immediate_actions.map((act, i) => (
                      <li key={i}>{act}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Comprehensive Treatment Plan */}
            <div className="glass-panel" style={{ padding: "1.75rem" }}>
              <h3 style={{ fontSize: "1.3rem", color: "var(--primary-950)", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Leaf size={18} color="var(--primary-600)" />
                Comprehensive Treatment Plan
              </h3>

              {/* Organic Solutions */}
              {activeDiagnosis.treatment_plan?.organic && (
                <div style={{
                  background: "#f0fdf4",
                  border: "1px solid var(--primary-200)",
                  borderRadius: "var(--radius-md)",
                  padding: "1rem",
                  marginBottom: "1rem"
                }}>
                  <h4 style={{ fontSize: "0.95rem", color: "var(--primary-900)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    🌿 Organic & Bio Solutions (Safe for Soil & Bees)
                  </h4>
                  <ul style={{ listStyle: "disc", paddingLeft: "1.25rem", fontSize: "0.88rem", color: "var(--primary-800)" }}>
                    {activeDiagnosis.treatment_plan.organic.map((org, i) => (
                      <li key={i}>{org}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Chemical Treatment with exact dosage */}
              {activeDiagnosis.treatment_plan?.chemical && (
                <div style={{
                  background: "#fffbeb",
                  border: "1px solid var(--earth-300)",
                  borderRadius: "var(--radius-md)",
                  padding: "1rem",
                  marginBottom: "1rem"
                }}>
                  <h4 style={{ fontSize: "0.95rem", color: "var(--earth-900)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    🧪 Targeted Chemical Treatment (Follow safety rules)
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                    {activeDiagnosis.treatment_plan.chemical.map((chem, i) => (
                      <div key={i} style={{ fontSize: "0.88rem", color: "var(--earth-900)" }}>
                        • <strong>{chem.product || chem}</strong>: {chem.dosage ? `Dosage: ${chem.dosage}` : ""} {chem.frequency ? `(${chem.frequency})` : ""}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Cultural / Agronomic Tips */}
              {activeDiagnosis.treatment_plan?.cultural && (
                <div style={{
                  background: "var(--surface-muted)",
                  borderRadius: "var(--radius-md)",
                  padding: "1rem",
                  fontSize: "0.88rem",
                  color: "var(--text-body)"
                }}>
                  <strong>🚜 Field & Irrigation Hygiene:</strong>
                  <ul style={{ listStyle: "disc", paddingLeft: "1.25rem", marginTop: "0.3rem" }}>
                    {activeDiagnosis.treatment_plan.cultural.map((cult, i) => (
                      <li key={i}>{cult}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Helpline CTA Card */}
            <div style={{
              background: "linear-gradient(135deg, #166534 0%, #15803d 100%)",
              color: "#ffffff",
              padding: "1.25rem 1.5rem",
              borderRadius: "var(--radius-md)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "1rem"
            }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>Need Expert Government Agronomist Consultation?</div>
                <div style={{ fontSize: "0.82rem", color: "#bbf7d0" }}>Kisan Call Center toll-free helpline is available 6 AM to 10 PM.</div>
              </div>
              <a href="tel:18001801551" className="btn btn-accent btn-sm">
                <PhoneCall size={14} />
                <span>Call 1800-180-1551</span>
              </a>
            </div>
          </div>
        )}
      </div>

      {/* Past Diagnosis Records for Crop */}
      {history.length > 0 && (
        <div style={{ marginTop: "4rem" }}>
          <h3 style={{ fontSize: "1.4rem", color: "var(--primary-950)", marginBottom: "1.25rem" }}>
            Past Health Diagnosis History for this Crop ({history.length})
          </h3>
          <div className="grid-3">
            {history.map((record) => {
              const diag = typeof record.diagnosis === "string" ? JSON.parse(record.diagnosis || "{}") : record.diagnosis || {};
              return (
                <div key={record.id} className="eco-card" style={{ fontSize: "0.88rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                    <span className="badge badge-gold">{record.severity}</span>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      {record.created_at?.slice(0, 10)}
                    </span>
                  </div>
                  <h4 style={{ fontSize: "1.05rem", color: "var(--primary-950)", marginBottom: "0.25rem" }}>
                    {diag.disease_or_pest_name || "Crop Check"}
                  </h4>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>
                    Symptoms: {record.symptoms_reported || "Visual photo check"}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function HealthDoctorPage() {
  return (
    <Suspense fallback={<div className="container" style={{ padding: "4rem 0" }}>Loading Crop Doctor...</div>}>
      <HealthDoctorContent />
    </Suspense>
  );
}

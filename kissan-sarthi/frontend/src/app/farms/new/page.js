"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { 
  MapPin, 
  ArrowLeft, 
  Check, 
  Droplets, 
  Mountain, 
  Ruler, 
  HelpCircle, 
  Sparkles,
  Save
} from "lucide-react";
import { api } from "@/lib/api";

export default function NewFarmPage() {
  const router = useRouter();

  const [states, setStates] = useState([]);
  const [soilTypes, setSoilTypes] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Form State
  const [formData, setFormData] = useState({
    name: "",
    owner_name: "",
    location_state: "Punjab",
    location_district: "",
    location_village: "",
    latitude: "",
    longitude: "",
    total_area_acres: "",
    dimension_length_ft: "",
    dimension_width_ft: "",
    soil_type: "Alluvial Soil",
    irrigation_type: "Tube Well / Borewell",
    water_source: "Groundwater Borewell (Submersible)",
    additional_notes: "",
  });

  useEffect(() => {
    // Fetch state and soil reference data
    api.getStates()
      .then((res) => setStates(res.states || []))
      .catch(() => {});

    api.getSoilTypes()
      .then((res) => setSoilTypes(res.soil_types || []))
      .catch(() => {});
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSoilSelect = (soilName) => {
    setFormData((prev) => ({ ...prev, soil_type: soilName }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!formData.name.trim()) {
      setError("Please provide a name for your farm land.");
      return;
    }
    if (!formData.owner_name.trim()) {
      setError("Please enter the farmer's name.");
      return;
    }
    if (!formData.total_area_acres || Number(formData.total_area_acres) <= 0) {
      setError("Please enter a valid total area in acres.");
      return;
    }

    try {
      setSubmitting(true);

      // Build dimension note if dimensions provided
      let notes = formData.additional_notes || "";
      if (formData.dimension_length_ft && formData.dimension_width_ft) {
        notes = `Dimensions: ${formData.dimension_length_ft} ft × ${formData.dimension_width_ft} ft. ${notes}`.trim();
      }

      const payload = {
        name: formData.name.trim(),
        owner_name: formData.owner_name.trim(),
        location_state: formData.location_state,
        location_district: formData.location_district.trim() || undefined,
        location_village: formData.location_village.trim() || undefined,
        latitude: formData.latitude ? parseFloat(formData.latitude) : undefined,
        longitude: formData.longitude ? parseFloat(formData.longitude) : undefined,
        total_area_acres: parseFloat(formData.total_area_acres),
        soil_type: formData.soil_type,
        irrigation_type: formData.irrigation_type,
        water_source: formData.water_source.trim() || undefined,
        additional_notes: notes || undefined,
      };

      const result = await api.createFarm(payload);
      router.push(`/farms/${result.id}`);
    } catch (err) {
      setError(err.message || "Failed to register farm");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "5rem", maxWidth: "860px" }}>
      {/* Back button */}
      <div style={{ marginBottom: "1.5rem" }}>
        <Link href="/farms" style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.4rem",
          color: "var(--text-muted)",
          fontSize: "0.9rem",
          fontWeight: 600
        }}>
          <ArrowLeft size={16} />
          <span>Back to Farm Lands</span>
        </Link>
      </div>

      <div className="glass-panel" style={{ padding: "2.5rem" }}>
        {/* Header */}
        <div style={{ borderBottom: "1px solid var(--border-light)", paddingBottom: "1.5rem", marginBottom: "2rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem" }}>
            <span className="badge badge-green">
              <MapPin size={14} /> चरण 1 • Step 1
            </span>
          </div>
          <h1 style={{ fontSize: "2rem", color: "var(--primary-950)", marginBottom: "0.4rem" }}>
            Register New Farm Land
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Enter your land specifications, location, dimensions, soil profile, and water supply to receive customized AI crop intelligence.
          </p>
        </div>

        {error && (
          <div style={{
            background: "var(--danger-50)",
            border: "1px solid var(--danger-100)",
            color: "var(--danger-700)",
            padding: "0.85rem 1.25rem",
            borderRadius: "var(--radius-md)",
            marginBottom: "1.75rem",
            fontSize: "0.9rem"
          }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* ── Section 1: Basic Farm Details ── */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ fontSize: "1.15rem", color: "var(--primary-900)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                width: "1.5rem",
                height: "1.5rem",
                borderRadius: "50%",
                background: "var(--primary-100)",
                color: "var(--primary-700)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.8rem",
                fontWeight: 700
              }}>1</span>
              Farm & Farmer Identity
            </h3>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="farm-name-input">
                  Farm Land Name *
                  <span className="form-hint">(e.g., हरियाली फार्म / North Field)</span>
                </label>
                <input
                  type="text"
                  id="farm-name-input"
                  name="name"
                  required
                  placeholder="e.g. Green Valley Farm #1"
                  value={formData.name}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="farmer-name-input">
                  Farmer / Owner Name *
                </label>
                <input
                  type="text"
                  id="farmer-name-input"
                  name="owner_name"
                  required
                  placeholder="e.g. Gurpreet Singh / Ramesh Patel"
                  value={formData.owner_name}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>
            </div>
          </div>

          {/* ── Section 2: Location Details ── */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ fontSize: "1.15rem", color: "var(--primary-900)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                width: "1.5rem",
                height: "1.5rem",
                borderRadius: "50%",
                background: "var(--primary-100)",
                color: "var(--primary-700)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.8rem",
                fontWeight: 700
              }}>2</span>
              Geographic Location
            </h3>

            <div className="grid-3">
              <div className="form-group">
                <label className="form-label" htmlFor="state-select">
                  State / राज्य *
                </label>
                <select
                  id="state-select"
                  name="location_state"
                  value={formData.location_state}
                  onChange={handleChange}
                  className="form-select"
                >
                  {states.length > 0 ? (
                    states.map((st) => (
                      <option key={st} value={st}>
                        {st}
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="Punjab">Punjab</option>
                      <option value="Haryana">Haryana</option>
                      <option value="Uttar Pradesh">Uttar Pradesh</option>
                      <option value="Madhya Pradesh">Madhya Pradesh</option>
                      <option value="Rajasthan">Rajasthan</option>
                      <option value="Maharashtra">Maharashtra</option>
                      <option value="Gujarat">Gujarat</option>
                    </>
                  )}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="district-input">
                  District / ज़िला
                </label>
                <input
                  type="text"
                  id="district-input"
                  name="location_district"
                  placeholder="e.g. Ludhiana, Karnal, Meerut"
                  value={formData.location_district}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="village-input">
                  Village / गाँव
                </label>
                <input
                  type="text"
                  id="village-input"
                  name="location_village"
                  placeholder="e.g. Raikot, Taraori"
                  value={formData.location_village}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>
            </div>
          </div>

          {/* ── Section 3: Land Size & Dimensions ── */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ fontSize: "1.15rem", color: "var(--primary-900)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                width: "1.5rem",
                height: "1.5rem",
                borderRadius: "50%",
                background: "var(--primary-100)",
                color: "var(--primary-700)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.8rem",
                fontWeight: 700
              }}>3</span>
              Land Area & Dimensions
            </h3>

            <div className="grid-3">
              <div className="form-group">
                <label className="form-label" htmlFor="area-acres-input">
                  Total Area (Acres) *
                </label>
                <input
                  type="number"
                  id="area-acres-input"
                  name="total_area_acres"
                  step="0.1"
                  min="0.1"
                  required
                  placeholder="e.g. 5.5"
                  value={formData.total_area_acres}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="dimension-length-input">
                  Length (Feet)
                  <span className="form-hint">(Optional)</span>
                </label>
                <input
                  type="number"
                  id="dimension-length-input"
                  name="dimension_length_ft"
                  placeholder="e.g. 600"
                  value={formData.dimension_length_ft}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="dimension-width-input">
                  Width (Feet)
                  <span className="form-hint">(Optional)</span>
                </label>
                <input
                  type="number"
                  id="dimension-width-input"
                  name="dimension_width_ft"
                  placeholder="e.g. 400"
                  value={formData.dimension_width_ft}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>
            </div>

            {formData.dimension_length_ft && formData.dimension_width_ft && (
              <div style={{
                background: "var(--primary-50)",
                border: "1px dashed var(--primary-300)",
                borderRadius: "var(--radius-md)",
                padding: "0.75rem 1rem",
                fontSize: "0.85rem",
                color: "var(--primary-800)",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem"
              }}>
                <Ruler size={16} />
                <span>
                  Calculated Perimeter: <strong>{2 * (Number(formData.dimension_length_ft) + Number(formData.dimension_width_ft))} ft</strong> |
                  Area in Sq Ft: <strong>{(Number(formData.dimension_length_ft) * Number(formData.dimension_width_ft)).toLocaleString()} sq ft</strong> (≈ {( (Number(formData.dimension_length_ft) * Number(formData.dimension_width_ft)) / 43560 ).toFixed(2)} acres)
                </span>
              </div>
            )}
          </div>

          {/* ── Section 4: Soil Profile ── */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ fontSize: "1.15rem", color: "var(--primary-900)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                width: "1.5rem",
                height: "1.5rem",
                borderRadius: "50%",
                background: "var(--primary-100)",
                color: "var(--primary-700)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.8rem",
                fontWeight: 700
              }}>4</span>
              Soil Type (Select closest match)
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "1rem" }}>
              Soil type determines water retention capacity and fertilizer schedules.
            </p>

            <div className="grid-4" style={{ gap: "0.75rem" }}>
              {(soilTypes.length > 0 ? soilTypes : [
                { id: "alluvial", name: "Alluvial Soil", name_hi: "जलोढ़ मिट्टी", icon: "🏔️" },
                { id: "black", name: "Black Soil", name_hi: "काली मिट्टी", icon: "⬛" },
                { id: "red", name: "Red Soil", name_hi: "लाल मिट्टी", icon: "🟥" },
                { id: "laterite", name: "Laterite Soil", name_hi: "लैटेराइट मिट्टी", icon: "🟫" },
                { id: "desert", name: "Desert/Arid Soil", name_hi: "मरुस्थली मिट्टी", icon: "🏜️" },
                { id: "mountain", name: "Mountain Soil", name_hi: "पर्वतीय मिट्टी", icon: "⛰️" },
                { id: "peaty", name: "Peaty/Marshy Soil", name_hi: "दलदली मिट्टी", icon: "🌿" },
                { id: "saline", name: "Saline Soil", name_hi: "लवणीय मिट्टी", icon: "🧂" },
              ]).map((st) => {
                const selected = formData.soil_type === st.name;
                return (
                  <button
                    type="button"
                    key={st.id || st.name}
                    id={`soil-option-${st.id}`}
                    onClick={() => handleSoilSelect(st.name)}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "0.85rem 0.5rem",
                      borderRadius: "var(--radius-md)",
                      background: selected ? "var(--primary-100)" : "#ffffff",
                      border: selected ? "2px solid var(--primary-600)" : "1.5px solid var(--border-light)",
                      cursor: "pointer",
                      transition: "all 0.18s ease",
                      position: "relative"
                    }}
                  >
                    <span style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>{st.icon}</span>
                    <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--primary-950)" }}>
                      {st.name}
                    </span>
                    <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                      {st.name_hi}
                    </span>
                    {selected && (
                      <div style={{
                        position: "absolute",
                        top: "6px",
                        right: "6px",
                        width: "18px",
                        height: "18px",
                        borderRadius: "50%",
                        background: "var(--primary-600)",
                        color: "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center"
                      }}>
                        <Check size={12} strokeWidth={3} />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── Section 5: Irrigation & Water ── */}
          <div style={{ marginBottom: "2.5rem" }}>
            <h3 style={{ fontSize: "1.15rem", color: "var(--primary-900)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                width: "1.5rem",
                height: "1.5rem",
                borderRadius: "50%",
                background: "var(--primary-100)",
                color: "var(--primary-700)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.8rem",
                fontWeight: 700
              }}>5</span>
              Irrigation System & Water Supply
            </h3>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="irrigation-select">
                  Irrigation System *
                </label>
                <select
                  id="irrigation-select"
                  name="irrigation_type"
                  value={formData.irrigation_type}
                  onChange={handleChange}
                  className="form-select"
                >
                  <option value="Tube Well / Borewell">Tube Well / Borewell (नलकूप)</option>
                  <option value="Canal Irrigation">Canal Irrigation (नहरी सिंचाई)</option>
                  <option value="Drip Irrigation">Drip Irrigation (ड्रिप/टपक सिंचाई - 70% Water Saver)</option>
                  <option value="Sprinkler System">Sprinkler System (फव्वारा सिंचाई)</option>
                  <option value="Rainfed (Monsoon Dependent)">Rainfed (वर्षा आधारित)</option>
                  <option value="River / Pond Pumping">River / Pond Pumping (नदी या तालाब)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="water-source-input">
                  Water Source Specifications
                </label>
                <input
                  type="text"
                  id="water-source-input"
                  name="water_source"
                  placeholder="e.g. 150 ft deep borewell, sweet water"
                  value={formData.water_source}
                  onChange={handleChange}
                  className="form-input"
                />
              </div>
            </div>

            <div className="form-group" style={{ marginTop: "0.5rem" }}>
              <label className="form-label" htmlFor="notes-textarea">
                Additional Notes / Topography
                <span className="form-hint">(Slope, fencing, nearby canal, etc.)</span>
              </label>
              <textarea
                id="notes-textarea"
                name="additional_notes"
                placeholder="e.g. Well-leveled alluvial field, fenced on east boundary..."
                value={formData.additional_notes}
                onChange={handleChange}
                className="form-textarea"
                rows={3}
              />
            </div>
          </div>

          {/* Form Actions */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "1rem",
            borderTop: "1px solid var(--border-light)",
            paddingTop: "1.75rem"
          }}>
            <Link href="/farms" className="btn btn-secondary">
              Cancel
            </Link>
            <button
              type="submit"
              id="btn-submit-farm"
              disabled={submitting}
              className="btn btn-primary btn-lg"
            >
              {submitting ? (
                <span>Registering Farm...</span>
              ) : (
                <>
                  <Save size={18} />
                  <span>Save Farm & Continue to Crops</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

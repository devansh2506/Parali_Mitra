"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { 
  Wheat, 
  ArrowLeft, 
  MapPin, 
  Calendar, 
  Sparkles, 
  Leaf, 
  Layers, 
  Check, 
  Save,
  HelpCircle
} from "lucide-react";
import { api } from "@/lib/api";

function AddCropForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedFarmId = searchParams.get("farm_id") || "";

  const [farms, setFarms] = useState([]);
  const [cropsRef, setCropsRef] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [formData, setFormData] = useState({
    farm_id: preselectedFarmId,
    crop_name: "Wheat",
    crop_type: "Rabi",
    variety: "",
    area_acres: "",
    sowing_date: new Date().toISOString().split("T")[0],
    current_stage: "Vegetative",
    fertilizers_input: "Urea, DAP, Zinc Sulphate",
    pesticides_input: "",
  });

  useEffect(() => {
    // Load farms and crop reference data
    api.getFarms()
      .then((data) => {
        setFarms(data);
        if (!preselectedFarmId && data.length > 0) {
          setFormData((prev) => ({ ...prev, farm_id: data[0].id }));
        }
      })
      .catch(() => {});

    api.getCropsRef()
      .then((res) => {
        if (res && res.crops) {
          setCropsRef(res.crops);
        }
      })
      .catch(() => {});
  }, [preselectedFarmId]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSelectPredefinedCrop = (crop) => {
    setFormData((prev) => ({
      ...prev,
      crop_name: crop.name,
      crop_type: crop.type || prev.crop_type,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!formData.farm_id) {
      setError("Please select a farm land to assign this crop.");
      return;
    }
    if (!formData.crop_name.trim()) {
      setError("Please specify the crop name.");
      return;
    }
    if (!formData.area_acres || Number(formData.area_acres) <= 0) {
      setError("Please enter a valid sown area in acres.");
      return;
    }

    try {
      setSubmitting(true);

      const fertilizers = formData.fertilizers_input
        ? formData.fertilizers_input.split(",").map((s) => s.trim()).filter(Boolean)
        : [];

      const pesticides = formData.pesticides_input
        ? formData.pesticides_input.split(",").map((s) => s.trim()).filter(Boolean)
        : [];

      const payload = {
        farm_id: formData.farm_id,
        crop_name: formData.crop_name.trim(),
        crop_type: formData.crop_type,
        variety: formData.variety.trim() || undefined,
        area_acres: parseFloat(formData.area_acres),
        sowing_date: formData.sowing_date || undefined,
        current_stage: formData.current_stage,
        fertilizers_used: fertilizers,
        pesticides_used: pesticides,
      };

      const result = await api.createCrop(payload);
      // Navigate to the crop detail page which immediately generates & shows the AI analysis
      router.push(`/crops/${result.id}`);
    } catch (err) {
      setError(err.message || "Failed to add crop");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "5rem", maxWidth: "860px" }}>
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
          <span>Back to Sown Crops</span>
        </Link>
      </div>

      <div className="glass-panel" style={{ padding: "2.5rem" }}>
        <div style={{ borderBottom: "1px solid var(--border-light)", paddingBottom: "1.5rem", marginBottom: "2rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem" }}>
            <span className="badge badge-gold">
              <Wheat size={14} /> चरण 2 • Step 2
            </span>
          </div>
          <h1 style={{ fontSize: "2rem", color: "var(--primary-950)", marginBottom: "0.4rem" }}>
            Add Sown Crop Details
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Enter crop variety, area sown, sowing date, and current stage to trigger precision AI agricultural care, harvest timing, and disease prevention.
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
          {/* Farm Selection */}
          <div className="form-group" style={{ marginBottom: "2rem" }}>
            <label className="form-label" htmlFor="farm-select">
              Select Farm Land *
            </label>
            {farms.length === 0 ? (
              <div style={{
                background: "var(--primary-50)",
                padding: "1rem",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--primary-200)",
                fontSize: "0.9rem"
              }}>
                No farms registered yet!{" "}
                <Link href="/farms/new" style={{ color: "var(--primary-700)", fontWeight: 700, textDecoration: "underline" }}>
                  Please register a farm land first.
                </Link>
              </div>
            ) : (
              <select
                id="farm-select"
                name="farm_id"
                required
                value={formData.farm_id}
                onChange={handleChange}
                className="form-select"
              >
                <option value="">-- Choose Farm --</option>
                {farms.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} ({f.total_area_acres} Acres) — {f.location_state}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Quick Predefined Indian Crops Selector */}
          <div style={{ marginBottom: "2rem" }}>
            <label className="form-label" style={{ marginBottom: "0.75rem" }}>
              Common Indian Crops (Click to quick-select)
            </label>
            <div style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.5rem"
            }}>
              {(cropsRef.length > 0 ? cropsRef.slice(0, 10) : [
                { name: "Wheat", name_hi: "गेहूं", type: "Rabi", icon: "🌾" },
                { name: "Rice", name_hi: "चावल / धान", type: "Kharif", icon: "🍚" },
                { name: "Sugarcane", name_hi: "गन्ना", type: "Perennial", icon: "🎋" },
                { name: "Cotton", name_hi: "कपास", type: "Kharif", icon: "☁️" },
                { name: "Mustard", name_hi: "सरसों", type: "Rabi", icon: "🌻" },
                { name: "Maize", name_hi: "मक्का", type: "Kharif", icon: "🌽" },
                { name: "Potato", name_hi: "आलू", type: "Rabi", icon: "🥔" },
                { name: "Tomato", name_hi: "टमाटर", type: "Rabi", icon: "🍅" },
                { name: "Soybean", name_hi: "सोयाबीन", type: "Kharif", icon: "🫘" },
              ]).map((c) => {
                const selected = formData.crop_name.toLowerCase() === c.name.toLowerCase();
                return (
                  <button
                    type="button"
                    key={c.name}
                    id={`quick-crop-${c.name.toLowerCase()}`}
                    onClick={() => handleSelectPredefinedCrop(c)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.35rem",
                      padding: "0.45rem 0.85rem",
                      borderRadius: "var(--radius-full)",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      background: selected ? "var(--primary-600)" : "#ffffff",
                      color: selected ? "#ffffff" : "var(--text-main)",
                      border: selected ? "1px solid var(--primary-700)" : "1px solid var(--border-light)",
                      cursor: "pointer",
                      transition: "all 0.15s ease"
                    }}
                  >
                    <span>{c.icon || "🌱"}</span>
                    <span>{c.name}</span>
                    <span style={{ fontSize: "0.75rem", opacity: selected ? 0.9 : 0.7 }}>
                      ({c.name_hi})
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Crop Specifications */}
          <div className="grid-3" style={{ marginBottom: "1.5rem" }}>
            <div className="form-group">
              <label className="form-label" htmlFor="crop-name-input">
                Crop Name *
              </label>
              <input
                type="text"
                id="crop-name-input"
                name="crop_name"
                required
                placeholder="e.g. Wheat (गेहूं)"
                value={formData.crop_name}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="crop-type-select">
                Cropping Season *
              </label>
              <select
                id="crop-type-select"
                name="crop_type"
                value={formData.crop_type}
                onChange={handleChange}
                className="form-select"
              >
                <option value="Rabi">Rabi / रबी (Winter: Oct–March)</option>
                <option value="Kharif">Kharif / खरीफ (Monsoon: June–Oct)</option>
                <option value="Zaid">Zaid / जायद (Summer: March–June)</option>
                <option value="Perennial">Perennial / बारहमासी (Sugarcane, Fruit)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="variety-input">
                Variety / किस्म
                <span className="form-hint">(Optional)</span>
              </label>
              <input
                type="text"
                id="variety-input"
                name="variety"
                placeholder="e.g. HD-2967, PBW 550, Pusa 1121"
                value={formData.variety}
                onChange={handleChange}
                className="form-input"
              />
            </div>
          </div>

          {/* Area, Sowing Date, Stage */}
          <div className="grid-3" style={{ marginBottom: "1.5rem" }}>
            <div className="form-group">
              <label className="form-label" htmlFor="crop-area-input">
                Area Under Crop (Acres) *
              </label>
              <input
                type="number"
                id="crop-area-input"
                name="area_acres"
                step="0.1"
                min="0.1"
                required
                placeholder="e.g. 4.0"
                value={formData.area_acres}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="sowing-date-input">
                Sowing Date / बुवाई तिथि *
              </label>
              <input
                type="date"
                id="sowing-date-input"
                name="sowing_date"
                required
                value={formData.sowing_date}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="stage-select">
                Current Growth Stage *
              </label>
              <select
                id="stage-select"
                name="current_stage"
                value={formData.current_stage}
                onChange={handleChange}
                className="form-select"
              >
                <option value="Germination">Germination (अंकुरण)</option>
                <option value="Vegetative">Vegetative Growth (वानस्पतिक वृद्धि)</option>
                <option value="Tillering / Branching">Tillering / कल्ले फूटना</option>
                <option value="Flowering">Flowering / फूल आना</option>
                <option value="Grain Filling / Pod Formation">Grain Filling / दाना भरना</option>
                <option value="Maturity">Maturity / परिपक्वता</option>
                <option value="Harvest-Ready">Ready for Harvest / कटाई हेतु तैयार</option>
              </select>
            </div>
          </div>

          {/* Fertilizers & Pesticides */}
          <div className="grid-2" style={{ marginBottom: "2.5rem" }}>
            <div className="form-group">
              <label className="form-label" htmlFor="fertilizers-input">
                Fertilizers Used so far
                <span className="form-hint">(Comma separated)</span>
              </label>
              <input
                type="text"
                id="fertilizers-input"
                name="fertilizers_input"
                placeholder="e.g. Urea 50kg, DAP, Vermicompost"
                value={formData.fertilizers_input}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="pesticides-input">
                Pesticides / Insecticides Sprayed
                <span className="form-hint">(Comma separated)</span>
              </label>
              <input
                type="text"
                id="pesticides-input"
                name="pesticides_input"
                placeholder="e.g. Neem Oil spray, Chlorpyrifos"
                value={formData.pesticides_input}
                onChange={handleChange}
                className="form-input"
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
            <Link href="/crops" className="btn btn-secondary">
              Cancel
            </Link>
            <button
              type="submit"
              id="btn-submit-crop"
              disabled={submitting}
              className="btn btn-primary btn-lg"
            >
              {submitting ? (
                <span>Generating AI Analysis...</span>
              ) : (
                <>
                  <Sparkles size={18} />
                  <span>Save Crop & Run AI Analysis</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function NewCropPage() {
  return (
    <Suspense fallback={<div className="container" style={{ padding: "4rem 0" }}>Loading form...</div>}>
      <AddCropForm />
    </Suspense>
  );
}

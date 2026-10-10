"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  Wheat, 
  PlusCircle, 
  MapPin, 
  Calendar, 
  Sparkles, 
  Stethoscope, 
  Recycle, 
  Search, 
  Trash2, 
  Clock,
  ArrowRight,
  ShieldAlert
} from "lucide-react";
import { api } from "@/lib/api";

export default function CropsListPage() {
  const [crops, setCrops] = useState([]);
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedFarmId, setSelectedFarmId] = useState("");

  const loadData = async () => {
    try {
      setLoading(true);
      const [cropsList, farmsList] = await Promise.all([
        api.getCrops(),
        api.getFarms(),
      ]);
      setCrops(cropsList);
      setFarms(farmsList);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleDelete = async (id, name) => {
    if (!confirm(`Delete crop "${name}"?`)) return;
    try {
      await api.deleteCrop(id);
      setCrops(crops.filter((c) => c.id !== id));
    } catch (err) {
      alert("Error: " + err.message);
    }
  };

  const farmMap = farms.reduce((acc, f) => {
    acc[f.id] = f.name;
    return acc;
  }, {});

  const filteredCrops = crops.filter((c) => {
    const matchesSearch =
      c.crop_name.toLowerCase().includes(search.toLowerCase()) ||
      (c.variety && c.variety.toLowerCase().includes(search.toLowerCase())) ||
      (farmMap[c.farm_id] && farmMap[c.farm_id].toLowerCase().includes(search.toLowerCase()));

    const matchesFarm = selectedFarmId ? c.farm_id === selectedFarmId : true;
    return matchesSearch && matchesFarm;
  });

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "5rem" }}>
      {/* Page Header */}
      <div style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1.25rem",
        marginBottom: "2rem"
      }}>
        <div>
          <span className="badge badge-gold" style={{ marginBottom: "0.5rem" }}>
            🌾 फसल चक्र • Crop Intelligence
          </span>
          <h1 style={{ fontSize: "2.2rem", color: "var(--primary-950)" }}>
            Sown Crops & AI Care
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Track sown crops, growth timelines, harvest predictions, and disease protection across all your farms.
          </p>
        </div>

        <Link href="/crops/new" id="btn-add-crop-top" className="btn btn-primary btn-lg">
          <PlusCircle size={20} />
          <span>Add Sown Crop</span>
        </Link>
      </div>

      {/* Filter and Farm Selection */}
      <div className="glass-panel" style={{
        padding: "1rem 1.25rem",
        marginBottom: "2rem",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: "1rem"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flex: 1, minWidth: "220px" }}>
          <Search size={18} color="var(--primary-600)" />
          <input
            type="text"
            id="search-crops-input"
            placeholder="Search by crop name (Wheat, Rice...), variety, or farm..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              border: "none",
              outline: "none",
              width: "100%",
              fontSize: "0.95rem",
              background: "transparent",
              color: "var(--text-main)"
            }}
          />
        </div>

        <div style={{ minWidth: "200px" }}>
          <select
            id="filter-farm-select"
            value={selectedFarmId}
            onChange={(e) => setSelectedFarmId(e.target.value)}
            className="form-select"
            style={{ padding: "0.5rem 0.75rem", fontSize: "0.88rem" }}
          >
            <option value="">All Farm Lands ({farms.length})</option>
            {farms.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "4rem 0" }}>
          <p style={{ color: "var(--text-muted)" }}>Loading crop records...</p>
        </div>
      ) : filteredCrops.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: "center", padding: "4.5rem 2rem", maxWidth: "600px", margin: "0 auto" }}>
          <Wheat size={48} color="var(--earth-500)" style={{ margin: "0 auto 1.25rem" }} />
          <h2 style={{ fontSize: "1.5rem", color: "var(--primary-950)", marginBottom: "0.5rem" }}>
            {crops.length === 0 ? "No crops recorded yet" : "No matching crops found"}
          </h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", marginBottom: "1.75rem" }}>
            {crops.length === 0
              ? "Add the crops currently sown in your fields to receive precision AI care instructions and harvest forecasts."
              : "Try changing your search keywords or farm selection."}
          </p>
          <Link href="/crops/new" id="empty-add-crop-btn" className="btn btn-primary btn-lg">
            <PlusCircle size={20} />
            <span>Add First Crop</span>
          </Link>
        </div>
      ) : (
        <div className="grid-3" style={{ gap: "1.5rem" }}>
          {filteredCrops.map((crop) => (
            <div key={crop.id} className="eco-card" style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                <div>
                  <h3 style={{ fontSize: "1.3rem", color: "var(--primary-950)", marginBottom: "0.2rem" }}>
                    {crop.crop_name}
                  </h3>
                  <div style={{ fontSize: "0.85rem", color: "var(--primary-700)", fontWeight: 600 }}>
                    Farm: {farmMap[crop.farm_id] || "Assigned Farm"}
                  </div>
                </div>

                <span className="badge badge-gold" style={{ fontSize: "0.78rem" }}>
                  {crop.current_stage || "Active"}
                </span>
              </div>

              <div style={{
                fontSize: "0.88rem",
                color: "var(--text-body)",
                display: "flex",
                flexDirection: "column",
                gap: "0.45rem",
                marginBottom: "1.25rem",
                background: "var(--surface-muted)",
                padding: "0.85rem 1rem",
                borderRadius: "var(--radius-md)",
                flex: 1
              }}>
                <div>
                  Season: <strong>{crop.crop_type}</strong> | Variety: <strong>{crop.variety || "Standard"}</strong>
                </div>
                <div>
                  Area Under Crop: <strong>{crop.area_acres} Acres</strong>
                </div>
                {crop.sowing_date && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--text-muted)" }}>
                    <Calendar size={14} />
                    <span>Sown on: {crop.sowing_date}</span>
                  </div>
                )}
                {crop.expected_harvest_date && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--primary-800)", fontWeight: 600 }}>
                    <Clock size={14} color="var(--primary-600)" />
                    <span>Est. Harvest: {crop.expected_harvest_date}</span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.6rem",
                borderTop: "1px solid var(--border-light)",
                paddingTop: "1rem",
                marginTop: "auto"
              }}>
                <Link
                  href={`/crops/${crop.id}`}
                  id={`btn-analyze-crop-${crop.id}`}
                  className="btn btn-primary btn-sm"
                  style={{ width: "100%" }}
                >
                  <Sparkles size={16} />
                  <span>Full AI Crop Analysis</span>
                </Link>

                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <Link
                    href={`/health?crop_id=${crop.id}`}
                    id={`btn-health-crop-${crop.id}`}
                    className="btn btn-secondary btn-sm"
                    style={{ flex: 1 }}
                  >
                    <Stethoscope size={14} />
                    <span>Doctor</span>
                  </Link>

                  <Link
                    href={`/stubble?crop_id=${crop.id}`}
                    id={`btn-stubble-crop-${crop.id}`}
                    className="btn btn-accent btn-sm"
                    style={{ flex: 1 }}
                  >
                    <Recycle size={14} />
                    <span>Stubble</span>
                  </Link>

                  <button
                    onClick={() => handleDelete(crop.id, crop.crop_name)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--danger-500)",
                      cursor: "pointer",
                      padding: "0.4rem",
                      display: "flex",
                      alignItems: "center"
                    }}
                    title="Delete crop"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

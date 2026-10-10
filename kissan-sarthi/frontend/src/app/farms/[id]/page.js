"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  MapPin, 
  ArrowLeft, 
  Wheat, 
  PlusCircle, 
  Droplets, 
  Mountain, 
  Ruler, 
  Calendar, 
  Sparkles, 
  Stethoscope, 
  Recycle, 
  Trash2, 
  CheckCircle,
  AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";

export default function FarmDetailPage({ params }) {
  // Unwrap params using React.use() in Next.js 15/16
  const resolvedParams = use(params);
  const farmId = resolvedParams.id;
  const router = useRouter();

  const [farm, setFarm] = useState(null);
  const [crops, setCrops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [farmData, cropsData] = await Promise.all([
          api.getFarm(farmId),
          api.getCrops(farmId),
        ]);
        setFarm(farmData);
        setCrops(cropsData);
      } catch (err) {
        setError(err.message || "Failed to load farm details");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [farmId]);

  const handleDeleteFarm = async () => {
    if (!confirm("Are you sure you want to delete this farm? All associated crops will be deleted.")) {
      return;
    }
    try {
      await api.deleteFarm(farmId);
      router.push("/farms");
    } catch (err) {
      alert("Error: " + err.message);
    }
  };

  if (loading) {
    return (
      <div className="container" style={{ padding: "5rem 0", textAlign: "center" }}>
        <p style={{ color: "var(--text-muted)" }}>Loading farm details...</p>
      </div>
    );
  }

  if (error || !farm) {
    return (
      <div className="container" style={{ padding: "4rem 0" }}>
        <div style={{
          background: "var(--danger-50)",
          border: "1px solid var(--danger-100)",
          padding: "1.5rem",
          borderRadius: "var(--radius-md)",
          color: "var(--danger-700)"
        }}>
          <h3>Farm Not Found</h3>
          <p>{error || "Could not retrieve the farm record."}</p>
          <Link href="/farms" className="btn btn-secondary" style={{ marginTop: "1rem" }}>
            Return to Farms
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "5rem" }}>
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
          <span>Back to All Farms</span>
        </Link>
      </div>

      {/* Farm Profile Header Card */}
      <div className="glass-panel" style={{
        padding: "2rem 2.5rem",
        marginBottom: "2.5rem",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "1.5rem"
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.5rem" }}>
            <span className="badge badge-green">
              <MapPin size={14} /> Registered Farm Land
            </span>
            <span className="badge badge-gold">
              {farm.total_area_acres} Total Acres
            </span>
          </div>

          <h1 style={{ fontSize: "2.2rem", color: "var(--primary-950)", marginBottom: "0.25rem" }}>
            {farm.name}
          </h1>
          <p style={{ fontSize: "1.05rem", color: "var(--primary-700)", fontWeight: 600, marginBottom: "0.75rem" }}>
            Farmer / Owner: {farm.owner_name}
          </p>

          <div style={{ display: "flex", flexWrap: "wrap", gap: "1.25rem", color: "var(--text-muted)", fontSize: "0.9rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <MapPin size={16} color="var(--primary-600)" />
              <span>
                {[farm.location_village, farm.location_district, farm.location_state]
                  .filter(Boolean)
                  .join(", ")}
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <Mountain size={16} color="var(--earth-700)" />
              <span>Soil: <strong>{farm.soil_type || "Alluvial"}</strong></span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <Droplets size={16} color="var(--sky-700)" />
              <span>Irrigation: <strong>{farm.irrigation_type || "Borewell"}</strong></span>
            </div>
          </div>

          {farm.additional_notes && (
            <div style={{
              marginTop: "1rem",
              background: "var(--primary-50)",
              padding: "0.6rem 0.9rem",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.85rem",
              color: "var(--primary-800)"
            }}>
              <strong>Land Notes:</strong> {farm.additional_notes}
            </div>
          )}
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", minWidth: "180px" }}>
          <Link
            href={`/crops/new?farm_id=${farm.id}`}
            id="btn-add-crop-to-farm"
            className="btn btn-primary"
          >
            <PlusCircle size={18} />
            <span>Add Sown Crop</span>
          </Link>

          <Link
            href="/health"
            className="btn btn-secondary"
          >
            <Stethoscope size={18} color="var(--primary-700)" />
            <span>Diagnose Crop</span>
          </Link>

          <button
            onClick={handleDeleteFarm}
            id="btn-delete-current-farm"
            className="btn btn-danger btn-sm"
          >
            <Trash2 size={16} />
            <span>Delete Farm</span>
          </button>
        </div>
      </div>

      {/* Sown Crops Section */}
      <div>
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "1.5rem"
        }}>
          <div>
            <h2 style={{ fontSize: "1.6rem", color: "var(--primary-950)" }}>
              Crops Sown on this Land ({crops.length})
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
              AI tracking, growth stage analysis, fertilizer schedules, and post-harvest stubble management.
            </p>
          </div>

          <Link
            href={`/crops/new?farm_id=${farm.id}`}
            className="btn btn-secondary btn-sm"
          >
            <PlusCircle size={16} />
            <span>Add Crop</span>
          </Link>
        </div>

        {crops.length === 0 ? (
          <div className="glass-panel" style={{ textAlign: "center", padding: "3.5rem 1.5rem" }}>
            <Wheat size={40} color="var(--primary-600)" style={{ margin: "0 auto 1rem" }} />
            <h3 style={{ fontSize: "1.3rem", color: "var(--primary-950)", marginBottom: "0.5rem" }}>
              No crops added to this farm yet
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", maxWidth: "450px", margin: "0 auto 1.5rem" }}>
              Enter what crops are currently sown (Wheat, Rice, Cotton, etc.) to get AI harvest dates, care calendars, and disease protection.
            </p>
            <Link
              href={`/crops/new?farm_id=${farm.id}`}
              id="empty-add-crop-btn"
              className="btn btn-primary"
            >
              <PlusCircle size={18} />
              <span>Add Your First Crop</span>
            </Link>
          </div>
        ) : (
          <div className="grid-2" style={{ gap: "1.5rem" }}>
            {crops.map((crop) => (
              <div key={crop.id} className="eco-card" style={{ display: "flex", flexDirection: "column" }}>
                <div style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  marginBottom: "0.75rem"
                }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <h3 style={{ fontSize: "1.3rem", color: "var(--primary-950)" }}>
                        {crop.crop_name}
                      </h3>
                      {crop.variety && (
                        <span className="badge badge-green" style={{ fontSize: "0.75rem" }}>
                          {crop.variety}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      Season: {crop.crop_type} | Area: <strong>{crop.area_acres || farm.total_area_acres} Acres</strong>
                    </span>
                  </div>

                  <span className={`badge ${crop.status === 'harvested' ? 'badge-blue' : 'badge-gold'}`}>
                    {crop.current_stage || "Sown"}
                  </span>
                </div>

                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                  fontSize: "0.88rem",
                  color: "var(--text-body)",
                  marginBottom: "1.25rem",
                  background: "var(--surface-muted)",
                  padding: "0.85rem 1rem",
                  borderRadius: "var(--radius-md)"
                }}>
                  {crop.sowing_date && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <Calendar size={15} color="var(--primary-700)" />
                      <span>Sowing Date: <strong>{crop.sowing_date}</strong></span>
                    </div>
                  )}

                  {crop.expected_harvest_date && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <CheckCircle size={15} color="var(--earth-700)" />
                      <span>Est. Harvest Date: <strong>{crop.expected_harvest_date}</strong></span>
                    </div>
                  )}
                </div>

                {/* Quick Action buttons */}
                <div style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "0.6rem",
                  marginTop: "auto",
                  borderTop: "1px solid var(--border-light)",
                  paddingTop: "1rem"
                }}>
                  <Link
                    href={`/crops/${crop.id}`}
                    id={`btn-view-crop-${crop.id}`}
                    className="btn btn-primary btn-sm"
                  >
                    <Sparkles size={14} />
                    <span>AI Crop Analysis</span>
                  </Link>

                  <Link
                    href={`/health?crop_id=${crop.id}`}
                    id={`btn-diagnose-crop-${crop.id}`}
                    className="btn btn-secondary btn-sm"
                  >
                    <Stethoscope size={14} />
                    <span>Check Health</span>
                  </Link>

                  <Link
                    href={`/stubble?crop_id=${crop.id}`}
                    id={`btn-stubble-crop-${crop.id}`}
                    className="btn btn-accent btn-sm"
                  >
                    <Recycle size={14} />
                    <span>Stubble Mgmt</span>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

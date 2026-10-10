"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  MapPin, 
  PlusCircle, 
  Wheat, 
  Droplets, 
  Mountain, 
  Search, 
  ArrowRight, 
  Trash2, 
  Calendar,
  AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";

export default function FarmsListPage() {
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);

  const fetchFarms = async () => {
    try {
      setLoading(true);
      const data = await api.getFarms();
      setFarms(data);
    } catch (err) {
      setError(err.message || "Failed to load farms");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFarms();
  }, []);

  const handleDelete = async (id, name) => {
    if (!confirm(`Are you sure you want to delete "${name}"? All associated crops will also be deleted.`)) {
      return;
    }
    try {
      await api.deleteFarm(id);
      setFarms(farms.filter((f) => f.id !== id));
    } catch (err) {
      alert("Error deleting farm: " + err.message);
    }
  };

  const filteredFarms = farms.filter((f) => {
    const q = search.toLowerCase();
    return (
      f.name?.toLowerCase().includes(q) ||
      f.owner_name?.toLowerCase().includes(q) ||
      f.location_state?.toLowerCase().includes(q) ||
      f.location_district?.toLowerCase().includes(q) ||
      f.soil_type?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="container" style={{ paddingTop: "2.5rem", paddingBottom: "4rem" }}>
      {/* Header Bar */}
      <div style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1.25rem",
        marginBottom: "2rem"
      }}>
        <div>
          <span className="badge badge-green" style={{ marginBottom: "0.5rem" }}>
            🏡 कृषक भूखंड • Farm Lands
          </span>
          <h1 style={{ fontSize: "2.2rem", color: "var(--primary-950)" }}>
            Registered Farm Lands
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Manage your land holdings, soil specifications, and irrigation systems.
          </p>
        </div>

        <Link href="/farms/new" id="btn-create-farm-top" className="btn btn-primary btn-lg">
          <PlusCircle size={20} />
          <span>Register New Farm</span>
        </Link>
      </div>

      {/* Filter / Search Bar */}
      <div className="glass-panel" style={{
        padding: "0.85rem 1.25rem",
        marginBottom: "2rem",
        display: "flex",
        alignItems: "center",
        gap: "0.75rem"
      }}>
        <Search size={20} color="var(--primary-600)" />
        <input
          type="text"
          id="search-farms-input"
          placeholder="Search by farm name, farmer name, state, district, or soil type..."
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
        {search && (
          <button
            onClick={() => setSearch("")}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
              fontSize: "0.85rem"
            }}
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <div style={{
          background: "var(--danger-50)",
          border: "1px solid var(--danger-100)",
          color: "var(--danger-700)",
          padding: "1rem",
          borderRadius: "var(--radius-md)",
          marginBottom: "1.5rem",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem"
        }}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: "4rem 0" }}>
          <div style={{
            display: "inline-block",
            width: "2.5rem",
            height: "2.5rem",
            border: "3px solid var(--primary-200)",
            borderTopColor: "var(--primary-600)",
            borderRadius: "50%",
            animation: "spin 1s linear infinite"
          }} />
          <p style={{ marginTop: "1rem", color: "var(--text-muted)" }}>Loading farm records...</p>
          <style jsx>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      ) : filteredFarms.length === 0 ? (
        /* Empty State */
        <div className="glass-panel" style={{
          textAlign: "center",
          padding: "4.5rem 2rem",
          maxWidth: "600px",
          margin: "0 auto"
        }}>
          <div style={{
            width: "4rem",
            height: "4rem",
            borderRadius: "50%",
            background: "var(--primary-100)",
            color: "var(--primary-700)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 1.5rem"
          }}>
            <MapPin size={32} />
          </div>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "0.75rem", color: "var(--primary-950)" }}>
            {search ? "No farms matching your search" : "No farms registered yet"}
          </h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "2rem", fontSize: "0.95rem" }}>
            {search
              ? "Try adjusting your search keywords."
              : "Start by entering your farm land details — location, area, dimensions, soil type, and irrigation source."}
          </p>
          <Link href="/farms/new" id="empty-state-add-farm" className="btn btn-primary btn-lg">
            <PlusCircle size={20} />
            <span>Register First Farm</span>
          </Link>
        </div>
      ) : (
        /* Farms Grid */
        <div className="grid-3" style={{ gap: "1.5rem" }}>
          {filteredFarms.map((farm) => (
            <div key={farm.id} className="eco-card" style={{ display: "flex", flexDirection: "column" }}>
              {/* Card Header */}
              <div style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                marginBottom: "1rem"
              }}>
                <div>
                  <h3 style={{ fontSize: "1.25rem", color: "var(--primary-950)", marginBottom: "0.2rem" }}>
                    {farm.name}
                  </h3>
                  <div style={{ fontSize: "0.85rem", color: "var(--primary-700)", fontWeight: 600 }}>
                    Farmer: {farm.owner_name}
                  </div>
                </div>
                <span className="badge badge-gold" style={{ fontSize: "0.78rem" }}>
                  {farm.total_area_acres} Acres
                </span>
              </div>

              {/* Location & Details */}
              <div style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.6rem",
                fontSize: "0.88rem",
                color: "var(--text-body)",
                marginBottom: "1.25rem",
                flex: 1
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-muted)" }}>
                  <MapPin size={16} color="var(--primary-600)" />
                  <span>
                    {[farm.location_village, farm.location_district, farm.location_state]
                      .filter(Boolean)
                      .join(", ")}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Mountain size={16} color="var(--earth-700)" />
                  <span>
                    Soil: <strong>{farm.soil_type || "Standard Alluvial"}</strong>
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Droplets size={16} color="var(--sky-700)" />
                  <span>
                    Irrigation: <strong>{farm.irrigation_type || "Tube Well / Canal"}</strong>
                  </span>
                </div>

                {farm.water_source && (
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                    Water: {farm.water_source}
                  </div>
                )}
              </div>

              {/* Card Footer Actions */}
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                borderTop: "1px solid var(--border-light)",
                paddingTop: "1rem",
                marginTop: "auto"
              }}>
                <button
                  id={`btn-delete-farm-${farm.id}`}
                  onClick={() => handleDelete(farm.id, farm.name)}
                  title="Delete farm"
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--danger-500)",
                    cursor: "pointer",
                    padding: "0.4rem",
                    borderRadius: "var(--radius-sm)",
                    display: "flex",
                    alignItems: "center"
                  }}
                >
                  <Trash2 size={16} />
                </button>

                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <Link
                    href={`/crops/new?farm_id=${farm.id}`}
                    id={`btn-add-crop-${farm.id}`}
                    className="btn btn-secondary btn-sm"
                  >
                    <Wheat size={14} />
                    <span>+ Crop</span>
                  </Link>
                  <Link
                    href={`/farms/${farm.id}`}
                    id={`btn-view-farm-${farm.id}`}
                    className="btn btn-primary btn-sm"
                  >
                    <span>Manage</span>
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

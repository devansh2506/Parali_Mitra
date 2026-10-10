/**
 * Kissan Sarthi — API Client Library
 * Handles communication with the FastAPI backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = {};

  if (!(options.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = `HTTP error ${response.status}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // ── Reference Data ──
  getStates: () => request("/api/reference-data/states"),
  getSoilTypes: () => request("/api/reference-data/soil-types"),
  getCropsRef: () => request("/api/reference-data/crops"),

  // ── Farms ──
  getFarms: () => request("/api/farms"),
  getFarm: (id) => request(`/api/farms/${id}`),
  createFarm: (data) =>
    request("/api/farms", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateFarm: (id, data) =>
    request(`/api/farms/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteFarm: (id) =>
    request(`/api/farms/${id}`, {
      method: "DELETE",
    }),

  // ── Crops ──
  getCrops: (farmId) => {
    const query = farmId ? `?farm_id=${encodeURIComponent(farmId)}` : "";
    return request(`/api/crops${query}`);
  },
  getCrop: (id) => request(`/api/crops/${id}`),
  createCrop: (data) =>
    request("/api/crops", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateCrop: (id, data) =>
    request(`/api/crops/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteCrop: (id) =>
    request(`/api/crops/${id}`, {
      method: "DELETE",
    }),
  analyzeCrop: (id) =>
    request(`/api/crops/${id}/analyze`, {
      method: "POST",
    }),
  getCropAnalysis: (id) => request(`/api/crops/${id}/analysis`),

  // ── Crop Health Doctor ──
  checkHealth: (formData) =>
    request("/api/health/check", {
      method: "POST",
      body: formData,
    }),
  getHealthHistory: (cropId) => request(`/api/health/history/${cropId}`),
  getHealthCheck: (checkId) => request(`/api/health/${checkId}`),

  // ── Stubble Management ──
  analyzeStubble: (cropId, stubbleAreaAcres) =>
    request("/api/stubble/analyze", {
      method: "POST",
      body: JSON.stringify({
        crop_id: cropId,
        stubble_area_acres: Number(stubbleAreaAcres),
      }),
    }),
  recordPledge: (cropId, stubbleAreaAcres, farmerChoice) =>
    request("/api/stubble/pledge", {
      method: "POST",
      body: JSON.stringify({
        crop_id: cropId,
        stubble_area_acres: Number(stubbleAreaAcres),
        farmer_choice: farmerChoice,
      }),
    }),
  getStubbleHistory: (cropId) => request(`/api/stubble/history/${cropId}`),
  getImpactSummary: () => request("/api/stubble/impact-summary"),
};

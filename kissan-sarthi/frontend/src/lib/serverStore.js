/**
 * Server-side in-memory data store for Vercel serverless deployment.
 * Provides fallback data and state persistence for Farms, Crops, Health Checks, and Stubble Pledges.
 */

// Global singleton to persist state across warm serverless function invocations
if (!global._kissanStore) {
  global._kissanStore = {
    farms: [
      {
        id: "farm-punjab-01",
        name: "Hariyali Krishi Farm",
        owner_name: "Sardar Gurpreet Singh",
        location_state: "Punjab",
        location_district: "Ludhiana",
        location_village: "Raikot",
        total_area_acres: 6.5,
        soil_type: "Alluvial Soil",
        irrigation_type: "Tube Well / Borewell",
        water_source: "150ft Submersible Borewell",
        additional_notes: "Dimensions: 600 ft x 450 ft. Rich alluvial loam.",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    crops: [
      {
        id: "crop-wheat-01",
        farm_id: "farm-punjab-01",
        crop_name: "Wheat",
        crop_type: "Rabi",
        variety: "HD-2967",
        area_acres: 6.5,
        sowing_date: "2026-11-05",
        expected_harvest_date: "2027-04-10",
        current_stage: "Vegetative",
        fertilizers_used: ["Urea", "DAP", "Zinc Sulphate"],
        pesticides_used: ["Neem Oil Spray"],
        status: "active",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    healthChecks: [],
    stubbleRecords: [],
    totalPledges: 142,
    totalAcresSaved: 1250,
    totalCo2SavedKg: 2680000,
    totalPm25SavedKg: 8400,
  };
}

export const store = global._kissanStore;

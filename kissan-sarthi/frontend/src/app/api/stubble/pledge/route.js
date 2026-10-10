import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function POST(request) {
  try {
    const body = await request.json();
    const area = Number(body.stubble_area_acres) || 1;
    const cropId = body.crop_id;
    const choice = body.farmer_choice || "In-Situ Mulching with Happy Seeder";

    const crop = store.crops.find((c) => c.id === cropId) || {
      crop_name: "Wheat",
      farm_id: "farm-punjab-01",
    };
    const farm = store.farms.find((f) => f.id === crop.farm_id) || {
      name: "Hariyali Krishi Farm",
      owner_name: "Sardar Gurpreet Singh",
    };

    const isWheat = crop.crop_name.toLowerCase().includes("wheat");
    const co2Saved = Math.round((isWheat ? 1780 : 2225) * area);
    const pm25Saved = Math.round((isWheat ? 5.6 : 7.0) * area);
    const trees = Math.round(co2Saved / 22);

    const certId = "KS-CERT-" + Math.random().toString(36).substring(2, 8).toUpperCase();
    const now = new Date().toISOString();

    // Increment aggregate community counters
    store.totalPledges += 1;
    store.totalAcresSaved += area;
    store.totalCo2SavedKg += co2Saved;
    store.totalPm25SavedKg += pm25Saved;

    const cert = {
      id: certId,
      certificate_id: certId,
      farmer_name: farm.owner_name || "Progressive Farmer",
      owner_name: farm.owner_name || "Progressive Farmer",
      farm_name: farm.name || "Krishi Farm",
      crop_name: crop.crop_name,
      stubble_area_acres: area,
      co2_saved_kg: co2Saved,
      pm25_saved_kg: pm25Saved,
      equivalent_trees: trees,
      farmer_choice: choice,
      pledge_date: now,
      created_at: now,
      message: "🌱 Thank you for your pledge! Your decision keeps the air clean for millions.",
    };

    store.stubbleRecords.unshift(cert);

    return NextResponse.json(cert);
  } catch (err) {
    return NextResponse.json({ detail: err.message || "Failed to record pledge" }, { status: 500 });
  }
}

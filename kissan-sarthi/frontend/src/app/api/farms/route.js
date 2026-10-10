import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function GET() {
  return NextResponse.json(store.farms);
}

export async function POST(request) {
  try {
    const body = await request.json();
    const id = "farm-" + Math.random().toString(36).substring(2, 9);
    const now = new Date().toISOString();

    const newFarm = {
      id,
      name: body.name,
      owner_name: body.owner_name,
      location_state: body.location_state || "Punjab",
      location_district: body.location_district || "",
      location_village: body.location_village || "",
      latitude: body.latitude || null,
      longitude: body.longitude || null,
      total_area_acres: Number(body.total_area_acres) || 1,
      soil_type: body.soil_type || "Alluvial Soil",
      irrigation_type: body.irrigation_type || "Tube Well / Borewell",
      water_source: body.water_source || "",
      additional_notes: body.additional_notes || "",
      created_at: now,
      updated_at: now,
    };

    store.farms.unshift(newFarm);
    return NextResponse.json(newFarm, { status: 201 });
  } catch (err) {
    return NextResponse.json({ detail: err.message || "Failed to create farm" }, { status: 400 });
  }
}

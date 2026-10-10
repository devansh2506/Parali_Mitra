import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const farmId = searchParams.get("farm_id");

  if (farmId) {
    return NextResponse.json(store.crops.filter((c) => c.farm_id === farmId));
  }
  return NextResponse.json(store.crops);
}

export async function POST(request) {
  try {
    const body = await request.json();
    const id = "crop-" + Math.random().toString(36).substring(2, 9);
    const now = new Date().toISOString();

    // Default calculated harvest date (approx 120-140 days)
    const sowing = body.sowing_date ? new Date(body.sowing_date) : new Date();
    const harvestDate = new Date(sowing);
    harvestDate.setDate(harvestDate.getDate() + 130);
    const expectedHarvest = harvestDate.toISOString().split("T")[0];

    const newCrop = {
      id,
      farm_id: body.farm_id,
      crop_name: body.crop_name,
      crop_type: body.crop_type || "Rabi",
      variety: body.variety || "Standard",
      area_acres: Number(body.area_acres) || 1,
      sowing_date: body.sowing_date || now.split("T")[0],
      expected_harvest_date: expectedHarvest,
      current_stage: body.current_stage || "Vegetative",
      fertilizers_used: Array.isArray(body.fertilizers_used) ? body.fertilizers_used : [],
      pesticides_used: Array.isArray(body.pesticides_used) ? body.pesticides_used : [],
      status: "active",
      created_at: now,
      updated_at: now,
    };

    store.crops.unshift(newCrop);
    return NextResponse.json(newCrop, { status: 201 });
  } catch (err) {
    return NextResponse.json({ detail: err.message || "Failed to create crop" }, { status: 400 });
  }
}

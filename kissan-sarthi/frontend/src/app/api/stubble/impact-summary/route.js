import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function GET() {
  return NextResponse.json({
    total_pledges: store.totalPledges,
    total_acres_saved: store.totalAcresSaved,
    total_co2_saved_kg: store.totalCo2SavedKg,
    total_pm25_saved_kg: store.totalPm25SavedKg,
    equivalent_trees: Math.round(store.totalCo2SavedKg / 22),
  });
}

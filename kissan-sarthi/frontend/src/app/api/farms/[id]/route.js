import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function GET(request, { params }) {
  const { id } = await params;
  const farm = store.farms.find((f) => f.id === id);
  if (!farm) {
    return NextResponse.json({ detail: "Farm not found" }, { status: 404 });
  }
  return NextResponse.json(farm);
}

export async function PUT(request, { params }) {
  const { id } = await params;
  const farmIndex = store.farms.findIndex((f) => f.id === id);
  if (farmIndex === -1) {
    return NextResponse.json({ detail: "Farm not found" }, { status: 404 });
  }

  const body = await request.json();
  const updated = {
    ...store.farms[farmIndex],
    ...body,
    updated_at: new Date().toISOString(),
  };
  store.farms[farmIndex] = updated;
  return NextResponse.json(updated);
}

export async function DELETE(request, { params }) {
  const { id } = await params;
  const farmIndex = store.farms.findIndex((f) => f.id === id);
  if (farmIndex === -1) {
    return NextResponse.json({ detail: "Farm not found" }, { status: 404 });
  }

  store.farms.splice(farmIndex, 1);
  // delete associated crops
  store.crops = store.crops.filter((c) => c.farm_id !== id);

  return NextResponse.json({ message: "Farm deleted successfully", id });
}

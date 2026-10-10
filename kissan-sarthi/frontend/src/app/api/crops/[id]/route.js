import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function GET(request, { params }) {
  const { id } = await params;
  const crop = store.crops.find((c) => c.id === id);
  if (!crop) {
    return NextResponse.json({ detail: "Crop not found" }, { status: 404 });
  }
  return NextResponse.json(crop);
}

export async function PUT(request, { params }) {
  const { id } = await params;
  const index = store.crops.findIndex((c) => c.id === id);
  if (index === -1) {
    return NextResponse.json({ detail: "Crop not found" }, { status: 404 });
  }

  const body = await request.json();
  const updated = {
    ...store.crops[index],
    ...body,
    updated_at: new Date().toISOString(),
  };
  store.crops[index] = updated;
  return NextResponse.json(updated);
}

export async function DELETE(request, { params }) {
  const { id } = await params;
  const index = store.crops.findIndex((c) => c.id === id);
  if (index === -1) {
    return NextResponse.json({ detail: "Crop not found" }, { status: 404 });
  }

  store.crops.splice(index, 1);
  return NextResponse.json({ message: "Crop deleted successfully", id });
}

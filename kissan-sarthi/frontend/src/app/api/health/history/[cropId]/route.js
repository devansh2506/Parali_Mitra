import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function GET(request, { params }) {
  const { cropId } = await params;
  const history = store.healthChecks.filter((h) => h.crop_id === cropId);
  return NextResponse.json(history);
}

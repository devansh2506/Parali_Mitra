import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    soil_types: [
      { id: "alluvial", name: "Alluvial Soil", name_hi: "जलोढ़ मिट्टी", icon: "🏔️", regions: ["Punjab", "UP", "Bihar", "West Bengal"] },
      { id: "black", name: "Black Soil", name_hi: "काली मिट्टी", icon: "⬛", regions: ["Maharashtra", "MP", "Gujarat"] },
      { id: "red", name: "Red Soil", name_hi: "लाल मिट्टी", icon: "🟥", regions: ["Tamil Nadu", "Karnataka", "Odisha"] },
      { id: "laterite", name: "Laterite Soil", name_hi: "लैटेराइट मिट्टी", icon: "🟫", regions: ["Kerala", "Assam", "Karnataka"] },
      { id: "desert", name: "Desert/Arid Soil", name_hi: "मरुस्थली मिट्टी", icon: "🏜️", regions: ["Rajasthan", "Gujarat"] },
      { id: "mountain", name: "Mountain Soil", name_hi: "पर्वतीय मिट्टी", icon: "⛰️", regions: ["Uttarakhand", "HP", "J&K"] },
      { id: "peaty", name: "Peaty/Marshy Soil", name_hi: "दलदली मिट्टी", icon: "🌿", regions: ["Kerala", "West Bengal"] },
      { id: "saline", name: "Saline Soil", name_hi: "लवणीय मिट्टी", icon: "🧂", regions: ["Rajasthan", "Gujarat", "Punjab"] },
    ],
  });
}

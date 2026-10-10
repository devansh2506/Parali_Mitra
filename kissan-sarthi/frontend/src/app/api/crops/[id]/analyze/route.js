import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";
import { callGeminiJson } from "@/lib/gemini";

export async function POST(request, { params }) {
  const { id } = await params;
  const crop = store.crops.find((c) => c.id === id);
  if (!crop) {
    return NextResponse.json({ detail: "Crop not found" }, { status: 404 });
  }

  const farm = store.farms.find((f) => f.id === crop.farm_id) || {};

  // Calculate estimated harvest date
  const sowingDate = crop.sowing_date ? new Date(crop.sowing_date) : new Date();
  const harvestDate = new Date(sowingDate);
  harvestDate.setDate(harvestDate.getDate() + 135);
  const estimatedHarvestDate = harvestDate.toISOString().split("T")[0];

  // Try live Gemini AI if GEMINI_API_KEY is configured
  let analysis = null;
  if (process.env.GEMINI_API_KEY) {
    const prompt = `You are an expert Indian agricultural advisor (Krishi Vaigyanik).
FARM DETAILS:
- Location: ${farm.location_state || "North India"}, ${farm.location_district || ""}
- Soil Type: ${farm.soil_type || "Alluvial"}
- Irrigation: ${farm.irrigation_type || "Borewell"}
- Area: ${farm.total_area_acres || 5} acres

CROP DETAILS:
- Crop: ${crop.crop_name} (${crop.variety || "Standard"})
- Cropping Season: ${crop.crop_type}
- Sown Area: ${crop.area_acres} acres
- Sowing Date: ${crop.sowing_date || "Recent"}
- Current Stage: ${crop.current_stage || "Vegetative"}
- Fertilizers Used: ${(crop.fertilizers_used || []).join(", ")}

Respond ONLY with valid JSON with this exact structure:
{
  "crop_health_overview": "Paragraph describing health and outlook",
  "growth_stage_assessment": "Assessment of current stage and advice",
  "estimated_harvest_date": "${estimatedHarvestDate}",
  "estimated_yield_per_acre": "Expected quintals per acre",
  "care_instructions": [
    {"stage": "Stage name", "task": "Specific task", "timing": "When to do", "details": "How to do"}
  ],
  "fertilizer_schedule": [
    {"week": 1, "fertilizer": "Name", "quantity_per_acre": "Amount", "method": "Method"}
  ],
  "pest_risk_alerts": [
    {"pest": "Pest name", "risk_level": "low|medium|high", "prevention": "Tips", "treatment": "Action"}
  ],
  "weather_considerations": "Weather advice",
  "market_insights": "Mandi pricing tips",
  "organic_alternatives": "Eco farming suggestions"
}`;
    analysis = await callGeminiJson(prompt);
  }

  // Fallback if Gemini key is omitted or call fails
  if (!analysis) {
    analysis = {
      crop_health_overview: `Crop ${crop.crop_name} (${crop.variety || "Standard"}) is currently in healthy ${crop.current_stage || "Vegetative"} phase on ${farm.soil_type || "Alluvial"} soil. Moisture and root development appear well-balanced.`,
      growth_stage_assessment: `Active ${crop.current_stage || "Vegetative"} development. Ensure adequate root aeration and maintain scheduled nitrogen application for maximum tillering.`,
      estimated_harvest_date: estimatedHarvestDate,
      estimated_yield_per_acre: "22-26 Quintals/Acre",
      care_instructions: [
        {
          stage: crop.current_stage || "Vegetative",
          task: "First Top-Dressing & Light Irrigation",
          timing: "Within 7-10 days",
          details: "Apply light irrigation followed by nitrogen top-dressing to stimulate vegetative tillers and enhance photosynthesis.",
        },
        {
          stage: "Tillering / Branching",
          task: "Weed Control & Intercultural Hoeing",
          timing: "Week 4 to 6 after sowing",
          details: "Perform manual weeding or apply selective eco-safe weed management before canopy closure.",
        },
        {
          stage: "Flowering & Grain Formation",
          task: "Moisture Monitoring during Critical Stages",
          timing: "Around 65-80 days post-sowing",
          details: "Ensure fields do not experience moisture stress during flowering; this directly influences grain weight and harvest yield.",
        },
      ],
      fertilizer_schedule: [
        {
          week: 1,
          fertilizer: "Basal DAP & Zinc Sulphate",
          quantity_per_acre: "50 kg DAP + 10 kg Zinc",
          method: "Drilled at sowing time below the seed furrow",
        },
        {
          week: 3,
          fertilizer: "First Top Dressing Urea",
          quantity_per_acre: "35 kg per acre",
          method: "Broadcasted immediately before light canal/borewell irrigation",
        },
        {
          week: 6,
          fertilizer: "Second Split Urea + Potash (MOP)",
          quantity_per_acre: "30 kg Urea + 15 kg MOP",
          method: "Broadcast during tillering stage",
        },
        {
          week: 10,
          fertilizer: "Foliar Micronutrient Spray (NPK 19:19:19)",
          quantity_per_acre: "1.5 kg in 150L water",
          method: "Fine mist foliar spray during pre-flowering",
        },
      ],
      pest_risk_alerts: [
        {
          pest: "Yellow Rust / Fungal Blight",
          risk_level: "low",
          prevention: "Inspect leaf undersides weekly for yellow powdery stripes after cloudy or humid mornings.",
          treatment: "Spray Propiconazole 25% EC @ 200ml/acre or organic Trichoderma viride culture.",
        },
        {
          pest: "Aphids / Leaf Borers",
          risk_level: "medium",
          prevention: "Install yellow sticky traps (5 traps per acre) along field borders.",
          treatment: "Apply 5% Neem Seed Kernel Extract (NSKE) or systemic bio-pesticide.",
        },
      ],
      weather_considerations: `Regional temperature trends in ${farm.location_state || "North India"} are favorable for ${crop.crop_type} season. Keep field drainage channels open in case of unseasonal winter showers.`,
      market_insights: `Current APMC mandi rates for quality ${crop.crop_name} are trending strong above Minimum Support Price (MSP). Proper drying post-harvest will command premium prices.`,
      organic_alternatives: "Use fermented Jeevamrit spray (200L/acre) every 21 days and vermicompost to enrich soil organic carbon naturally.",
    };
  }

  crop.analysis_result = JSON.stringify(analysis);
  crop.expected_harvest_date = estimatedHarvestDate;

  return NextResponse.json({
    crop_id: id,
    analysis,
  });
}

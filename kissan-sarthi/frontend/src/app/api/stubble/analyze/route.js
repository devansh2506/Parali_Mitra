import { NextResponse } from "next/server";
import { store } from "@/lib/serverStore";

export async function POST(request) {
  try {
    const body = await request.json();
    const area = Number(body.stubble_area_acres) || 1;
    const cropId = body.crop_id;

    const crop = store.crops.find((c) => c.id === cropId) || {
      crop_name: "Wheat",
      farm_id: "farm-punjab-01",
    };
    const farm = store.farms.find((f) => f.id === crop.farm_id) || {
      name: "Green Valley Farm",
    };

    const isWheat = crop.crop_name.toLowerCase().includes("wheat");
    const co2PerAcre = isWheat ? 1780 : 2225;
    const pm25PerAcre = isWheat ? 5.6 : 7.0;

    const co2Kg = Math.round(co2PerAcre * area);
    const pm25Kg = Math.round(pm25PerAcre * area);
    const pm10Kg = Math.round(pm25Kg * 1.35);
    const trees = Math.round(co2Kg / 22);

    const result = {
      id: "stubble-" + Math.random().toString(36).substring(2, 9),
      crop_id: cropId,
      crop_name: crop.crop_name,
      farm_name: farm.name,
      stubble_area_acres: area,
      analysis: {
        pollution_if_burned: {
          co2_kg: co2Kg,
          pm25_kg: pm25Kg,
          pm10_kg: pm10Kg,
          methane_kg: Math.round(area * 3.5),
          black_carbon_kg: Math.round(area * 1.8),
          equivalent_trees_needed: trees,
          health_impact_description: `Burning ${area} acres releases toxic particulate smog causing severe respiratory distress and destroys topsoil biology.`,
        },
        eco_alternatives: [
          {
            method: "Pusa Bio-Decomposer Microbial Spray",
            description: "ICAR-developed capsule & liquid spray that converts crop stubble into rich organic manure directly inside the field in 20-25 days.",
            benefits: ["Increases soil organic carbon (SOC) by 0.3%", "Eliminates need for any burning", "Low cost and easy application"],
            estimated_cost: "₹300 - ₹500 per acre",
            estimated_revenue: "Saves ₹2,500 in chemical fertilizer costs",
            difficulty: "easy",
            time_required: "20-25 days",
            government_schemes: ["Free demonstration & spraying by State Agriculture Departments"],
          },
          {
            method: "In-Situ Mulching with Happy Seeder / Super SMS",
            description: "Direct sowing of the next crop into standing stubble without tilling. Stubble acts as moisture-retaining protective mulch.",
            benefits: ["Saves 15-20 days between harvest and sowing", "Saves ₹1,800/acre in tractor diesel", "Suppresses winter weeds"],
            estimated_cost: "₹1,200 - ₹1,500 per acre (custom hiring)",
            estimated_revenue: "Increases next crop yield by 1.5 - 2 quintals/acre",
            difficulty: "easy",
            time_required: "Direct single pass",
            government_schemes: ["50% subsidy on individual machines, 80% for Custom Hiring Centers"],
          },
          {
            method: "Commercial Bio-Pellets & Power Plant Supply",
            description: "Baling crop straw and supplying to thermal power plants for green co-firing power generation under Central Govt mandates.",
            benefits: ["Direct cash income from waste", "Completely clears field for next crop", "Zero air pollution"],
            estimated_cost: "₹800/acre baling cost",
            estimated_revenue: "₹1,500 to ₹2,200 per ton (₹3,500 - ₹5,000/acre)",
            difficulty: "medium",
            time_required: "3-5 days",
            government_schemes: ["Govt 5% Biomass Co-firing Mandate in coal power plants"],
          },
          {
            method: "Paddy Straw Mushroom Cultivation",
            description: "Using crop straw bundles to grow oyster and paddy straw mushrooms yielding cash harvest in 15-20 days.",
            benefits: ["High-value cash return", "Requires small shed/indoor space", "Spent straw becomes premium compost"],
            estimated_cost: "₹2,000 per 50 straw bundles",
            estimated_revenue: "₹15,000 to ₹25,000 profit per cycle",
            difficulty: "medium",
            time_required: "15-20 days",
            government_schemes: ["National Horticulture Mission mushroom subsidy"],
          },
          {
            method: "Cattle Fodder Enrichment & Silage",
            description: "Urea-molasses enrichment of straw to increase protein content from 3.5% to 7.5% for dairy cattle.",
            benefits: ["Overcomes dry fodder scarcity", "Boosts daily milk yield", "Saves purchase of expensive market fodder"],
            estimated_cost: "₹400 per quintal treated",
            estimated_revenue: "Saves ₹6,000 in fodder costs per milch animal",
            difficulty: "easy",
            time_required: "21 days curing",
            government_schemes: ["National Livestock Mission"],
          },
        ],
      },
      created_at: new Date().toISOString(),
    };

    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json({ detail: err.message || "Failed to analyze stubble" }, { status: 500 });
  }
}

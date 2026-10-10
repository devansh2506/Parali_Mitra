import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    crops: [
      { name: "Wheat", name_hi: "गेहूं", type: "Rabi", duration_days: "120-150", icon: "🌾" },
      { name: "Rice", name_hi: "चावल", type: "Kharif", duration_days: "90-150", icon: "🍚" },
      { name: "Sugarcane", name_hi: "गन्ना", type: "Perennial", duration_days: "300-365", icon: "🎋" },
      { name: "Cotton", name_hi: "कपास", type: "Kharif", duration_days: "150-180", icon: "☁️" },
      { name: "Mustard", name_hi: "सरसों", type: "Rabi", duration_days: "110-140", icon: "🌻" },
      { name: "Maize", name_hi: "मक्का", type: "Kharif", duration_days: "80-110", icon: "🌽" },
      { name: "Potato", name_hi: "आलू", type: "Rabi", duration_days: "75-120", icon: "🥔" },
      { name: "Tomato", name_hi: "टमाटर", type: "Rabi", duration_days: "60-80", icon: "🍅" },
      { name: "Onion", name_hi: "प्याज", type: "Rabi", duration_days: "120-150", icon: "🧅" },
      { name: "Soybean", name_hi: "सोयाबीन", type: "Kharif", duration_days: "90-120", icon: "🫘" },
      { name: "Groundnut", name_hi: "मूंगफली", type: "Kharif", duration_days: "100-130", icon: "🥜" },
      { name: "Chickpea", name_hi: "चना", type: "Rabi", duration_days: "90-120", icon: "🫘" },
      { name: "Turmeric", name_hi: "हल्दी", type: "Kharif", duration_days: "240-300", icon: "🟡" },
      { name: "Bajra", name_hi: "बाजरा", type: "Kharif", duration_days: "70-90", icon: "🌾" },
      { name: "Jowar", name_hi: "ज्वार", type: "Kharif", duration_days: "90-120", icon: "🌾" },
      { name: "Barley", name_hi: "जौ", type: "Rabi", duration_days: "110-130", icon: "🌾" },
      { name: "Lentil", name_hi: "मसूर", type: "Rabi", duration_days: "90-120", icon: "🫘" },
      { name: "Green Gram", name_hi: "मूंग", type: "Kharif", duration_days: "60-75", icon: "🫛" },
      { name: "Black Gram", name_hi: "उड़द", type: "Kharif", duration_days: "75-90", icon: "🫘" },
      { name: "Pigeon Pea", name_hi: "अरहर/तूर", type: "Kharif", duration_days: "150-270", icon: "🫛" },
    ],
  });
}

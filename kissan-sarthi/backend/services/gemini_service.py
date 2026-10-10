"""
Kissan Sarthi — Gemini AI Service
Central wrapper for all Google Gemini API interactions.
Handles text generation, multimodal (image+text), and structured output.
"""

import json
import traceback
from typing import Optional
from pathlib import Path

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL


class GeminiService:
    """Singleton-like service for Gemini AI interactions."""

    def __init__(self):
        self.available = bool(GEMINI_API_KEY)
        if self.available:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            self.model = GEMINI_MODEL
            print(f"✅ Gemini AI initialized with model: {self.model}")
        else:
            self.client = None
            self.model = None
            print("⚠️  Gemini API key not set. AI features will use fallback data.")

    async def analyze_crop(self, farm_data: dict, crop_data: dict) -> dict:
        """
        Analyze crop based on farm and crop context.
        Returns structured JSON with analysis results.
        """
        if not self.available:
            return self._fallback_crop_analysis(crop_data)

        prompt = f"""You are an expert Indian agricultural advisor (Krishi Vaigyanik).

FARM DETAILS:
- Location: {farm_data.get('location_state', 'Unknown')}, {farm_data.get('location_district', 'Unknown')}
- Soil Type: {farm_data.get('soil_type', 'Unknown')}
- Irrigation: {farm_data.get('irrigation_type', 'Unknown')}
- Total Farm Area: {farm_data.get('total_area_acres', 'Unknown')} acres

CROP DETAILS:
- Crop: {crop_data.get('crop_name', 'Unknown')} ({crop_data.get('variety', 'Standard')})
- Season: {crop_data.get('crop_type', 'Unknown')}
- Area Under Crop: {crop_data.get('area_acres', 'Unknown')} acres
- Sowing Date: {crop_data.get('sowing_date', 'Unknown')}
- Current Stage: {crop_data.get('current_stage', 'Unknown')}
- Fertilizers Used: {crop_data.get('fertilizers_used', '[]')}
- Pesticides Used: {crop_data.get('pesticides_used', '[]')}

Provide a comprehensive agricultural analysis. Respond ONLY with valid JSON in this exact format:
{{
  "crop_health_overview": "A brief paragraph about overall crop health and expectations",
  "growth_stage_assessment": "Assessment of current growth stage and what to expect next",
  "estimated_harvest_date": "YYYY-MM-DD format estimated harvest date",
  "estimated_yield_per_acre": "Yield in quintals per acre",
  "care_instructions": [
    {{"stage": "Current stage name", "task": "What to do", "timing": "When to do it", "details": "Detailed instructions"}}
  ],
  "fertilizer_schedule": [
    {{"week": 1, "fertilizer": "Name", "quantity_per_acre": "Amount", "method": "Application method"}}
  ],
  "pest_risk_alerts": [
    {{"pest": "Pest name", "risk_level": "low or medium or high", "prevention": "How to prevent", "treatment": "How to treat"}}
  ],
  "weather_considerations": "Weather-related advice for the region and season",
  "market_insights": "Current market trends and pricing advice",
  "organic_alternatives": "Eco-friendly and organic farming suggestions"
}}"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"❌ Gemini crop analysis error: {traceback.format_exc()}")
            return self._fallback_crop_analysis(crop_data)

    async def diagnose_health(self, image_path: str, context: dict) -> dict:
        """
        Analyze a crop image for disease/pest diagnosis.
        Uses multimodal input (image + text context).
        """
        if not self.available:
            return self._fallback_health_diagnosis(context)

        prompt = f"""You are an expert plant pathologist specializing in Indian agriculture.

CONTEXT:
- Crop: {context.get('crop_name', 'Unknown')} ({context.get('variety', 'Standard')})
- Location: {context.get('location_state', 'Unknown')}, {context.get('location_district', 'Unknown')}
- Current Growth Stage: {context.get('current_stage', 'Unknown')}
- Farmer-Reported Symptoms: {context.get('symptoms', 'None reported')}

Analyze the attached crop image and provide a detailed diagnosis. Respond ONLY with valid JSON:
{{
  "identified_issue": "Brief name of the identified issue",
  "disease_or_pest_name": "Common name of disease/pest",
  "scientific_name": "Scientific name if applicable",
  "severity": "low or medium or high or critical",
  "confidence": 0.85,
  "affected_parts": ["leaves", "stem"],
  "causes": ["Cause 1", "Cause 2"],
  "immediate_actions": ["Action 1", "Action 2"],
  "treatment_plan": {{
    "organic": ["Organic treatment 1", "Organic treatment 2"],
    "chemical": [{{"product": "Product name", "dosage": "Dosage info", "frequency": "How often"}}],
    "cultural": ["Cultural practice 1", "Cultural practice 2"]
  }},
  "prevention_tips": ["Prevention tip 1", "Prevention tip 2"],
  "when_to_seek_expert": "When to consult an agricultural officer",
  "nearby_kisan_call_center": "1800-180-1551"
}}"""

        try:
            # Read image file
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                return self._fallback_health_diagnosis(context)

            image_bytes = image_path_obj.read_bytes()
            mime_type = "image/jpeg"
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"

            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"❌ Gemini health diagnosis error: {traceback.format_exc()}")
            return self._fallback_health_diagnosis(context)

    async def analyze_stubble(self, crop_data: dict, area: float) -> dict:
        """
        Calculate environmental impact of stubble and suggest alternatives.
        """
        if not self.available:
            return self._fallback_stubble_analysis(crop_data, area)

        prompt = f"""You are an environmental sustainability expert focused on Indian agriculture and stubble burning prevention.

CONTEXT:
- Crop Harvested: {crop_data.get('crop_name', 'Unknown')}
- Area: {area} acres
- Location: {crop_data.get('location_state', 'Unknown')}, {crop_data.get('location_district', 'Unknown')}
- Season: {crop_data.get('crop_type', 'Unknown')}

The farmer has just harvested their crop. Calculate the environmental impact
of NOT burning the crop stubble and provide eco-friendly alternatives.

Respond ONLY with valid JSON:
{{
  "pollution_if_burned": {{
    "co2_kg": 2225,
    "pm25_kg": 7.0,
    "pm10_kg": 10.5,
    "methane_kg": 3.0,
    "black_carbon_kg": 0.56,
    "equivalent_trees_needed": 37,
    "health_impact_description": "Description of health impacts from burning"
  }},
  "eco_alternatives": [
    {{
      "method": "Alternative method name",
      "description": "Brief description",
      "benefits": ["Benefit 1", "Benefit 2"],
      "estimated_cost": "₹X,XXX",
      "estimated_revenue": "₹X,XXX",
      "difficulty": "easy or medium or hard",
      "time_required": "X weeks/months",
      "steps": ["Step 1", "Step 2", "Step 3"],
      "government_schemes": ["Scheme 1", "Scheme 2"]
    }}
  ],
  "government_subsidies": [
    {{"scheme_name": "Scheme", "benefit": "What you get", "how_to_apply": "Steps to apply"}}
  ],
  "success_stories": "A brief motivational success story from Indian farmers",
  "motivational_message": "An encouraging message in simple Hindi/English for the farmer"
}}"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"❌ Gemini stubble analysis error: {traceback.format_exc()}")
            return self._fallback_stubble_analysis(crop_data, area)

    # ── Fallback Methods (used when Gemini is unavailable) ──

    def _fallback_crop_analysis(self, crop_data: dict) -> dict:
        """Static fallback when AI is unavailable."""
        return {
            "crop_health_overview": f"General care guide for {crop_data.get('crop_name', 'your crop')}. For detailed AI-powered analysis, please configure your Gemini API key.",
            "growth_stage_assessment": "Unable to assess — AI service unavailable. Please ensure regular monitoring.",
            "estimated_harvest_date": crop_data.get("expected_harvest_date", "Unknown"),
            "estimated_yield_per_acre": "Varies by region and variety",
            "care_instructions": [
                {"stage": "General", "task": "Regular watering", "timing": "Daily/as needed", "details": "Maintain consistent soil moisture"},
                {"stage": "General", "task": "Weed management", "timing": "Weekly", "details": "Remove weeds to reduce competition"},
            ],
            "fertilizer_schedule": [
                {"week": 1, "fertilizer": "DAP", "quantity_per_acre": "50 kg", "method": "Basal application"},
            ],
            "pest_risk_alerts": [
                {"pest": "Common pests", "risk_level": "medium", "prevention": "Regular field inspection", "treatment": "Consult local agriculture officer"},
            ],
            "weather_considerations": "Monitor local weather forecasts. Protect crops during extreme conditions.",
            "market_insights": "Check local mandi prices before harvest. Connect with FPOs for better rates.",
            "organic_alternatives": "Consider neem-based pesticides and vermicompost for sustainable farming.",
            "_ai_status": "fallback"
        }

    def _fallback_health_diagnosis(self, context: dict) -> dict:
        """Static fallback for health diagnosis."""
        return {
            "identified_issue": "AI analysis unavailable",
            "disease_or_pest_name": "Unable to diagnose — please consult a local agricultural expert",
            "scientific_name": "N/A",
            "severity": "medium",
            "confidence": 0,
            "affected_parts": [],
            "causes": ["Unable to determine without AI analysis"],
            "immediate_actions": [
                "Take clear photos of affected parts",
                "Note symptoms and progression",
                "Contact your local Krishi Vigyan Kendra (KVK)",
                "Call Kisan Call Center: 1800-180-1551"
            ],
            "treatment_plan": {
                "organic": ["Neem oil spray as general treatment"],
                "chemical": [{"product": "Consult local expert", "dosage": "As prescribed", "frequency": "As needed"}],
                "cultural": ["Ensure proper drainage", "Remove infected plant parts"]
            },
            "prevention_tips": ["Regular field monitoring", "Crop rotation", "Balanced fertilization"],
            "when_to_seek_expert": "Immediately if symptoms worsen",
            "nearby_kisan_call_center": "1800-180-1551",
            "_ai_status": "fallback"
        }

    def _fallback_stubble_analysis(self, crop_data: dict, area: float) -> dict:
        """Static fallback using IARI reference values."""
        crop_name = crop_data.get("crop_name", "").lower()
        # Use rice straw values as default, wheat if detected
        is_wheat = "wheat" in crop_name or "गेहूं" in crop_name
        co2_per_acre = 1780 if is_wheat else 2225
        pm25_per_acre = 5.6 if is_wheat else 7.0
        pm10_per_acre = 8.4 if is_wheat else 10.5

        return {
            "pollution_if_burned": {
                "co2_kg": round(co2_per_acre * area, 1),
                "pm25_kg": round(pm25_per_acre * area, 1),
                "pm10_kg": round(pm10_per_acre * area, 1),
                "methane_kg": round(3.0 * area, 1),
                "black_carbon_kg": round(0.56 * area, 2),
                "equivalent_trees_needed": round((co2_per_acre * area) / 60),
                "health_impact_description": "Stubble burning causes severe respiratory issues, eye irritation, and contributes to hazardous smog in north India."
            },
            "eco_alternatives": [
                {
                    "method": "Mulching with Happy Seeder",
                    "description": "Use a Happy Seeder machine to sow wheat directly into rice stubble without burning.",
                    "benefits": ["Saves plowing cost", "Improves soil health", "No air pollution"],
                    "estimated_cost": "₹800-1,200/acre (machine rental)",
                    "estimated_revenue": "Saves ₹2,000-3,000/acre in tillage costs",
                    "difficulty": "easy",
                    "time_required": "Same as normal sowing",
                    "steps": ["Contact Custom Hiring Center", "Book Happy Seeder", "Sow directly into stubble"],
                    "government_schemes": ["CRM Scheme - 50% subsidy on machinery"]
                },
                {
                    "method": "Composting",
                    "description": "Convert stubble into nutrient-rich compost for future crops.",
                    "benefits": ["Free organic fertilizer", "Improves soil health", "Reduces chemical fertilizer costs"],
                    "estimated_cost": "₹500-1,000/acre",
                    "estimated_revenue": "₹2,000-5,000/acre in fertilizer savings",
                    "difficulty": "easy",
                    "time_required": "3-4 months",
                    "steps": ["Chop stubble", "Mix with cow dung and water", "Pile and cover", "Turn every 2 weeks"],
                    "government_schemes": ["GOBAR-DHAN scheme"]
                },
                {
                    "method": "Mushroom Cultivation",
                    "description": "Use paddy straw as substrate for growing oyster mushrooms.",
                    "benefits": ["High income potential", "Growing market demand", "Uses waste productively"],
                    "estimated_cost": "₹5,000-10,000 initial setup",
                    "estimated_revenue": "₹10,000-30,000/acre of straw",
                    "difficulty": "medium",
                    "time_required": "2-3 months per cycle",
                    "steps": ["Collect and chop straw", "Sterilize substrate", "Inoculate with spawn", "Maintain humidity and temperature"],
                    "government_schemes": ["PMFME - 35% subsidy for food processing"]
                },
            ],
            "government_subsidies": [
                {"scheme_name": "Crop Residue Management (CRM)", "benefit": "50-80% subsidy on machinery", "how_to_apply": "Apply through District Agriculture Office or CHC"},
                {"scheme_name": "GOBAR-DHAN", "benefit": "Financial support for biogas/compost", "how_to_apply": "Contact Block Development Office"},
            ],
            "success_stories": "Farmers in Karnal, Haryana have earned ₹25,000/acre extra income by converting rice straw into mushroom substrate, while keeping the air clean for their families.",
            "motivational_message": "आपका एक कदम लाखों लोगों को स्वच्छ हवा दे सकता है। पराली न जलाएं, विकल्प अपनाएं! 🌱",
            "_ai_status": "fallback"
        }


# Global instance
gemini_service = GeminiService()

/* Reference lists for the farmer screens, in English (en) and Hindi (hi). General guidance only, not a diagnosis or a
   prescription: costs, subsidies and doses change by state and season, so the screens tell farmers to confirm with the
   local Krishi Vigyan Kendra (KVK) or the Kisan Call Centre, 1800-180-1551. Crop names and durations are from the
   Kissan Sarthi project; the three chemical doses are the usual label doses. */
window.PM_FARM = {
  callCentre: "1800-180-1551",
  states: ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu & Kashmir", "Ladakh",
    "Puducherry", "Chandigarh"],
  soils: [
    { id: "alluvial", en: "Alluvial soil", hi: "जलोढ़ मिट्टी" }, { id: "black", en: "Black soil", hi: "काली मिट्टी" },
    { id: "red", en: "Red soil", hi: "लाल मिट्टी" }, { id: "laterite", en: "Laterite soil", hi: "लैटेराइट मिट्टी" },
    { id: "desert", en: "Desert or dry soil", hi: "मरुस्थली मिट्टी" }, { id: "mountain", en: "Mountain soil", hi: "पर्वतीय मिट्टी" },
    { id: "peaty", en: "Marshy soil", hi: "दलदली मिट्टी" }, { id: "saline", en: "Saline soil", hi: "लवणीय मिट्टी" },
  ],
  irrigation: [
    { id: "tubewell", en: "Tube well or borewell", hi: "ट्यूबवेल / बोरवेल" }, { id: "canal", en: "Canal", hi: "नहर" },
    { id: "drip", en: "Drip", hi: "ड्रिप" }, { id: "sprinkler", en: "Sprinkler", hi: "फव्वारा" },
    { id: "pond", en: "Pond or river", hi: "तालाब या नदी" }, { id: "rainfed", en: "Rain only", hi: "सिर्फ़ बारिश" },
  ],
  // season: rabi / kharif / year (perennial); days = usual sowing-to-harvest range
  crops: [
    { id: "wheat", en: "Wheat", hi: "गेहूं", season: "rabi", min: 120, max: 150 }, { id: "rice", en: "Rice (paddy)", hi: "चावल (धान)", season: "kharif", min: 90, max: 150 },
    { id: "sugarcane", en: "Sugarcane", hi: "गन्ना", season: "year", min: 300, max: 365 }, { id: "cotton", en: "Cotton", hi: "कपास", season: "kharif", min: 150, max: 180 },
    { id: "mustard", en: "Mustard", hi: "सरसों", season: "rabi", min: 110, max: 140 }, { id: "maize", en: "Maize", hi: "मक्का", season: "kharif", min: 80, max: 110 },
    { id: "potato", en: "Potato", hi: "आलू", season: "rabi", min: 75, max: 120 }, { id: "tomato", en: "Tomato", hi: "टमाटर", season: "rabi", min: 60, max: 80 },
    { id: "onion", en: "Onion", hi: "प्याज", season: "rabi", min: 120, max: 150 }, { id: "soybean", en: "Soybean", hi: "सोयाबीन", season: "kharif", min: 90, max: 120 },
    { id: "groundnut", en: "Groundnut", hi: "मूंगफली", season: "kharif", min: 100, max: 130 }, { id: "chickpea", en: "Chickpea", hi: "चना", season: "rabi", min: 90, max: 120 },
    { id: "turmeric", en: "Turmeric", hi: "हल्दी", season: "kharif", min: 240, max: 300 }, { id: "bajra", en: "Pearl millet (bajra)", hi: "बाजरा", season: "kharif", min: 70, max: 90 },
    { id: "jowar", en: "Sorghum (jowar)", hi: "ज्वार", season: "kharif", min: 90, max: 120 }, { id: "barley", en: "Barley", hi: "जौ", season: "rabi", min: 110, max: 130 },
    { id: "lentil", en: "Lentil", hi: "मसूर", season: "rabi", min: 90, max: 120 }, { id: "moong", en: "Green gram (moong)", hi: "मूंग", season: "kharif", min: 60, max: 75 },
    { id: "urad", en: "Black gram (urad)", hi: "उड़द", season: "kharif", min: 75, max: 90 }, { id: "arhar", en: "Pigeon pea (arhar)", hi: "अरहर / तूर", season: "kharif", min: 150, max: 270 },
  ],

  // What to do at each stage of a crop's life (the share of the way from sowing to harvest). General, not crop-specific.
  stages: [
    { id: "sowing", upto: 0.12, en: "Germination", hi: "अंकुरण", tasks: {
      en: ["Keep the soil moist, not waterlogged, so seeds come up evenly.", "Check the field after a week and re-sow any bare patches.", "Protect seedlings from birds and ants."],
      hi: ["मिट्टी में नमी रखें, पानी भरने न दें, ताकि बीज बराबर उगें।", "एक हफ़्ते बाद खेत देखें और खाली जगहों पर दोबारा बुवाई करें।", "अंकुरों को चिड़ियों और चींटियों से बचाएँ।"] } },
    { id: "vegetative", upto: 0.4, en: "Growing leaves and shoots", hi: "पत्तियों और कल्लों की बढ़वार", tasks: {
      en: ["Weed the field once or twice before the plants close the gaps.", "Give the first top-dressing of nitrogen fertiliser as advised for your soil test, followed by light irrigation.", "Walk the field every week and look under the leaves for insects and spots."],
      hi: ["पौधों के बीच की जगह भरने से पहले एक-दो बार निराई करें।", "मिट्टी जाँच की सलाह के अनुसार नाइट्रोजन खाद की पहली खुराक दें, फिर हल्की सिंचाई करें।", "हर हफ़्ते खेत में घूमकर पत्तियों के नीचे कीड़े और धब्बे देखें।"] } },
    { id: "flowering", upto: 0.65, en: "Flowering", hi: "फूल आना", tasks: {
      en: ["Do not let the crop go dry now: flowering is when water stress costs the most yield.", "Avoid spraying in the heat of the day, to protect pollinating bees.", "Keep an eye out for fungal disease after cloudy, humid mornings."],
      hi: ["अब फसल को सूखने न दें: फूल के समय पानी की कमी से सबसे ज़्यादा उपज घटती है।", "दोपहर की गर्मी में छिड़काव न करें, ताकि परागण करने वाली मधुमक्खियाँ सुरक्षित रहें।", "बादल और नमी भरी सुबह के बाद फफूंद की बीमारी पर नज़र रखें।"] } },
    { id: "filling", upto: 0.9, en: "Grain or fruit filling", hi: "दाना या फल भरना", tasks: {
      en: ["Give the last irrigation as advised, then stop so the crop can ripen evenly.", "Watch for lodging (plants falling over) after wind and rain.", "Plan labour, machines and storage for harvest now."],
      hi: ["सलाह के अनुसार आख़िरी सिंचाई करें, फिर बंद करें ताकि फसल बराबर पके।", "हवा और बारिश के बाद पौधे गिरने (लॉजिंग) पर नज़र रखें।", "कटाई के लिए मज़दूर, मशीन और भंडारण की योजना अभी बना लें।"] } },
    { id: "harvest", upto: 1.0, en: "Ready to harvest", hi: "कटाई के लिए तैयार", tasks: {
      en: ["Harvest when the grain is dry and hard, in dry weather.", "Do not burn the stalks. See the Stubble page for ways to earn from them or put them back in the soil.", "Dry the produce well before storing or selling: it fetches a better price."],
      hi: ["सूखे मौसम में, जब दाना सूखा और सख़्त हो, तब कटाई करें।", "डंठल न जलाएँ। इनसे कमाने या इन्हें मिट्टी में मिलाने के तरीके के लिए पराली वाला पन्ना देखें।", "भंडारण या बिक्री से पहले उपज को अच्छी तरह सुखाएँ: दाम बेहतर मिलता है।"] } },
  ],

  // Things a farmer can see in the field. The doctor matches ticked symptoms to the diseases below.
  symptoms: [
    { id: "yellow_stripes", en: "Yellow or orange stripes or powder on leaves", hi: "पत्तियों पर पीली या नारंगी धारियाँ या पाउडर" },
    { id: "white_powder", en: "White powdery patches on leaves", hi: "पत्तियों पर सफ़ेद पाउडर जैसे धब्बे" },
    { id: "holes_stem", en: "Holes in the stem, dried centre shoot, rot at the base", hi: "तने में छेद, बीच की कोंपल सूखना, जड़ के पास सड़न" },
    { id: "brown_spots", en: "Brown or black spots with a yellow ring", hi: "पीले घेरे वाले भूरे या काले धब्बे" },
    { id: "sticky_insects", en: "Tiny insects, sticky leaves, curled leaves", hi: "छोटे कीड़े, चिपचिपी या मुड़ी हुई पत्तियाँ" },
    { id: "wilting", en: "Wilting even after watering", hi: "पानी देने के बाद भी मुरझाना" },
    { id: "pale_leaves", en: "Whole plant pale yellow and stunted", hi: "पूरा पौधा हल्का पीला और छोटा रह जाना" },
  ],
  diseases: [
    { id: "rust", symptoms: ["yellow_stripes"], severity: "medium", name: { en: "Yellow rust (fungus)", hi: "पीला रतुआ (फफूंद)" },
      what: { en: "A fungus that makes yellow stripes on the leaf blades. It spreads fast in cool, cloudy, humid weather.", hi: "एक फफूंद जो पत्तियों पर पीली धारियाँ बनाती है। ठंडे, बादल वाले, नम मौसम में तेज़ी से फैलती है।" },
      organic: { en: ["Spray 5 % neem oil with a little soap.", "Mix Trichoderma bio-fungicide into compost and apply to the field."], hi: ["5 % नीम तेल में थोड़ा साबुन मिलाकर छिड़कें।", "ट्राइकोडर्मा जैव-फफूंदनाशक को कम्पोस्ट में मिलाकर खेत में डालें।"] },
      chemical: [{ product: "Propiconazole 25 % EC", dose: { en: "1 ml per litre of water", hi: "1 मिली प्रति लीटर पानी" }, freq: { en: "One spray; repeat after 15 days if the weather stays cloudy", hi: "एक छिड़काव; मौसम बादल वाला रहे तो 15 दिन बाद दोहराएँ" } }],
      cultural: { en: ["Bury or compost the worst leaves away from the field. Do not burn them.", "Avoid too much urea: it makes plants soft and easy to infect."], hi: ["सबसे ख़राब पत्तियाँ खेत से दूर गाड़ें या कम्पोस्ट करें (खेत में जलाएँ नहीं)।", "यूरिया ज़्यादा न दें: इससे पौधे नरम होकर जल्दी बीमार होते हैं।"] } },
    { id: "mildew", symptoms: ["white_powder"], severity: "medium", name: { en: "Powdery mildew (fungus)", hi: "चूर्णिल आसिता (फफूंद)" },
      what: { en: "White powder on the leaves, mostly on the lower ones, in cool dry days with humid nights.", hi: "पत्तियों पर सफ़ेद पाउडर, ज़्यादातर नीचे की पत्तियों पर, ठंडे सूखे दिनों और नम रातों में।" },
      organic: { en: ["Spray buttermilk (chhachh) mixed 1 part to 10 parts water.", "Dust fine sulphur in the cool morning hours."], hi: ["छाछ को 1 हिस्सा और पानी 10 हिस्से मिलाकर छिड़कें।", "ठंडी सुबह में बारीक गंधक का बुरकाव करें।"] },
      chemical: [{ product: "Wettable sulphur 80 % WP", dose: { en: "2 g per litre of water", hi: "2 ग्राम प्रति लीटर पानी" }, freq: { en: "Every 12 to 14 days", hi: "हर 12 से 14 दिन में" } }],
      cultural: { en: ["Give plants space and airflow.", "Water in the morning, not the evening."], hi: ["पौधों के बीच जगह और हवा रखें।", "सिंचाई शाम को नहीं, सुबह करें।"] } },
    { id: "borer", symptoms: ["holes_stem", "wilting"], severity: "high", name: { en: "Stem borer or foot rot", hi: "तना छेदक या जड़ सड़न" },
      what: { en: "Grubs bore into the stem, or the base rots, so water and food cannot reach the top. Dried centre shoots are the usual sign.", hi: "इल्लियाँ तने में छेद करती हैं या जड़ के पास सड़न होती है, जिससे ऊपर पानी और खुराक नहीं पहुँचती। बीच की कोंपल सूखना आम निशानी है।" },
      organic: { en: ["Put up pheromone traps, about 4 per acre.", "Release Trichogramma egg parasites, about 20,000 per acre."], hi: ["फेरोमोन ट्रैप लगाएँ, लगभग 4 प्रति एकड़।", "ट्राइकोग्रामा परजीवी छोड़ें, लगभग 20,000 प्रति एकड़।"] },
      chemical: [{ product: "Chlorantraniliprole 18.5 % SC", dose: { en: "0.4 ml per litre of water", hi: "0.4 मिली प्रति लीटर पानी" }, freq: { en: "Spray in the evening", hi: "शाम को छिड़काव करें" } }],
      cultural: { en: ["Pull out and bury the dried shoots.", "Keep water from standing at the base of the plants."], hi: ["सूखी कोंपलें उखाड़कर गाड़ दें।", "पौधों की जड़ के पास पानी जमा न होने दें।"] } },
    { id: "blight", symptoms: ["brown_spots"], severity: "medium", name: { en: "Leaf spot or blight", hi: "पत्ती धब्बा या झुलसा" },
      what: { en: "Fungus or bacteria cause brown or black spots that join up and dry the leaf. It grows with leaf wetness.", hi: "फफूंद या जीवाणु भूरे-काले धब्बे बनाते हैं जो जुड़कर पत्ती सुखा देते हैं। पत्तियों के गीले रहने से बढ़ता है।" },
      organic: { en: ["Spray 5 % neem oil.", "Remove badly spotted leaves and compost them away from the field."], hi: ["5 % नीम तेल छिड़कें।", "ज़्यादा धब्बे वाली पत्तियाँ हटाकर खेत से दूर कम्पोस्ट करें।"] },
      chemical: [],
      cultural: { en: ["Do not water overhead in the evening.", "Rotate crops next season."], hi: ["शाम को ऊपर से पानी न दें।", "अगले मौसम में फसल बदलें।"] } },
    { id: "aphid", symptoms: ["sticky_insects"], severity: "low", name: { en: "Aphids or whitefly (sap-sucking insects)", hi: "माहू या सफ़ेद मक्खी (रस चूसने वाले कीड़े)" },
      what: { en: "Tiny insects suck sap, curl the leaves and leave a sticky film that grows black mould.", hi: "छोटे कीड़े रस चूसते हैं, पत्तियाँ मोड़ देते हैं और चिपचिपी परत छोड़ते हैं जिस पर काली फफूंद उगती है।" },
      organic: { en: ["Spray 5 % neem seed kernel extract.", "Hang yellow sticky traps, about 5 per acre, along the edges."], hi: ["5 % नीम बीज अर्क का छिड़काव करें।", "किनारों पर पीले चिपचिपे ट्रैप लगाएँ, लगभग 5 प्रति एकड़।"] },
      chemical: [],
      cultural: { en: ["Keep bunds free of weeds where insects hide.", "Protect ladybirds and other helpful insects: avoid broad sprays."], hi: ["मेड़ों से खरपतवार हटाएँ जहाँ कीड़े छिपते हैं।", "लेडीबर्ड जैसे मित्र कीड़ों को बचाएँ: हर तरह के कीड़े मारने वाला छिड़काव न करें।"] } },
    { id: "deficiency", symptoms: ["pale_leaves", "wilting"], severity: "low", name: { en: "Hunger for nutrients (for example nitrogen or zinc)", hi: "पोषक तत्वों की कमी (जैसे नाइट्रोजन या ज़िंक)" },
      what: { en: "The whole plant turns pale and stays small when the soil lacks food, or when roots sit in too much water.", hi: "मिट्टी में खुराक कम हो या जड़ें ज़्यादा पानी में रहें, तो पूरा पौधा पीला पड़ता और छोटा रह जाता है।" },
      organic: { en: ["Spray fermented jeevamrit and add vermicompost.", "Add well-rotted farmyard manure before the next crop."], hi: ["जीवामृत का छिड़काव करें और वर्मीकम्पोस्ट डालें।", "अगली फसल से पहले अच्छी सड़ी गोबर की खाद डालें।"] },
      chemical: [],
      cultural: { en: ["Get a soil test and follow its dose. Your KVK can help.", "Drain the field if water is standing."], hi: ["मिट्टी की जाँच कराएँ और उसकी खुराक मानें। KVK मदद कर सकता है।", "पानी खड़ा हो तो खेत से निकालें।"] } },
  ],

  // Ways to use crop straw without burning it. Money figures are indicative, from the Kissan Sarthi project.
  alternatives: [
    { id: "decomposer", en: "Pusa bio-decomposer spray", hi: "पूसा बायो-डीकंपोज़र का छिड़काव",
      what: { en: "A microbe spray from ICAR that turns the stubble into manure inside the field in about 20 to 25 days.", hi: "ICAR का सूक्ष्मजीव घोल जो लगभग 20-25 दिन में खेत में ही पराली को खाद बना देता है।" },
      cost: { en: "₹300 to ₹500 per acre", hi: "₹300 से ₹500 प्रति एकड़" }, gain: { en: "Saves about ₹2,500 of fertiliser", hi: "लगभग ₹2,500 की खाद की बचत" },
      effort: "easy", time: { en: "20 to 25 days", hi: "20 से 25 दिन" },
      scheme: { en: "Free demonstration and spraying by many state agriculture departments", hi: "कई राज्यों के कृषि विभाग मुफ़्त प्रदर्शन और छिड़काव करते हैं" } },
    { id: "seeder", en: "Sow straight through the straw (Happy Seeder)", hi: "पराली में ही सीधी बुवाई (हैप्पी सीडर)",
      what: { en: "The next crop is sown directly into the standing stubble without ploughing. The straw works as a moisture-keeping mulch.", hi: "अगली फसल बिना जुताई सीधे खड़ी पराली में बोई जाती है। पराली नमी बचाने वाली परत का काम करती है।" },
      cost: { en: "₹1,200 to ₹1,500 per acre (hired machine)", hi: "₹1,200 से ₹1,500 प्रति एकड़ (किराये की मशीन)" }, gain: { en: "Saves 15 to 20 days and about ₹1,800 of diesel; may raise yield", hi: "15-20 दिन और लगभग ₹1,800 का डीज़ल बचता है; उपज बढ़ सकती है" },
      effort: "easy", time: { en: "One pass", hi: "एक बार में" },
      scheme: { en: "Subsidy on machines and on custom hiring centres (the share differs by state)", hi: "मशीनों और कस्टम हायरिंग सेंटर पर सब्सिडी (हिस्सा राज्य के अनुसार अलग)" } },
    { id: "pellets", en: "Sell straw for bio-pellets and power plants", hi: "पराली बेचें: बायो-पेलेट और बिजली संयंत्र",
      what: { en: "Bale the straw and sell it to plants that co-fire biomass with coal.", hi: "पराली की गाँठें बनाकर उन संयंत्रों को बेचें जो कोयले के साथ बायोमास जलाते हैं।" },
      cost: { en: "About ₹800 per acre for baling", hi: "गाँठ बनाने का लगभग ₹800 प्रति एकड़" }, gain: { en: "About ₹1,500 to ₹2,200 per tonne", hi: "लगभग ₹1,500 से ₹2,200 प्रति टन" },
      effort: "medium", time: { en: "3 to 5 days", hi: "3 से 5 दिन" },
      scheme: { en: "Government biomass co-firing target for coal power plants", hi: "कोयला संयंत्रों के लिए सरकार का बायोमास को-फ़ायरिंग लक्ष्य" } },
    { id: "mushroom", en: "Grow straw mushrooms", hi: "पराली पर मशरूम उगाएँ",
      what: { en: "Straw bundles grow oyster and paddy-straw mushrooms in 15 to 20 days. The used straw becomes compost.", hi: "पराली की गठरियों पर 15-20 दिन में ऑयस्टर और पैडी-स्ट्रॉ मशरूम उगते हैं। इस्तेमाल के बाद पराली खाद बन जाती है।" },
      cost: { en: "About ₹2,000 per 50 bundles", hi: "लगभग ₹2,000 प्रति 50 गठरी" }, gain: { en: "₹15,000 to ₹25,000 profit per cycle (indicative)", hi: "प्रति चक्र ₹15,000 से ₹25,000 मुनाफ़ा (अनुमानित)" },
      effort: "medium", time: { en: "15 to 20 days", hi: "15 से 20 दिन" },
      scheme: { en: "Horticulture mission support for mushroom growing", hi: "मशरूम उत्पादन के लिए बागवानी मिशन की सहायता" } },
    { id: "fodder", en: "Enrich straw as cattle fodder", hi: "पशु चारे के लिए पराली को पौष्टिक बनाएँ",
      what: { en: "Treating straw with urea and molasses raises its protein, so dairy animals eat it with benefit.", hi: "पराली को यूरिया और शीरे से उपचारित करने पर उसका प्रोटीन बढ़ता है, जिससे दुधारू पशुओं को फ़ायदा होता है।" },
      cost: { en: "About ₹400 per quintal treated", hi: "लगभग ₹400 प्रति क्विंटल उपचार" }, gain: { en: "Saves about ₹6,000 of fodder per milch animal", hi: "प्रति दुधारू पशु लगभग ₹6,000 के चारे की बचत" },
      effort: "easy", time: { en: "21 days of curing", hi: "21 दिन पकाना" },
      scheme: { en: "National Livestock Mission", hi: "राष्ट्रीय पशुधन मिशन" } },
  ],
};

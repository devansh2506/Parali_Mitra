/* What burning a field gives off: the same numbers as the server (src/smoke_path/emissions.py), so the farmer's
   calculator and the fire pages never disagree. Crop residue factors are GFED4.1 (van der Werf et al. 2017, mostly
   Akagi et al. 2011), grams per kg of dry matter; NOx is given as NO. The straw load (6.3 t per hectare) is the Punjab
   paddy figure used everywhere in the app, and 80 % of it is assumed to burn. For any other crop it is only a rough guide. */
(function (PM) {
  "use strict";
  var STRAW_T_PER_HA = 6.3, BURNED_FRACTION = 0.8, ACRE_HA = 0.404686, NO2_PER_NO = 46 / 30;
  var AGRI = { co2: 1585, co: 102, ch4: 5.82, pm2_5: 6.26, tpm: 12.4, oc: 2.3, bc: 0.75, nox: 3.11, so2: 0.40, nh3: 2.17, benzene: 0.15, toluene: 0.19, formaldehyde: 2.08 };
  var ORDER = ["pm2_5", "tpm", "bc", "oc", "co", "no2", "so2", "nh3", "benzene", "toluene", "formaldehyde", "ch4", "co2"];
  // Safe limits in µg/m³: CPCB national standards (24 h; CO 8 h; benzene annual); formaldehyde WHO 30-minute guideline.
  var LIMITS = { pm2_5: 60, no2: 80, so2: 80, co: 2000, nh3: 400, benzene: 5, formaldehyde: 100 };
  var LEVELS = [[0.5, "low"], [2.0, "moderate"], [5.0, "high"], [Infinity, "very_high"]];

  function round(x) { var p = x < 10 ? 100 : x < 1000 ? 10 : 1; return Math.round(x * p) / p; }
  function burnedKg(acres) { return acres * ACRE_HA * STRAW_T_PER_HA * BURNED_FRACTION * 1000; }

  /** What burning `acres` of crop residue gives off in total: {burnedKg, kg: {pm2_5: ...}, tox: {km3, level, worst, shares}}. */
  function fromField(acres) {
    var burned = burnedKg(acres), kg = {};
    Object.keys(AGRI).forEach(function (k) {
      if (k === "nox") kg.no2 = burned * AGRI[k] * NO2_PER_NO / 1000; else kg[k] = burned * AGRI[k] / 1000;
    });
    var parts = {}, total = 0;
    Object.keys(LIMITS).forEach(function (p) { if (kg[p]) { parts[p] = kg[p] / LIMITS[p]; total += parts[p]; } });
    var tox = null;
    if (total > 0) {
      var worst = Object.keys(parts).sort(function (a, b) { return parts[b] - parts[a]; })[0];
      var shares = {};
      Object.keys(parts).sort(function (a, b) { return parts[b] - parts[a]; }).forEach(function (p) { shares[p] = Math.round(100 * parts[p] / total); });
      tox = { km3: Math.round(total * 1000) / 1000, level: LEVELS.filter(function (l) { return total < l[0]; })[0][1], worst: worst, shares: shares };
    }
    var out = {};
    ORDER.forEach(function (k) { if (kg[k] != null) out[k] = round(kg[k]); });
    return { burned_kg: Math.round(burned), kg: out, toxicity: tox };
  }

  PM.emissions = { fromField: fromField, ORDER: ORDER, STRAW_T_PER_HA: STRAW_T_PER_HA, BURNED_FRACTION: BURNED_FRACTION };
})((window.PM = window.PM || {}));

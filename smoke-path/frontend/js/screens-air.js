/* Air quality: measured stations (now) and the 48 hour forecast. Used by both roles.
   Also the small helpers the citizen home uses: nearest station, forecast strip and headline. */
(function (PM) {
  "use strict";
  var U = PM.U, esc = U.esc, t = function (k, v) { return PM.t(k, v); };
  var Air = (PM.air = {});

  // ---- helpers ---------------------------------------------------------------------------------------------------
  Air.nearest = function (stations, lat, lon) {
    var best = null;
    (stations || []).forEach(function (s) {
      if (s.aqi == null) return;
      var d = U.distKm(lat, lon, s.lat, s.lon);
      if (!best || d < best.d) best = { s: s, d: d };
    });
    return best;
  };
  /** What the next hours hold: {now, worst, worstAt, trend: 'worse'|'better'|'same'}. outlook items need {ms, aqi}. */
  Air.headline = function (outlook, nowMs) {
    var future = outlook.filter(function (o) { return o.ms >= nowMs - 90 * 60000; }).slice(0, 56);
    if (!future.length) return null;
    var first = future[0], next24 = future.filter(function (o) { return o.ms <= nowMs + 24 * 3600000; });
    var worst = next24.reduce(function (m, o) { return o.aqi > m.aqi ? o : m; }, first);
    var best = next24.reduce(function (m, o) { return o.aqi < m.aqi ? o : m; }, first);
    var ck = function (n) { return U.AQI.map(function (c) { return c.key; }).indexOf(U.aqiKey(n)); };
    var trend = ck(worst.aqi) > ck(first.aqi) ? "worse" : ck(best.aqi) < ck(first.aqi) ? "better" : "same";
    return { now: first, worst: worst, best: best, trend: trend, future: future };
  };
  /** Bars for an outlook: height follows the AQI, colour is the official CPCB colour. */
  Air.strip = function (items, nowMs) {
    if (!items.length) return "";
    var bars = items.map(function (o) {
      var k = U.aqiKey(o.aqi), h = Math.max(6, Math.min(100, (o.aqi / 400) * 100));
      return '<div class="bar" style="height:' + h + "%;background:" + U.aqiColor(k) + '" title="' + esc(U.when(o.ms, nowMs) + " · AQI " + Math.round(o.aqi) + " · " + t("aqi." + k)) + '"></div>';
    }).join("");
    var first = items[0].ms, last = items[items.length - 1].ms, mid = items[Math.floor(items.length / 2)].ms;
    return '<div class="strip" role="img" aria-label="' + esc(t("air.strip_label")) + '">' + bars + '</div><div class="strip-axis"><span>' + esc(t("air.now_label")) + "</span><span>" + esc(U.when(mid, nowMs)) + "</span><span>" + esc(U.when(last, nowMs)) + "</span></div>";
  };
  /** The header and body of one station: AQI, category, main pollutant, age, every pollutant with its sub-index. */
  Air.stationHead = function (s, closeAttr) {
    return '<div class="detail-head"><div class="row"><div class="grow"><div class="eyebrow" style="margin:0">' + esc(t("air.station")) + "</div><h3>" + esc(s.name) + '</h3><p class="small muted">' + esc([s.city, s.state].filter(Boolean).join(", ")) + "</p></div>" +
      '<button class="btn ghost icon-only sm" ' + closeAttr + ' aria-label="' + esc(t("btn.close")) + '">' + U.icon("x") + "</button></div></div>";
  };
  Air.stationBody = function (s, doc) {
    var k = U.aqiKey(s.aqi), pol = s.pollutants || {};
    return '<div class="row" style="gap:16px">' + U.aqiBadge(s.aqi, true) + '<div><div class="num" style="font-size:22px;font-weight:700">' + esc(t("aqi." + k)) + '</div><div class="small muted">' + esc(t("air.main_pollutant", { p: U.POLLUTANTS[s.dominant] || "–" })) + "</div></div></div>" +
      '<p class="small muted">' + esc(t("air.reading_age", { when: s.updated ? U.when(U.parse(s.updated) || 0, PM.now()) : "?", h: s.age_h == null ? "?" : U.num(s.age_h, 0) })) + "</p>" +
      '<section class="block"><h4>' + esc(t("air.pollutants")) + '</h4><div class="stack" style="gap:10px">' + Object.keys(pol).map(function (p) {
        var v = pol[p], sub = v.sub == null ? 0 : v.sub, sk = U.aqiKey(sub);
        var range = v.min != null && v.max != null ? ' <span class="faint tiny">' + esc(t("air.range", { lo: U.num(v.min, v.min < 10 ? 1 : 0), hi: U.num(v.max, v.max < 10 ? 1 : 0) })) + "</span>" : "";
        return '<div><div class="row spread small"><span>' + esc(U.POLLUTANTS[p] || p) + range + "</span><b>" + U.num(v.avg, v.avg < 10 ? 1 : 0) + ' <span class="muted">' + esc(U.UNITS[p] || "") + '</span></b></div><div class="meter" style="margin-top:3px"><i style="width:' + Math.min(100, sub / 4) + "%;background:" + U.aqiColor(sk) + '"></i></div><div class="tiny faint">' + esc(t("air.subindex", { n: sub })) + "</div></div>";
      }).join("") + "</div></section>" +
      '<p class="tiny muted">' + esc(t("air.source_line", { src: (doc && doc.source) || "" })) + "</p>" +
      (doc && doc.indicative ? '<div class="note">' + U.icon("info") + "<span>" + esc(t("air.indicative")) + "</span></div>" : "");
  };
  Air.pollutantTiles = function (s) {
    var pol = (s && s.pollutants) || {};
    return Object.keys(pol).map(function (p) {
      return '<span class="pol"><span class="tiny muted">' + esc(U.POLLUTANTS[p] || p) + "</span><b>" + U.num(pol[p].avg, pol[p].avg < 10 ? 1 : 0) + ' <span class="tiny muted">' + esc(U.UNITS[p] || "") + "</span></b></span>";
    }).join("");
  };
  Air.scaleLegend = function () {
    var labels = ["0", "50", "100", "200", "300", "400", "500"];
    return '<div class="scale" role="img" aria-label="CPCB AQI colours">' + U.AQI.map(function (c) { return '<i style="background:' + U.aqiColor(c.key) + '"></i>'; }).join("") + "</div>" +
      '<div class="row spread tiny muted">' + labels.map(function (l) { return "<span>" + l + "</span>"; }).join("") + "</div>";
  };
  function failBox(root, e, retry) {
    root.innerHTML = PM.authority.errorBox(e.message, retry);
  }

  // ---- the page with two views --------------------------------------------------------------------------------------
  Air.page = function (root, opts) {
    var view = opts.initial || "now", ctl = null;
    root.innerHTML = '<div class="map-screen"><div class="row spread wrap" style="padding:10px 16px;border-bottom:1px solid var(--line);background:var(--surface)"><div class="seg" role="group" aria-label="View">' +
      '<button data-view="now" aria-pressed="' + (view === "now") + '">' + esc(t("air.now")) + '</button><button data-view="forecast" aria-pressed="' + (view === "forecast") + '">' + esc(t("air.forecast")) + "</button></div>" +
      '<span class="small muted" data-source></span></div><div data-body style="flex:1;min-height:0;position:relative"></div></div>';
    function show(v) {
      view = v;
      root.querySelectorAll("[data-view]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-view") === v)); });
      if (ctl && ctl.destroy) ctl.destroy();
      var body = root.querySelector("[data-body]");
      body.innerHTML = "";
      ctl = (v === "now" ? Air.nowView : Air.forecastView)(body, opts, function (txt) { var s = root.querySelector("[data-source]"); if (s) s.textContent = txt || ""; });
    }
    root.addEventListener("click", function (e) { var b = e.target.closest("[data-view]"); if (b) show(b.getAttribute("data-view")); });
    show(view);
    return { destroy: function () { if (ctl && ctl.destroy) ctl.destroy(); } };
  };

  // ---- measured air now ------------------------------------------------------------------------------------------------
  Air.nowView = function (root, opts, setSource) {
    root.innerHTML = '<div class="dash-body" style="height:100%;padding:12px 16px 16px"><div class="mapwrap"><div class="map" id="airmap"></div></div><section class="panel"><div class="panel-body" style="padding:16px">' + U.skeleton(6, 30) + "</div></section></div>";
    var ctl = { destroyed: false }, mapc = null, layer = null, doc = null, side = root.querySelector(".panel");
    PM.api.stations().then(function (d) {
      if (ctl.destroyed) return;
      doc = d; setSource(d.source + " · " + t("air.updated", { time: U.when(U.parse(d.generated_at) || PM.now(), PM.now()) }));
      build();
    }).catch(function (e) { if (!ctl.destroyed) failBox(root, e, function () { PM.api.refresh(); Air.nowView(root, opts, setSource); }); });

    function build() {
      var wrap = root.querySelector(".mapwrap");
      var rated = doc.stations.filter(function (s) { return s.aqi != null; });
      if (PM.maps.available()) {
        mapc = PM.maps.create(root.querySelector("#airmap"), { theme: document.documentElement.getAttribute("data-theme"), bounds: PM.maps.INDIA });
        layer = PM.maps.stationLayer(mapc.map, rated, function (s) { pick(s, false); });
        wrap.insertAdjacentHTML("beforeend", '<div class="float bl glass legend"><div class="eyebrow">' + esc(t("air.legend")) + "</div>" + Air.scaleLegend() + "</div>");
      } else wrap.innerHTML = PM.maps.noMapHtml();
      list("");
      side.addEventListener("input", function (e) { if (e.target.matches("[data-s]")) listOnly(e.target.value); });
      side.addEventListener("click", function (e) {
        var r = e.target.closest("[data-sid]");
        if (r) { var s = doc.stations.filter(function (x) { return x.id === r.getAttribute("data-sid"); })[0]; if (s) pick(s, true); }
        if (e.target.closest("[data-back]")) list("");
      });
    }
    function row(s) {
      return '<button class="queue-item" style="grid-template-columns:auto 1fr auto" data-sid="' + esc(s.id) + '">' + U.aqiBadge(s.aqi) + '<div style="min-width:0"><div class="truncate"><b>' + esc(s.name) + '</b></div><div class="small muted truncate">' + esc([s.city, s.state].filter(Boolean).join(", ")) + "</div></div>" +
        '<span class="small muted">' + esc(U.POLLUTANTS[s.dominant] || "") + "</span></button>";
    }
    function byId(id) { return doc.stations.filter(function (s) { return s.id === id; })[0]; }
    function section(title, ids) {
      var rows = (ids || []).map(byId).filter(Boolean).slice(0, 8);
      return rows.length ? '<div class="eyebrow" style="padding:12px 16px 4px;margin:0">' + esc(title) + "</div>" + rows.map(row).join("") : "";
    }
    function list(q) {
      side.className = "panel";
      var r = doc.rankings || {};
      side.innerHTML = '<div class="panel-head"><div class="row spread"><h3>' + esc(t("air.stations")) + ' <span class="muted small">' + doc.stations.length + '</span></h3></div><div class="search"><span aria-hidden="true">' + U.icon("search") + '</span><input class="input" data-s type="search" placeholder="' + esc(t("air.search")) + '" aria-label="' + esc(t("air.search")) + '" value="' + esc(q) + '"></div></div>' +
        '<div class="panel-body" data-list></div>';
      listOnly(q);
    }
    function listOnly(q) {
      var box = side.querySelector("[data-list]"), r = doc.rankings || {}, term = q.trim().toLowerCase();
      if (term) {
        var found = doc.stations.filter(function (s) { return s.aqi != null && (s.name + " " + (s.city || "") + " " + (s.state || "")).toLowerCase().indexOf(term) >= 0; }).sort(function (a, b) { return b.aqi - a.aqi; });
        box.innerHTML = found.slice(0, 60).map(row).join("") || '<div class="empty"><p>' + esc(t("air.none")) + "</p></div>";
        return;
      }
      var notes = (doc.notes || []).filter(Boolean);
      box.innerHTML = (notes.length ? '<div style="padding:12px 16px 0"><div class="note warn">' + U.icon("info") + "<span>" + esc(notes[notes.length - 1]) + "</span></div></div>" : "") +
        section(t("air.most_polluted"), r.most_polluted) + (opts.role === "authority" ? section(t("air.focus"), r.focus_most_polluted) : "") + section(t("air.cleanest"), r.cleanest) +
        (opts.role === "authority" ? cityTable() : "");
    }
    function cityTable() {
      var cities = (doc.cities || []).slice().sort(function (a, b) { return b.aqi - a.aqi; }).slice(0, 25);
      if (!cities.length) return "";
      return '<div class="eyebrow" style="padding:12px 16px 4px;margin:0">' + esc(t("air.cities")) + '</div><table class="t"><tbody>' + cities.map(function (c) {
        return "<tr><td>" + esc(c.city) + '</td><td class="small muted">' + esc(U.POLLUTANTS[c.dominant] || "") + '</td><td style="text-align:right">' + U.aqiBadge(c.aqi) + "</td></tr>";
      }).join("") + "</tbody></table>";
    }
    function pick(s, fly) {
      if (mapc && fly) mapc.map.setView([s.lat, s.lon], Math.max(mapc.map.getZoom(), 9));
      side.className = "panel sheet slide-in";
      side.innerHTML = '<div class="sheet-handle"></div>' + Air.stationHead(s, "data-back") + '<div class="detail-body">' + Air.stationBody(s, doc) + "</div>";
      U.sheetDrag(side);
    }
    ctl.destroy = function () { ctl.destroyed = true; if (layer) layer.destroy(); if (mapc) mapc.destroy(); };
    return ctl;
  };

  // ---- forecast ---------------------------------------------------------------------------------------------------------------
  Air.forecastView = function (root, opts, setSource) {
    root.innerHTML = '<div class="dash-body" style="height:100%;padding:12px 16px 16px"><div class="mapwrap"><div class="map" id="fcmap"></div></div><section class="panel"><div class="panel-body" style="padding:16px">' + U.skeleton(6, 30) + "</div></section></div>";
    var ctl = { destroyed: false }, mapc = null, layer = null, grid = null, spotLayer = null, side = root.querySelector(".panel");
    var home = PM.store.home();
    var spot = opts.spot || (home ? { lat: home.lat, lon: home.lon, name: home.name } : { lat: 28.6139, lon: 77.209, name: "Delhi" });
    var timer = null, idx = 0;
    PM.api.forecast().then(function (g) {
      if (ctl.destroyed) return;
      grid = g; setSource(g.source + " · " + t("air.updated", { time: U.when(U.parse(g.generated_at) || PM.now(), PM.now()) }));
      build();
    }).catch(function (e) { if (!ctl.destroyed) failBox(root, e, function () { PM.api.refresh(); Air.forecastView(root, opts, setSource); }); });

    function build() {
      var wrap = root.querySelector(".mapwrap");
      if (PM.maps.available()) {
        mapc = PM.maps.create(root.querySelector("#fcmap"), { theme: document.documentElement.getAttribute("data-theme"), center: [spot.lat, spot.lon], zoom: 6 });
        layer = PM.maps.forecastLayer(mapc.map, grid);
        mapc.map.on("click", function (e) { setSpot({ lat: e.latlng.lat, lon: e.latlng.lng, name: t("air.picked_spot") }); });
        wrap.insertAdjacentHTML("beforeend",
          '<div class="float bl glass legend" style="min-width:260px"><div class="row spread"><b data-time class="num"></b><button class="btn sm icon-only" data-play aria-label="' + esc(t("btn.play")) + '">' + U.icon("play") + "</button></div>" +
          '<input type="range" min="0" max="' + (grid.times.length - 1) + '" value="0" data-slide style="width:100%;margin:8px 0" aria-label="' + esc(t("air.time")) + '">' + Air.scaleLegend() +
          '<div class="tiny muted" style="margin-top:4px">' + esc(t("air.coarse")) + "</div></div>");
        wrap.querySelector("[data-slide]").addEventListener("input", function (e) { stop(); setIdx(Number(e.target.value)); });
        wrap.querySelector("[data-play]").addEventListener("click", function () { timer ? stop() : start(); });
        setIdx(0);
      } else wrap.innerHTML = PM.maps.noMapHtml();
      setSpot(spot);
    }
    function setIdx(i) {
      idx = i;
      layer && layer.setIndex(i);
      var el = root.querySelector("[data-time]"), sl = root.querySelector("[data-slide]");
      if (el) el.textContent = U.when(Date.parse(grid.times[i]), PM.now());
      if (sl) sl.value = i;
    }
    function start() {
      var b = root.querySelector("[data-play]"); b.innerHTML = U.icon("pause");
      timer = setInterval(function () { setIdx((idx + 1) % grid.times.length); }, 900);
    }
    function stop() { if (timer) clearInterval(timer); timer = null; var b = root.querySelector("[data-play]"); if (b) b.innerHTML = U.icon("play"); }

    async function setSpot(s) {
      spot = s;
      if (mapc) {
        if (spotLayer) spotLayer.destroy();
        spotLayer = PM.maps.homeLayer(mapc.map, s, 10);
      }
      side.className = "panel";
      side.innerHTML = '<div class="panel-body" style="padding:16px">' + U.skeleton(5, 28) + "</div>";
      try {
        var r = await PM.api.spot(s.lat, s.lon);
        if (ctl.destroyed) return;
        spotPanel(s, r);
      } catch (e) { side.innerHTML = '<div class="panel-body" style="padding:16px">' + PM.authority.errorBox(e.message, function () { setSpot(s); }) + "</div>"; }
    }
    function spotPanel(s, r) {
      var nowMs = PM.now(), h = Air.headline(r.outlook, nowMs);
      if (!h) { side.innerHTML = '<div class="empty"><p>' + esc(t("air.no_data")) + "</p></div>"; return; }
      var k = U.aqiKey(h.now.aqi), wk = U.aqiKey(h.worst.aqi), n = h.now;
      var pols = ["pm2_5", "pm10", "no2", "so2", "o3", "co"].filter(function (p) { return n[p] != null; });
      side.innerHTML = '<div class="panel-head"><div class="eyebrow" style="margin:0">' + esc(t("air.spot")) + "</div><h3>" + esc(s.name || "") + '</h3><p class="tiny muted">' + U.num(s.lat, 2) + "°N, " + U.num(s.lon, 2) + "°E</p></div>" +
        '<div class="panel-body"><div style="padding:16px" class="stack"><div class="row" style="gap:16px">' + U.aqiBadge(n.aqi, true) + '<div><div class="num" style="font-size:22px;font-weight:700">' + esc(t("aqi." + k)) + '</div><div class="small muted">' + esc(t("air.expected_now")) + "</div></div></div>" +
        '<div><div class="label">' + esc(t("air.next48")) + "</div>" + Air.strip(h.future, nowMs) + "</div>" +
        '<p class="small">' + esc(t("air.worst_at", { aqi: Math.round(h.worst.aqi), cat: t("aqi." + wk), when: U.when(h.worst.ms, nowMs) })) + "</p>" +
        (pols.length ? '<section class="block"><h4>' + esc(t("air.pollutants")) + '</h4><dl class="kv">' + pols.map(function (p) { return "<dt>" + esc(U.POLLUTANTS[p]) + "</dt><dd>" + U.num(n[p], n[p] < 10 ? 1 : 0) + " " + esc(U.UNITS[p]) + "</dd>"; }).join("") + "</dl></section>" : "") +
        (r.approx ? '<div class="note">' + U.icon("info") + "<span>" + esc(t("air.sample_note")) + "</span></div>" : "") +
        '<p class="tiny muted">' + esc(t("air.forecast_note")) + "</p></div></div>";
    }
    ctl.destroy = function () { ctl.destroyed = true; stop(); if (layer) layer.destroy(); if (spotLayer) spotLayer.destroy(); if (mapc) mapc.destroy(); };
    return ctl;
  };
})((window.PM = window.PM || {}));

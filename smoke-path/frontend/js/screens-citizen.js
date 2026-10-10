/* Citizen screens: pick your area, "My area" (air now, next 48 hours, smoke coming, health advice, alerts),
   a calm map, the alerts inbox and health tips. Read only: nothing here can send or change anything. */
(function (PM) {
  "use strict";
  var U = PM.U, esc = U.esc, t = function (k, v) { return PM.t(k, v); };
  var C = (PM.citizen = {});
  var NEAR_KM = 50;

  function needHome(root) {
    if (PM.store.home()) return false;
    PM.go("#/citizen/setup");
    return true;
  }
  function catKey(n) { return U.aqiKey(n); }
  function band(k) { return k === "good" || k === "satisfactory" ? "ok" : k === "moderate" || k === "poor" ? "care" : "stay"; }
  function loading(h) { return '<div class="card">' + U.skeleton(3, h || 22) + "</div>"; }

  // ---- pick your area ------------------------------------------------------------------------------------------------
  C.setup = function (root) {
    var first = !PM.store.home();
    root.innerHTML = '<div class="page" style="max-width:760px"><div class="page-head"><div><h1>' + esc(t("cz.setup_title")) + '</h1><p class="muted">' + esc(t("cz.setup_sub")) + "</p></div></div>" +
      '<div class="card stack"><div class="field"><label for="place-q">' + esc(t("cz.search_label")) + '</label><div class="search"><span aria-hidden="true">' + U.icon("search") + '</span><input id="place-q" class="input" data-q type="search" autocomplete="off" placeholder="' + esc(t("cz.search_ph")) + '"></div><div class="results" data-results hidden></div><p class="small muted" data-hint></p></div>' +
      '<div class="row wrap"><button class="btn" data-gps>' + U.icon("crosshair") + esc(t("cz.use_gps")) + '</button><button class="btn" data-pickmap>' + U.icon("pin") + esc(t("cz.pick_map")) + '</button></div>' +
      '<div class="mini-map" data-map hidden></div>' +
      '<div data-heading hidden><div class="label" style="margin-bottom:8px">' + esc(t("cz.smoke_heading")) + '</div><div class="quick" data-heading-list></div></div>' +
      '<div><div class="label" style="margin-bottom:8px">' + esc(t("cz.quick")) + '</div><div class="quick">' + (window.PM_PLACES || []).map(function (p, i) {
        return '<button class="chip" data-quick="' + i + '">' + esc(p.name) + "</button>";
      }).join("") + "</div></div></div>" + (first ? "" : '<p style="margin-top:16px"><a href="#/citizen/home">' + esc(t("btn.back")) + "</a></p>") + "</div>";
    var mapc = null, results = root.querySelector("[data-results]"), hint = root.querySelector("[data-hint]"), heading = [];
    // Places the smoke is heading to right now (from the fire data): a quick way to try the app where it matters.
    PM.api.fires().then(function (model) {
      var seen = {};
      heading = model.reached.filter(function (r) { return r.name && r.fires >= 2; }).sort(function (a, b) { return b.fires - a.fires; })
        .filter(function (r) { if (seen[r.name]) return false; seen[r.name] = 1; return true; }).slice(0, 6);
      if (!heading.length) return;
      root.querySelector("[data-heading]").hidden = false;
      root.querySelector("[data-heading-list]").innerHTML = heading.map(function (r, i) {
        return '<button class="chip" data-heading-pick="' + i + '">' + U.icon("wind", "sm") + esc(t("cz.smoke_chip", { name: r.name, n: r.fires })) + "</button>";
      }).join("");
    }).catch(function () {});
    function save(h) { PM.store.setHome(h); U.toast(t("cz.saved", { name: h.name })); PM.go("#/citizen/home"); }
    root.addEventListener("click", function (e) {
      var q = e.target.closest("[data-quick]");
      if (q) { var p = window.PM_PLACES[Number(q.getAttribute("data-quick"))]; save({ name: p.name, state: p.state, lat: p.lat, lon: p.lon }); }
      var hp = e.target.closest("[data-heading-pick]");
      if (hp) { var r0 = heading[Number(hp.getAttribute("data-heading-pick"))]; save({ name: r0.name, state: "", lat: r0.lat, lon: r0.lon }); }
      var r = e.target.closest("[data-res]");
      if (r) save(JSON.parse(r.getAttribute("data-res")));
      if (e.target.closest("[data-gps]")) {
        if (!navigator.geolocation) { U.toast(t("cz.no_gps"), "err"); return; }
        navigator.geolocation.getCurrentPosition(function (pos) { save({ name: t("cz.my_location"), lat: pos.coords.latitude, lon: pos.coords.longitude }); },
          function () { U.toast(t("cz.no_gps"), "err"); }, { timeout: 10000 });
      }
      if (e.target.closest("[data-pickmap]")) {
        var box = root.querySelector("[data-map]"); box.hidden = false;
        if (!PM.maps.available()) { box.innerHTML = PM.maps.noMapHtml(); return; }
        if (!mapc) {
          mapc = PM.maps.create(box, { theme: document.documentElement.getAttribute("data-theme"), center: [29.5, 76], zoom: 6 });
          mapc.map.on("click", function (ev) { save({ name: U.num(ev.latlng.lat, 3) + "°N, " + U.num(ev.latlng.lng, 3) + "°E", lat: ev.latlng.lat, lon: ev.latlng.lng }); });
        } else mapc.map.invalidateSize();
        hint.textContent = t("cz.tap_map");
      }
    });
    var search = U.debounce(async function (q) {
      if (q.trim().length < 3) { results.hidden = true; return; }
      var local = (window.PM_PLACES || []).filter(function (p) { return p.name.toLowerCase().indexOf(q.trim().toLowerCase()) >= 0; });
      var list = local.map(function (p) { return { name: p.name, state: p.state, lat: p.lat, lon: p.lon }; });
      try {
        var r = await fetch("https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=6&countrycodes=in&q=" + encodeURIComponent(q), { headers: { Accept: "application/json" } });
        (await r.json()).forEach(function (x) {
          var a = x.address || {}, name = x.name || a.village || a.town || a.city || a.hamlet || (x.display_name || "").split(",")[0];
          list.push({ name: name, state: a.state || "", lat: Number(x.lat), lon: Number(x.lon), sub: [a.county || a.state_district, a.state].filter(Boolean).join(", ") });
        });
        hint.textContent = "";
      } catch (e) { hint.textContent = t("cz.search_offline"); }
      results.hidden = !list.length;
      results.innerHTML = list.slice(0, 8).map(function (p) {
        return "<button data-res='" + esc(JSON.stringify({ name: p.name, state: p.state, lat: p.lat, lon: p.lon })) + "'><b>" + esc(p.name) + '</b> <span class="muted small">' + esc(p.sub || p.state || "") + "</span></button>";
      }).join("");
    }, 450);
    root.querySelector("[data-q]").addEventListener("input", function (e) { search(e.target.value); });
    return { destroy: function () { if (mapc) mapc.destroy(); } };
  };

  // ---- My area ------------------------------------------------------------------------------------------------------------------
  C.home = function (root) {
    if (needHome(root)) return { destroy: function () {} };
    var home = PM.store.home(), ctl = { destroyed: false }, mapc = null, layers = [];
    var name = home.name + (home.state ? ", " + home.state : "");
    root.innerHTML = '<div class="page"><div class="page-head"><div><p class="eyebrow">' + esc(t("cz.hello")) + "</p><h1>" + esc(name) + '</h1></div><a class="btn" href="#/citizen/setup">' + U.icon("pin") + esc(t("cz.change_area")) + "</a></div>" +
      '<div class="home-grid"><div class="span-12" data-hero>' + loading(60) + '</div><div class="span-7" data-next>' + loading(70) + '</div><div class="span-5" data-advice>' + loading(70) + '</div>' +
      '<div class="span-7" data-smoke>' + loading(70) + '</div><div class="span-5" data-alerts>' + loading(50) + "</div></div></div>";
    var $ = function (s) { return root.querySelector(s); };
    var nowMs = function () { return PM.now(); };

    // air now + next 48 h
    Promise.all([PM.api.stations().catch(function () { return null; }), PM.api.spot(home.lat, home.lon).catch(function () { return null; })]).then(function (r) {
      if (ctl.destroyed) return;
      var near = r[0] ? PM.air.nearest(r[0].stations, home.lat, home.lon) : null, spot = r[1];
      var head = spot ? PM.air.headline(spot.outlook, nowMs()) : null;
      var useStation = near && near.d <= 100, aqi, src;
      if (useStation) { aqi = near.s.aqi; src = t("cz.measured_at", { station: near.s.name, km: U.num(near.d, 0), when: near.s.updated ? U.when(U.parse(near.s.updated) || 0, nowMs()) : "" }); }
      else if (head) { aqi = head.now.aqi; src = t("cz.forecast_for", { km: 100 }); }
      if (aqi == null) {
        $("[data-hero]").innerHTML = '<div class="card"><p>' + esc(t("cz.no_air")) + "</p></div>";
      } else {
        var k = catKey(aqi);
        $("[data-hero]").innerHTML = '<div class="hero-aqi fade-in" style="--c:var(--aqi-' + k + ')"><div><div class="eyebrow">' + esc(t("cz.air_now")) + '</div><div class="big-num num" data-n>0</div></div><div><div class="cat" style="color:var(--ink)"><span class="dot" style="background:var(--aqi-' + k + ');width:14px;height:14px"></span> ' + esc(t("aqi." + k)) + "</div>" +
          '<p class="say">' + esc(t("cz.say." + k)) + '</p><p class="small muted" style="margin-top:10px">' + esc(src) + "</p>" + (useStation ? '<div class="pol-grid">' + PM.air.pollutantTiles(near.s) + "</div>" : "") + "</div></div>";
        U.countUp($("[data-n]"), aqi, 600);
        advice(k);
      }
      if (head) {
        var wk = catKey(head.worst.aqi), bk = catKey(head.best.aqi);
        var line = head.trend === "worse" ? t("cz.trend.worse", { cat: t("aqi." + wk), when: U.when(head.worst.ms, nowMs()) }) : head.trend === "better" ? t("cz.trend.better", { cat: t("aqi." + bk), when: U.when(head.best.ms, nowMs()) }) : t("cz.trend.same", { cat: t("aqi." + catKey(head.now.aqi)) });
        $("[data-next]").innerHTML = '<div class="card fade-in"><div class="eyebrow">' + esc(t("cz.next48")) + '</div><h3 style="margin-bottom:12px">' + esc(line) + "</h3>" + PM.air.strip(head.future, nowMs()) + (spot.approx ? '<p class="tiny muted" style="margin-top:8px">' + esc(t("air.sample_note")) + "</p>" : "") + "</div>";
      } else $("[data-next]").innerHTML = '<div class="card"><div class="eyebrow">' + esc(t("cz.next48")) + "</div><p>" + esc(t("cz.no_forecast")) + "</p></div>";
    });
    function advice(k) {
      var b = band(k);
      $("[data-advice]").innerHTML = '<div class="card fade-in"><div class="eyebrow">' + esc(t("cz.advice_title")) + '</div><ul class="advice" style="padding-left:18px;margin:0">' + t("tips." + k + ".do").split("|").map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" +
        '<hr class="divider"><div class="stack" style="gap:8px">' + ["children", "elderly", "asthma"].map(function (g) {
          return '<div class="row" style="align-items:flex-start"><span class="chip" style="min-width:92px;justify-content:center">' + esc(t("grp2." + g)) + '</span><span class="small">' + esc(t("cz.group." + g + "." + b)) + "</span></div>";
        }).join("") + "</div></div>";
    }

    // smoke coming + fires near
    PM.api.fires().then(function (model) {
      if (ctl.destroyed) return;
      var reaching = model.firesReaching(home.lat, home.lon, 5), nearby = model.firesNear(home.lat, home.lon, NEAR_KM);
      var upcoming = reaching.filter(function (x) { return x.t > nowMs(); }), already = reaching.filter(function (x) { return x.t <= nowMs(); });
      var shownList = upcoming.concat(already.slice().reverse()).slice(0, 5);
      var lines = shownList.map(function (x) {
        var d = U.distKm(home.lat, home.lon, x.fire.lat, x.fire.lon);
        return '<div class="fire-line">' + U.typeBadge(x.fire.p) + '<div style="min-width:0"><div class="truncate"><b>' + esc(t("cz.fire_line", { type: U.typeName(x.fire.p), near: x.fire.near || t("cz.unknown_place"), km: U.num(d, 0) })) + '</b></div><div class="small muted">' + esc(t(x.t > nowMs() ? "cz.arrives" : "cz.arrived", { when: U.when(x.t, nowMs()) })) + '</div></div><span class="pill">' + esc(U.rel(x.t, nowMs())) + "</span></div>";
      }).join("");
      var firstUp = upcoming[0], headline = firstUp ? t("cz.smoke_some", { n: upcoming.length, rel: U.rel(firstUp.t, nowMs()), when: U.when(firstUp.t, nowMs()) })
        : already.length ? t("cz.smoke_here", { n: already.length, when: U.when(already[0].t, nowMs()) }) : "";
      $("[data-smoke]").innerHTML = '<div class="card fade-in"><div class="eyebrow">' + esc(t("cz.smoke_title")) + "</div>" +
        (headline ? '<h3 style="margin-bottom:6px">' + esc(headline) + "</h3>" + (firstUp && already.length ? '<p class="small muted" style="margin-bottom:6px">' + esc(t("cz.smoke_also", { n: already.length })) + "</p>" : "") + lines
          : '<div class="row" style="gap:10px"><span style="color:var(--ok)">' + U.icon("check", "lg") + "</span><h3>" + esc(t("cz.smoke_none")) + "</h3></div>") +
        '<p class="small muted" style="margin-top:10px">' + esc(nearby.length ? t("cz.nearby", { n: nearby.length, km: NEAR_KM }) : t("cz.nearby_none", { km: NEAR_KM })) + "</p>" +
        '<div class="mini-map" data-map style="margin-top:12px"></div><div class="row" style="margin-top:10px"><a class="btn" href="#/citizen/map">' + U.icon("map") + esc(t("cz.open_map")) + "</a></div></div>";
      if (PM.maps.available()) {
        mapc = PM.maps.create($("[data-map]"), { theme: document.documentElement.getAttribute("data-theme"), center: [home.lat, home.lon], zoom: 8 });
        layers.push(PM.maps.homeLayer(mapc.map, home, NEAR_KM));
        var fl = PM.maps.fireLayer(mapc.map, {});
        fl.set(model.firesNear(home.lat, home.lon, 120).map(function (x) { return x.fire; }));
        layers.push(fl);
        shownList.forEach(function (x) {
          var line = L.polyline(x.fire.path.coords.map(function (c) { return [c[1], c[0]]; }), { color: U.css("--fire"), weight: 3, opacity: 0.8, dashArray: "6 6", interactive: false }).addTo(mapc.map);
          layers.push({ destroy: function () { line.remove(); } });
        });
        mapc.map.setView([home.lat, home.lon], nearby.length ? 8 : 9);
      } else $("[data-map]").innerHTML = PM.maps.noMapHtml();
    }).catch(function (e) { if (!ctl.destroyed) $("[data-smoke]").innerHTML = PM.authority.errorBox(e.message, function () { PM.api.refresh(); C.home(root); }); });

    // alerts from authorities
    function alerts() {
      PM.api.alertsNear(home).then(function (list) {
        if (ctl.destroyed) return;
        var read = PM.store.read(), a = list[0];
        $("[data-alerts]").innerHTML = '<div class="card fade-in"><div class="eyebrow">' + esc(t("cz.alerts_title")) + "</div>" +
          (a ? '<a href="#/citizen/alerts" class="alert-card' + (read.indexOf(a.id) < 0 ? " unread" : "") + '" style="text-decoration:none;color:inherit"><span class="ic">' + U.icon("bell") + '</span><div><b>' + esc(t("cz.alert_title", { place: (a.fire && (a.fire.near || a.fire.state)) || t("cz.unknown_place") })) + '</b><div class="small muted">' + esc(U.rel(U.parse(a.created_at) || 0, nowMs())) + '</div><p class="small" style="margin-top:6px">' + esc(a.message.slice(0, 140)) + (a.message.length > 140 ? "…" : "") + "</p></div></a>"
            : '<p class="muted">' + esc(t("cz.no_alerts")) + "</p>") + "</div>";
      }).catch(function () { $("[data-alerts]").innerHTML = '<div class="card"><p class="muted">' + esc(t("cz.no_alerts")) + "</p></div>"; });
    }
    alerts();
    var off = PM.on("alerts", alerts);
    ctl.destroy = function () { ctl.destroyed = true; off(); layers.forEach(function (l) { l.destroy(); }); if (mapc) mapc.destroy(); };
    return ctl;
  };

  // ---- the calm map ----------------------------------------------------------------------------------------------------------------
  C.map = function (root) {
    if (needHome(root)) return { destroy: function () {} };
    var home = PM.store.home(), ctl = { destroyed: false }, on = { fires: true, air: false }, layers = {};
    var types = {};  // fire types switched on (none on = show all)
    root.innerHTML = '<div class="map-screen"><div class="mapwrap"><div class="map" id="cmap"></div><div class="float tl glass typebar" style="flex-direction:column;align-items:flex-start" role="group" aria-label="Layers">' +
      '<div class="row" style="gap:6px"><button class="chip" data-layer="fires" aria-pressed="true">' + U.icon("flame", "sm") + esc(t("cz.layer_fires")) + '</button><button class="chip" data-layer="air" aria-pressed="false">' + U.icon("wind", "sm") + esc(t("cz.layer_air")) + "</button></div>" +
      '<div class="row" style="gap:6px;flex-wrap:wrap" data-typechips></div></div><section class="panel sheet floatpanel" data-fire hidden></section></div></div>';
    if (!PM.maps.available()) { root.innerHTML = PM.maps.noMapHtml(); return ctl; }
    var mapc = PM.maps.create(root.querySelector("#cmap"), { theme: document.documentElement.getAttribute("data-theme"), center: [home.lat, home.lon], zoom: 7 });
    var smoke = PM.maps.smokeLayer(mapc.map), model = null, stations = null, popup = null;
    layers.home = PM.maps.homeLayer(mapc.map, home, NEAR_KM);
    mapc.map.on("click", function () { smoke.clear(); root.querySelector("[data-fire]").hidden = true; });

    function popupFor(f) {
      var d = U.distKm(home.lat, home.lon, f.lat, f.lon), hit = f.path ? U.reaches(f.path, home.lat, home.lon, 5) : null;
      return '<div style="min-width:200px"><b>' + esc(t("cz.fire_line", { type: U.typeName(f.p), near: f.near || t("cz.unknown_place"), km: U.num(d, 0) })) + '</b><div class="small" style="margin-top:4px">' +
        esc(hit ? (hit.t > PM.now() ? t("cz.smoke_you", { when: U.when(hit.t, PM.now()), rel: U.rel(hit.t, PM.now()) }) : t("cz.smoke_here1", { when: U.when(hit.t, PM.now()) })) : t("cz.smoke_not_you")) + '</div><div class="small muted" style="margin-top:4px">' + esc(f.p.fire_type_reason || "") + "</div></div>";
    }
    function showStation(st) {
      var box = root.querySelector("[data-fire]");
      box.hidden = false;
      box.innerHTML = '<div class="sheet-handle"></div>' + PM.air.stationHead(st, "data-fclose") + '<div class="detail-body">' + PM.air.stationBody(st, stations) + "</div>";
      U.sheetDrag(box);
    }
    function showFire(f) {
      var box = root.querySelector("[data-fire]"), A = PM.authority, p = f.p, places = model.placesOn(f);
      var d = U.distKm(home.lat, home.lon, f.lat, f.lon), hit = f.path ? U.reaches(f.path, home.lat, home.lon, 5) : null;
      var you = hit ? (hit.t > PM.now() ? t("cz.smoke_you", { when: U.when(hit.t, PM.now()), rel: U.rel(hit.t, PM.now()) }) : t("cz.smoke_here1", { when: U.when(hit.t, PM.now()) })) : t("cz.smoke_not_you");
      box.hidden = false;
      box.innerHTML = '<div class="sheet-handle"></div><div class="detail-head"><div class="row" style="align-items:flex-start">' + U.typeBadge(p) + '<div class="grow"><div class="eyebrow" style="margin:0">' + esc(U.typeName(p)) + "</div><h3>" + esc(f.near || f.state || "Fire") + (f.near && f.state ? ", " + esc(f.state) : "") + '</h3><p class="small muted" style="margin-top:4px">' + esc(t("cz.km_away", { km: U.num(d, 0) })) + " · " + esc(t("auth.first_seen", { when: U.when(f.seenMs, PM.now()), rel: U.rel(f.seenMs, PM.now()) })) + "</p></div>" +
        '<button class="btn ghost icon-only sm" data-fclose aria-label="' + esc(t("btn.close")) + '">' + U.icon("x") + "</button></div></div>" +
        '<div class="detail-body"><div class="note ' + (hit ? "warn" : "") + '">' + U.icon(hit ? "alert" : "check") + "<span>" + esc(you) + "</span></div>" +
        '<section class="block"><h4>' + esc(t("auth.what_burning")) + "</h4><p><b>" + esc(p.fire_type_label || U.typeName(p)) + '</b></p><p class="small">' + esc(p.fire_type_reason || "") + '</p><div style="margin-top:8px">' + A.coverBar(p) + "</div>" + A.outsideNote(f) + "</section>" +
        '<section class="block"><h4>' + esc(t("auth.toxicity")) + "</h4>" + A.toxBlock(f, true) + "</section>" +
        (places.length ? '<section class="block"><h4>' + esc(t("cz.places_on_path")) + '</h4><div class="places">' + places.slice(0, 10).map(function (q) {
          return '<div class="place"><span>' + esc(q.name) + ' <span class="faint small">' + esc(q.type) + '</span></span><span class="t">' + esc(U.when(q.t, PM.now())) + "</span></div>";
        }).join("") + "</div></section>" : "") + "</div>";
      U.sheetDrag(box);
    }
    function paintFires() {
      if (layers.fires) layers.fires.destroy();
      layers.fires = null;
      if (!on.fires || !model) return;
      layers.fires = PM.maps.fireLayer(mapc.map, { onPick: function (f) {
        smoke.show(f, { ticks: "clock", fit: false }); smoke.play();
        showFire(f);
      } });
      layers.fires.set(filteredFires(), Object.keys(types).some(function (k) { return types[k]; }));
    }
    function filteredFires() {
      var active = Object.keys(types).filter(function (k) { return types[k]; });
      return model.fires.filter(function (f) { return !active.length || active.indexOf(f.p.fire_type || "unknown") >= 0; });
    }
    function paintChips() {
      var counts = {};
      model.fires.forEach(function (f) { var k = f.p.fire_type || "unknown"; counts[k] = (counts[k] || 0) + 1; });
      root.querySelector("[data-typechips]").innerHTML = U.typeChips(counts, types);
    }
    function paintAir() {
      if (layers.air) layers.air.destroy();
      layers.air = null;
      if (!on.air || !stations) return;
      layers.air = PM.maps.stationLayer(mapc.map, stations.stations.filter(function (s) { return s.aqi != null; }), function (s) {
        smoke.clear(); showStation(s);
      });
    }
    PM.api.fires().then(function (m) { if (!ctl.destroyed) { model = m; paintChips(); paintFires(); } });
    PM.api.stations().then(function (s) { if (!ctl.destroyed) { stations = s; paintAir(); } }).catch(function () {});
    root.addEventListener("click", function (e) {
      var ft = e.target.closest("[data-ftype]");
      if (ft) {
        U.toggleType(types, ft.getAttribute("data-ftype")); on.fires = true;
        paintChips(); paintFires();
        var list = filteredFires();
        if (list.length && Object.keys(types).some(function (k) { return types[k]; })) mapc.map.fitBounds(L.latLngBounds(list.map(function (f) { return [f.lat, f.lon]; }).concat([[home.lat, home.lon]])).pad(0.2), { maxZoom: 8, animate: true });
        return;
      }
      if (e.target.closest("[data-fclose]")) { root.querySelector("[data-fire]").hidden = true; smoke.clear(); return; }
      var b = e.target.closest("[data-layer]");
      if (!b) return;
      var k = b.getAttribute("data-layer"); on[k] = !on[k]; b.setAttribute("aria-pressed", String(on[k]));
      if (k === "fires") paintFires(); else paintAir();
    });
    ctl.destroy = function () { ctl.destroyed = true; smoke.destroy(); Object.keys(layers).forEach(function (k) { if (layers[k]) layers[k].destroy(); }); mapc.destroy(); };
    return ctl;
  };

  // ---- forecast ---------------------------------------------------------------------------------------------------------------------
  C.forecast = function (root) {
    if (needHome(root)) return { destroy: function () {} };
    root.innerHTML = '<div class="map-screen"><div data-body style="flex:1;min-height:0;position:relative"></div></div>';
    var v = PM.air.forecastView(root.querySelector("[data-body]"), { role: "citizen" }, function () {});
    return v;
  };

  // ---- alerts inbox -------------------------------------------------------------------------------------------------------------------
  C.alerts = function (root) {
    if (needHome(root)) return { destroy: function () {} };
    var home = PM.store.home(), ctl = { destroyed: false }, open = null;
    root.innerHTML = '<div class="page" style="max-width:760px"><div class="page-head"><div><h1>' + esc(t("nav.alerts")) + '</h1><p class="muted">' + esc(t("cz.inbox_sub", { name: home.name })) + '</p></div><button class="btn" data-readall>' + U.icon("check") + esc(t("cz.mark_read")) + '</button></div><div class="stack" data-list>' + loading(60) + "</div></div>";
    var list = [];
    function load() {
      PM.api.alertsNear(home).then(function (l) { if (!ctl.destroyed) { list = l; paint(); } })
        .catch(function (e) { if (!ctl.destroyed) root.querySelector("[data-list]").innerHTML = PM.authority.errorBox(e.message, load); });
    }
    function paint() {
      var read = PM.store.read(), box = root.querySelector("[data-list]");
      if (!list.length) { box.innerHTML = '<div class="empty card">' + U.icon("check") + "<p><b>" + esc(t("cz.inbox_empty")) + "</b></p><p class=\"small\">" + esc(t("cz.inbox_empty_sub")) + "</p></div>"; return; }
      box.innerHTML = list.map(function (a) {
        var unread = read.indexOf(a.id) < 0, isOpen = open === a.id, places = a.target.places;
        return '<button class="alert-card' + (unread ? " unread" : "") + '" data-id="' + esc(a.id) + '" aria-expanded="' + isOpen + '"><span class="ic">' + U.icon("bell") + '</span><div style="min-width:0;flex:1"><div class="row spread"><b>' + esc(t("cz.alert_title", { place: (a.fire && (a.fire.near || a.fire.state)) || t("cz.unknown_place") })) + "</b>" + (unread ? '<span class="pill" style="background:var(--fire);color:#fff;border:0">' + esc(t("cz.new")) + "</span>" : "") + '</div><div class="small muted">' + esc(U.rel(U.parse(a.created_at) || 0, PM.now())) + " · " + esc((a.distance_km < 1 ? t("cz.affects_here", { n: places.length }) : t("cz.affects", { n: places.length, km: U.num(a.distance_km, 0) }))) + "</div>" +
          '<p class="body" ' + (isOpen ? "" : 'style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden"') + ">" + esc(a.message) + "</p>" +
          (isOpen && places[0] && places[0].arrival ? '<p class="small muted" style="margin-top:8px">' + esc(t("cz.first_place", { place: places[0].name, when: U.when(U.parse(places[0].arrival) || 0, PM.now()) })) + "</p>" : "") + "</div></button>";
      }).join("");
    }
    root.addEventListener("click", function (e) {
      var c = e.target.closest("[data-id]");
      if (c) { open = open === c.getAttribute("data-id") ? null : c.getAttribute("data-id"); PM.store.markRead([c.getAttribute("data-id")]); }
      if (e.target.closest("[data-readall]")) PM.store.markRead(list.map(function (a) { return a.id; }));
    });
    var off = PM.on("alerts", function () { if (list.length) { paint(); } load(); });
    var poll = setInterval(load, 20000);
    load();
    ctl.destroy = function () { ctl.destroyed = true; off(); clearInterval(poll); };
    return ctl;
  };

  // ---- health tips -----------------------------------------------------------------------------------------------------------------------
  C.tips = function (root) {
    root.innerHTML = '<div class="page" style="max-width:820px"><div class="page-head"><div><h1>' + esc(t("nav.tips")) + '</h1><p class="muted">' + esc(t("tips.sub")) + "</p></div></div>" +
      '<div class="card">' + U.AQI.map(function (c) {
        return '<div class="cat-row"><span class="sw" style="background:' + U.aqiColor(c.key) + '"></span><div><div class="row spread"><b>' + esc(t("aqi." + c.key)) + '</b><span class="small muted">AQI ' + c.min + "–" + c.max + '</span></div><p class="small" style="margin-top:4px">' + esc(t("tips." + c.key + ".who")) + '</p><ul class="small advice" style="margin:6px 0 0;padding-left:18px">' + t("tips." + c.key + ".do").split("|").map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul></div></div>";
      }).join("") + "</div>" +
      '<div class="card" style="margin-top:16px"><h3 style="margin-bottom:8px">' + esc(t("tips.smoke_title")) + '</h3><ul class="advice" style="padding-left:18px;margin:0">' + t("tips.smoke").split("|").map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul></div>" +
      '<p class="small muted" style="margin-top:12px">' + esc(t("tips.source")) + "</p></div>";
    return { destroy: function () {} };
  };
})((window.PM = window.PM || {}));

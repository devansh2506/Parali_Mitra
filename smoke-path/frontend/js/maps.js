/* Everything that draws on a Leaflet map: base map, fire dots, the smoke path and its animation, stations,
   the forecast squares and the citizen's home. Screens call these and never touch Leaflet directly. */
(function (PM) {
  "use strict";
  var U = PM.U;
  var M = (PM.maps = {});
  var INDIA = [[7.0, 68.0], [36.5, 93.5]];  // India on screen (the far islands are left to panning)
  // Base maps that need no key. CARTO's basemaps now ask for a key (they return a watermark tile), so the
  // calm grey maps come from Esri's "Canvas" set (light and dark, with a separate labels layer); plain
  // OpenStreetMap with a CSS filter is the fallback if those tiles fail.
  var ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/";
  var ESRI_ATTR = 'Tiles © Esri — Esri, HERE, Garmin, © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  var OSM_ATTR = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  M.available = function () { return typeof window.L !== "undefined"; };
  M.INDIA = INDIA;
  M.noMapHtml = function () {
    return '<div class="empty"><p><b>The map could not load.</b></p><p class="small">Check your internet connection. The rest of the page still works.</p></div>';
  };

  /** A map with a dark or light base. Falls back to plain OpenStreetMap (with a CSS filter) if the Esri tiles fail. */
  M.create = function (el, opts) {
    opts = opts || {};
    var map = L.map(el, { preferCanvas: true, zoomControl: false, zoomSnap: 0.5, zoomDelta: 0.5, minZoom: 4, maxZoom: 14, worldCopyJump: false, attributionControl: true });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    if (opts.bounds) map.fitBounds(opts.bounds, { padding: [10, 10] });
    else map.setView(opts.center || [22.5, 79], opts.zoom || 5);
    var base = null, labels = null, theme = opts.theme || "light", fails = 0, fallback = false;
    function setBase() {
      if (base) map.removeLayer(base);
      if (labels) map.removeLayer(labels);
      base = labels = null;
      el.classList.remove("fallback-dark", "fallback-light");
      if (!fallback) {
        var name = theme === "dark" ? "World_Dark_Gray" : "World_Light_Gray";
        base = L.tileLayer(ESRI + name + "_Base/MapServer/tile/{z}/{y}/{x}", { maxZoom: 14, maxNativeZoom: 13, attribution: ESRI_ATTR });
        labels = L.tileLayer(ESRI + name + "_Reference/MapServer/tile/{z}/{y}/{x}", { maxZoom: 14, maxNativeZoom: 13, pane: "overlayPane", opacity: 0.9 });
        base.on("tileerror", function () { if (++fails >= 4 && !fallback) { fallback = true; setBase(); } });
        base.on("tileload", function () { fails = 0; });
        labels.addTo(map).bringToBack();
      } else {
        base = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 14, attribution: OSM_ATTR });
        el.classList.add(theme === "dark" ? "fallback-dark" : "fallback-light");
      }
      base.addTo(map);
      base.bringToBack();
    }
    setBase();
    var stop = PM.on("theme", function () { theme = document.documentElement.getAttribute("data-theme"); setBase(); });
    setTimeout(function () { map.invalidateSize(); }, 0);
    function onResize() { map.invalidateSize(); }
    window.addEventListener("resize", onResize);
    return {
      map: map,
      destroy: function () { stop(); window.removeEventListener("resize", onResize); map.remove(); },
    };
  };

  // ---- fire dots ---------------------------------------------------------------------------------------------
  /**
   * Fire dots sized and coloured by toxicity. Few at far zoom, all when you zoom in (decluttering).
   * opts: {onPick(fire), selectedKey}. Returns {set(fires), select(key), destroy()}.
   */
  M.fireLayer = function (map, opts) {
    var dots = L.layerGroup().addTo(map), pulses = L.layerGroup().addTo(map), ring = L.layerGroup().addTo(map);
    var fires = [], selected = opts.selectedKey || null, markers = {};
    var MAX_FAR = 90;

    function style(f) {
      var level = f.level, none = !f.tox;
      var color = none ? U.css("--tox-none") : U.toxColor(level);
      return { radius: U.toxRadius(level), color: U.css("--surface"), weight: 1.5, fillColor: color, fillOpacity: none ? 0.35 : 0.88, opacity: 1 };
    }
    function draw() {
      dots.clearLayers(); pulses.clearLayers(); ring.clearLayers(); markers = {};
      var zoom = map.getZoom();
      var order = fires.slice().sort(function (a, b) { return (a.km3 || 0) - (b.km3 || 0); });  // strongest on top
      var shown = zoom >= 6 ? order : order.filter(function (f, i) { return i >= order.length - MAX_FAR || f.p.fire_type === "industrial" || f.key === selected; });
      var pulseLeft = 24;
      shown.forEach(function (f) {
        var st = style(f);
        var m = L.circleMarker([f.lat, f.lon], st).addTo(dots);
        m.bindTooltip(U.esc((f.near ? "Near " + f.near : "Fire " + f.id) + " · " + U.typeName(f.p) + (f.level ? " · " + f.level + " toxicity" : "")), { direction: "top", offset: [0, -6] });
        m.on("click", function () { opts.onPick && opts.onPick(f); });
        markers[f.key] = m;
        if (f.level === "very high" && pulseLeft-- > 0) {
          L.marker([f.lat, f.lon], { interactive: false, keyboard: false, icon: L.divIcon({ className: "", html: '<div class="pulse soft" style="--c:' + U.toxColor(f.level) + '"></div>', iconSize: [0, 0] }) }).addTo(pulses);
        }
      });
      if (selected && markers[selected]) {
        var f = fires.filter(function (x) { return x.key === selected; })[0];
        L.circleMarker([f.lat, f.lon], { radius: U.toxRadius(f.level) + 7, color: U.css("--ink"), weight: 3, fill: false, interactive: false }).addTo(ring);
        L.marker([f.lat, f.lon], { interactive: false, keyboard: false, icon: L.divIcon({ className: "", html: '<div class="pulse" style="--c:' + (f.tox ? U.toxColor(f.level) : U.css("--fire")) + '"></div>', iconSize: [0, 0] }) }).addTo(ring);
      }
    }
    map.on("zoomend", draw);
    return {
      set: function (list) { fires = list; draw(); },
      select: function (key) { selected = key; draw(); },
      destroy: function () { map.off("zoomend", draw); dots.remove(); pulses.remove(); ring.remove(); },
    };
  };

  // ---- the smoke path ------------------------------------------------------------------------------------------
  function offsetBand(coords, km) {
    // A band around the path that widens as the smoke travels (the same rule as the server: 1 km + 0.25 km per km).
    var left = [], right = [];
    for (var i = 0; i < coords.length; i++) {
      var a = coords[Math.max(0, i - 1)], b = coords[Math.min(coords.length - 1, i + 1)];
      var dx = (b[0] - a[0]) * Math.cos(coords[i][1] * Math.PI / 180), dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
      var nx = -dy / len, ny = dx / len, w = (1 + 0.25 * km[i]) / U.KM_PER_DEG;
      left.push([coords[i][1] + ny * w, coords[i][0] + (nx * w) / Math.cos(coords[i][1] * Math.PI / 180)]);
      right.push([coords[i][1] - ny * w, coords[i][0] - (nx * w) / Math.cos(coords[i][1] * Math.PI / 180)]);
    }
    return left.concat(right.reverse());
  }
  function lerpAt(path, t) {
    var ts = path.times, n = ts.length;
    if (t <= ts[0]) return path.coords[0];
    if (t >= ts[n - 1]) return path.coords[n - 1];
    var i = 0;
    while (i + 2 < n && ts[i + 1] < t) i++;
    var f = (t - ts[i]) / (ts[i + 1] - ts[i] || 1);
    return [path.coords[i][0] + f * (path.coords[i + 1][0] - path.coords[i][0]), path.coords[i][1] + f * (path.coords[i + 1][1] - path.coords[i][1])];
  }
  M.lerpAt = lerpAt;

  /**
   * One fire's smoke path: a widening band, a flowing line, time ticks and a moving head.
   * show(fire, {ticks}) draws it; setProgress(0..1) moves the head; play()/pause() animate it.
   * onProgress(cb) tells the page where the head is (to fill the slider and light up places).
   */
  M.smokeLayer = function (map) {
    var svg = L.svg({ padding: 0.5 });
    var group = L.layerGroup().addTo(map);
    var fire = null, head = null, trail = null, progress = 0, raf = null, last = 0, cb = null;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function timeAt(f) { var p = fire.path; return p.times[0] + f * (p.times[p.times.length - 1] - p.times[0]); }
    function place() {
      if (!fire) return;
      var t = timeAt(progress), at = lerpAt(fire.path, t);
      var upto = [[fire.lat, fire.lon]];
      fire.path.coords.forEach(function (c, i) { if (fire.path.times[i] <= t) upto.push([c[1], c[0]]); });
      upto.push([at[1], at[0]]);
      trail.setLatLngs(upto); head.setLatLng([at[1], at[0]]);
      cb && cb(progress, t);
    }
    function frame(now) {
      raf = requestAnimationFrame(frame);
      var dt = Math.min(100, now - (last || now)); last = now;
      progress += dt / 9000;
      if (progress >= 1) progress = 0;
      place();
    }
    var api = {
      show: function (f, o) {
        o = o || {};
        api.clear();
        if (!f || !f.path) return;
        fire = f;
        var color = f.tox ? U.toxColor(f.level) : U.css("--fire"), line = f.path.coords.map(function (c) { return [c[1], c[0]]; });
        L.polygon(offsetBand(f.path.coords, f.path.km), { renderer: svg, stroke: false, fillColor: color, fillOpacity: 0.16, interactive: false }).addTo(group);
        L.polyline(line, { renderer: svg, color: "#fff", weight: 8, opacity: 0.55, interactive: false }).addTo(group);
        L.polyline(line, { renderer: svg, color: color, weight: 4, opacity: 0.95, className: "flow-line", interactive: false }).addTo(group);
        trail = L.polyline(line.slice(0, 1), { renderer: svg, color: U.css("--fire"), weight: 6, opacity: 1, interactive: false }).addTo(group);
        // time marks every 3 hours: "+3 h", "+6 h" ...
        f.path.coords.forEach(function (c, i) {
          var hours = Math.round((f.path.times[i] - f.path.times[0]) / 3600000);
          if (hours > 0 && hours % 3 === 0) {
            var label = o.ticks === "clock" ? U.clock(f.path.times[i], 900000) : "+" + hours + " h";
            L.marker([c[1], c[0]], { interactive: false, keyboard: false, icon: L.divIcon({ className: "", html: '<span class="tick">' + label + "</span>", iconSize: [0, 0], iconAnchor: [-6, 8] }) }).addTo(group);
          }
        });
        head = L.marker(line[0], { interactive: false, keyboard: false, icon: L.divIcon({ className: "", html: '<div class="head-dot"></div>', iconSize: [0, 0] }) }).addTo(group);
        progress = o.progress || 0;
        place();
        if (o.fit !== false) map.fitBounds(L.latLngBounds(line).pad(0.35), { maxZoom: 9, animate: true });
      },
      setProgress: function (f) { progress = Math.max(0, Math.min(1, f)); place(); },
      play: function () { if (!raf && fire && !reduce) { last = 0; raf = requestAnimationFrame(frame); } },
      pause: function () { if (raf) cancelAnimationFrame(raf); raf = null; },
      playing: function () { return !!raf; },
      onProgress: function (fn) { cb = fn; },
      clear: function () { api.pause(); group.clearLayers(); fire = null; head = null; trail = null; },
      destroy: function () { api.clear(); group.remove(); },
      reducedMotion: reduce,
    };
    return api;
  };

  // ---- air quality -----------------------------------------------------------------------------------------------
  /** Measured stations as small coloured circles with the AQI number. */
  M.stationLayer = function (map, stations, onPick) {
    var group = L.layerGroup().addTo(map), pins = {};
    stations.forEach(function (s) {
      if (s.aqi == null) return;
      var k = U.aqiKey(s.aqi);
      var icon = L.divIcon({ className: "", iconSize: [30, 30], iconAnchor: [15, 15],
        html: '<div style="width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font:700 11px var(--font-display);background:' +
          U.aqiColor(k) + ";color:" + U.aqiInk(k) + ';border:2px solid var(--surface);box-shadow:0 1px 6px rgba(0,0,0,.45)">' + Math.round(s.aqi) + "</div>" });
      var m = L.marker([s.lat, s.lon], { icon: icon, riseOnHover: true, keyboard: true, title: s.name + " · AQI " + Math.round(s.aqi) }).addTo(group);
      m.on("click", function () { onPick && onPick(s); });
      pins[s.id] = m;
    });
    return { pins: pins, destroy: function () { group.remove(); } };
  };
  /**
   * The forecast as one smooth picture: every pixel is blended from the four nearest forecast points
   * (bilinear) and coloured along the CPCB colours, so there are no squares. setIndex(i) paints the i-th time.
   */
  var STOPS = [[25, "good"], [75, "satisfactory"], [150, "moderate"], [250, "poor"], [350, "very_poor"], [450, "severe"]];
  function rgb(hex) { var h = hex.replace("#", ""); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
  function mercY(lat) { return Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)); }
  function mercLat(y) { return ((2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180) / Math.PI; }
  M.forecastLayer = function (map, grid) {
    var half = grid.step / 2, CELL = 10;
    var latS = grid.south - half, latN = grid.south + (grid.rows - 1) * grid.step + half;
    var lonW = grid.west - half, lonE = grid.west + (grid.cols - 1) * grid.step + half;
    var W = grid.cols * CELL, mS = mercY(latS), mN = mercY(latN);
    var H = Math.round((W * (mN - mS)) / (((lonE - lonW) * Math.PI) / 180));
    var canvas = document.createElement("canvas"); canvas.width = W; canvas.height = H;
    var ctx = canvas.getContext("2d"), cache = {}, colors = null;
    function ramp() {
      colors = STOPS.map(function (s) { return [s[0], rgb(U.aqiColor(s[1]))]; });
    }
    function colorAt(v) {
      if (v <= colors[0][0]) return colors[0][1];
      for (var i = 1; i < colors.length; i++) if (v <= colors[i][0]) {
        var a = colors[i - 1], b = colors[i], f = (v - a[0]) / (b[0] - a[0]);
        return [a[1][0] + f * (b[1][0] - a[1][0]), a[1][1] + f * (b[1][1] - a[1][1]), a[1][2] + f * (b[1][2] - a[1][2])];
      }
      return colors[colors.length - 1][1];
    }
    function render(i) {
      var row = grid.aqi[i] || [], img = ctx.createImageData(W, H), d = img.data;
      for (var y = 0; y < H; y++) {
        var lat = mercLat(mN - ((y + 0.5) / H) * (mN - mS));
        var fr = Math.max(0, Math.min(grid.rows - 1, (lat - grid.south) / grid.step)), r0 = Math.floor(fr), r1 = Math.min(grid.rows - 1, r0 + 1), dr = fr - r0;
        for (var x = 0; x < W; x++) {
          var fc = Math.max(0, Math.min(grid.cols - 1, ((lonW + ((x + 0.5) / W) * (lonE - lonW)) - grid.west) / grid.step)), c0 = Math.floor(fc), c1 = Math.min(grid.cols - 1, c0 + 1), dc = fc - c0;
          var v00 = row[r0 * grid.cols + c0], v01 = row[r0 * grid.cols + c1], v10 = row[r1 * grid.cols + c0], v11 = row[r1 * grid.cols + c1];
          var w00 = (1 - dr) * (1 - dc), w01 = (1 - dr) * dc, w10 = dr * (1 - dc), w11 = dr * dc, w = 0, sum = 0;
          if (v00 != null) { w += w00; sum += w00 * v00; } if (v01 != null) { w += w01; sum += w01 * v01; }
          if (v10 != null) { w += w10; sum += w10 * v10; } if (v11 != null) { w += w11; sum += w11 * v11; }
          var o = (y * W + x) * 4;
          if (w < 0.01) { d[o + 3] = 0; continue; }
          var col = colorAt(sum / w);
          d[o] = col[0]; d[o + 1] = col[1]; d[o + 2] = col[2]; d[o + 3] = Math.round(255 * Math.min(1, w * 1.2));
        }
      }
      ctx.putImageData(img, 0, 0);
      return canvas.toDataURL("image/png");
    }
    var overlay = null;
    return {
      setIndex: function (i) {
        if (!colors) ramp();
        var url = cache[i] || (cache[i] = render(i));
        if (!overlay) overlay = L.imageOverlay(url, [[latS, lonW], [latN, lonE]], { opacity: 0.6, interactive: false, className: "fc-img" }).addTo(map);
        else overlay.setUrl(url);
      },
      destroy: function () { if (overlay) overlay.remove(); },
    };
  };
  /** The citizen's home: a pin and a ring (the "your area" ring). */
  M.homeLayer = function (map, home, radiusKm) {
    var group = L.layerGroup().addTo(map);
    L.circle([home.lat, home.lon], { radius: radiusKm * 1000, color: U.css("--brand"), weight: 2, dashArray: "6 6", fillColor: U.css("--brand"), fillOpacity: 0.06, interactive: false, className: "home-ring" }).addTo(group);
    L.marker([home.lat, home.lon], { interactive: false, keyboard: false, icon: L.divIcon({ className: "", html: '<div class="home-pin"></div>', iconSize: [0, 0] }) }).addTo(group);
    return { destroy: function () { group.remove(); } };
  };
})((window.PM = window.PM || {}));

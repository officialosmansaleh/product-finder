(function () {
  const DIMENSION_KEYS = new Set(["diameter", "luminaire_length", "luminaire_width", "luminaire_height"]);
  const TEMP_KEYS = new Set(["ambient_temp_min_c", "ambient_temp_max_c"]);
  const LUMEN_KEYS = new Set(["lumen_output", "lumen_output_value"]);

  function readAuthUser() {
    try {
      return window.ProductFinderAuth?.getUser?.() || window.ProductFinderQuoteUtils?.readSessionAuthUser?.() || null;
    } catch (_e) {
      return null;
    }
  }

  function isUnitedStatesUser(user) {
    const country = String((user || readAuthUser())?.country || "").trim().toLowerCase();
    return ["united states", "united states of america", "usa", "u.s.a.", "us", "u.s."].includes(country);
  }

  function normalizeNumberToken(token) {
    let s = String(token || "").trim();
    if (!s) return null;
    s = s.replace(/[^\d,.\-]/g, "");
    if (/^-?\d{1,3}(?:[.,]\d{3})+$/.test(s)) {
      s = s.replace(/[.,]/g, "");
    }
    const lastComma = s.lastIndexOf(",");
    const lastDot = s.lastIndexOf(".");
    if (lastComma >= 0 && lastDot >= 0) {
      s = lastComma > lastDot ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
    } else if (lastComma >= 0) {
      s = s.replace(",", ".");
    }
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }

  function formatNumber(n, maxDecimals) {
    if (!Number.isFinite(n)) return "";
    const decimals = Number.isInteger(n) ? 0 : maxDecimals;
    return n.toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimals,
    });
  }

  function replaceNumbers(value, converter, maxDecimals) {
    const source = String(value ?? "").trim();
    if (!source) return "";
    return source.replace(/-?\d+(?:[.,]\d+)?/g, (token) => {
      const n = normalizeNumberToken(token);
      if (n === null) return token;
      return formatNumber(converter(n), maxDecimals);
    });
  }

  function stripMetricUnit(value, unitPattern) {
    return String(value || "").replace(unitPattern, "").replace(/\s+/g, " ").trim();
  }

  function formatLengthValue(value) {
    const raw = String(value ?? "").trim();
    if (!raw) return "";
    const hasMetricUnit = /\b(?:mm|cm|m)\b/i.test(raw);
    const unit = /\bm\b/i.test(raw) && !/\b(?:mm|cm)\b/i.test(raw) ? "m" : /\bcm\b/i.test(raw) ? "cm" : "mm";
    const multiplier = unit === "m" ? 1000 : unit === "cm" ? 10 : 1;
    const withoutUnit = stripMetricUnit(raw, /\s*(?:mm|cm|m)\b/gi);
    const source = hasMetricUnit ? withoutUnit : raw;
    const first = normalizeNumberToken((source.match(/-?\d+(?:[.,]\d+)?/) || [])[0]);
    if (first !== null && first * multiplier >= 304.8 && !/[<>]=?|=/.test(source)) {
      return `${replaceNumbers(source, (n) => (n * multiplier) / 304.8, 2)} ft`;
    }
    return `${replaceNumbers(source, (n) => (n * multiplier) / 25.4, 2)} in`;
  }

  function formatTemperatureValue(value) {
    const raw = String(value ?? "").trim();
    if (!raw) return "";
    const source = stripMetricUnit(raw, /\s*(?:°?\s*C|celsius)\b/gi);
    return `${replaceNumbers(source, (n) => (n * 9) / 5 + 32, 1)} °F`;
  }

  function formatLumenValue(value) {
    const raw = String(value ?? "").trim();
    if (!raw) return "";
    const source = stripMetricUnit(raw, /\s*(?:lm|lumen|lumens)\b/gi);
    return `${replaceNumbers(source, (n) => n, 0)} lumens`;
  }

  function formatSpecValue(key, value, options) {
    const opts = options || {};
    if (opts.forceUs !== true && !isUnitedStatesUser(opts.user)) return String(value ?? "").trim();
    const cleanKey = String(key || "").trim();
    if (DIMENSION_KEYS.has(cleanKey)) return formatLengthValue(value);
    if (TEMP_KEYS.has(cleanKey)) return formatTemperatureValue(value);
    if (LUMEN_KEYS.has(cleanKey)) return formatLumenValue(value);
    return String(value ?? "").trim();
  }

  function labelForKey(key, label, options) {
    const opts = options || {};
    if (opts.forceUs !== true && !isUnitedStatesUser(opts.user)) return String(label || "");
    const cleanKey = String(key || "").trim();
    const base = String(label || "");
    if (DIMENSION_KEYS.has(cleanKey)) return base.replace(/\s*\((?:mm|cm|m)\)\s*$/i, "");
    if (TEMP_KEYS.has(cleanKey)) return base.replace(/°C|Celsius|\(C\)/gi, "°F");
    if (LUMEN_KEYS.has(cleanKey)) return base.replace(/\blm\b/gi, "lumens");
    return base;
  }

  window.ProductFinderMeasurements = {
    isUnitedStatesUser,
    formatSpecValue,
    labelForKey,
  };
})();

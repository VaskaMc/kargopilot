/**
 * KargoPilot v6.5 — Content Script for Trendyol, Temu, Starex, Camex, Limak, Dynamex, and SmartCustoms
 * Injects a non-intrusive 1-Click Quick-Bridge pill and strictly preserves SmartCustoms Read-Only Safe Mode.
 */
(function () {
  'use strict';

  var host = (window.location.hostname || '').toLowerCase();
  var isSmartCustoms = host.indexOf('customs.gov.az') !== -1;

  // Expose page metadata for popup inspection
  window.__KP_EXT_V65_META__ = {
    version: '6.5.0',
    hostname: host,
    read_only_safe_mode: true,
    declarations_created: 0,
    is_smartcustoms: isSmartCustoms
  };
})();

/**
 * KargoPilot v4.5 Enterprise Universal Dual-Hosting Connection Adapter
 * Manages dynamic runtime switching between Managed Cloud and Self-Hosted Sovereign editions,
 * health testing, live ping telemetry, and client-side data export.
 */
(function (global) {
  'use strict';

  var STORAGE_KEY_MODE = 'kp_connection_mode';
  var STORAGE_KEY_CUSTOM_URL = 'kp_custom_server_url';
  var STORAGE_KEY_CONSENT = 'kp_cloud_data_consent';
  var STORAGE_KEY_ONBOARDED = 'kp_dual_hosting_onboarded';

  var DEFAULT_CLOUD_URL = window.location.origin;
  var DEFAULT_SOVEREIGN_URL = 'http://127.0.0.1:48481';

  var ConnectionManager = {
    _listeners: [],

    getMode: function () {
      var mode = localStorage.getItem(STORAGE_KEY_MODE);
      return (mode === 'self-hosted') ? 'self-hosted' : 'cloud';
    },

    isOnboarded: function () {
      return localStorage.getItem(STORAGE_KEY_ONBOARDED) === 'true';
    },

    setOnboarded: function (val) {
      localStorage.setItem(STORAGE_KEY_ONBOARDED, val ? 'true' : 'false');
      this._emitChange();
    },

    getCustomUrl: function () {
      return localStorage.getItem(STORAGE_KEY_CUSTOM_URL) || DEFAULT_SOVEREIGN_URL;
    },

    hasDataConsent: function () {
      return localStorage.getItem(STORAGE_KEY_CONSENT) === 'true';
    },

    getBaseUrl: function () {
      if (this.getMode() === 'self-hosted') {
        var custom = this.getCustomUrl();
        return custom.replace(/\/+$/, '');
      }
      return DEFAULT_CLOUD_URL;
    },

    setMode: function (mode, customUrl, consent) {
      if (mode === 'self-hosted') {
        localStorage.setItem(STORAGE_KEY_MODE, 'self-hosted');
        if (customUrl) {
          var clean = customUrl.trim().replace(/\/+$/, '');
          if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
            clean = 'http://' + clean;
          }
          localStorage.setItem(STORAGE_KEY_CUSTOM_URL, clean);
        }
      } else {
        localStorage.setItem(STORAGE_KEY_MODE, 'cloud');
        if (typeof consent === 'boolean') {
          localStorage.setItem(STORAGE_KEY_CONSENT, consent ? 'true' : 'false');
        }
      }
      this.setOnboarded(true);
      this._emitChange();
    },

    testConnection: async function (targetUrl) {
      var rawUrl = (targetUrl || this.getBaseUrl()).trim().replace(/\/+$/, '');
      if (!rawUrl.startsWith('http://') && !rawUrl.startsWith('https://')) {
        rawUrl = 'http://' + rawUrl;
      }
      var testEndpoint = rawUrl + '/health';
      var startTime = Date.now();

      try {
        var controller = new AbortController();
        var timer = setTimeout(function () { controller.abort(); }, 4500);

        var res = await fetch(testEndpoint, {
          method: 'GET',
          signal: controller.signal,
          headers: { 'Accept': 'application/json' },
          cache: 'no-cache'
        });
        clearTimeout(timer);
        var latencyMs = Date.now() - startTime;

        if (res.ok) {
          var data = await res.json();
          return {
            ok: true,
            status: 'online',
            latencyMs: latencyMs,
            version: data.version || '4.5.0',
            edition: data.edition || (data.service ? 'sovereign' : 'cloud'),
            service: data.service || 'kargopilot-core',
            url: rawUrl,
            message: 'Server tapıldı və bağlantı uğurludur! (Cavab müddəti: ' + latencyMs + ' ms)'
          };
        } else {
          var errDetail = '';
          if (res.status === 404) {
            errDetail = 'Server tapıldı, lakin tələb olunan "/health" endpoint-i aşkar edilmədi. Zəhmət olmasa KargoPilot API ünvanını dəqiqləşdirin.';
          } else if (res.status === 401 || res.status === 403) {
            errDetail = 'Giriş məhdudlaşdırılıb (HTTP ' + res.status + '). API token və ya CORS icazələrini yoxlayın.';
          } else if (res.status >= 500) {
            errDetail = 'Server daxili xəta bildirdi (HTTP ' + res.status + '). Server loqlarını ("docker logs") nəzərdən keçirin.';
          } else {
            errDetail = 'Server ' + res.status + ' cavabı qaytardı. Zəhmət olmasa endpoint ünvanını və şəbəkə konfiqurasiyasını yoxlayın.';
          }
          return {
            ok: false,
            status: 'error',
            httpCode: res.status,
            latencyMs: latencyMs,
            url: rawUrl,
            message: errDetail
          };
        }
      } catch (err) {
        var isAbort = err.name === 'AbortError';
        return {
          ok: false,
          status: 'offline',
          url: rawUrl,
          message: isAbort
            ? 'Serverlə əlaqə zamanı gözləmə vaxtı aşımı (4.5s timeout). Serverin aktiv iş rejimində olduğunu və 48481 portunun əlçatanlığını yoxlayın.'
            : 'Serverə qoşulmaq mümkün olmadı. Narahat olmayın, məlumatlarınız qorunur. Ehtimal olunan səbəblər: 1) Yerli Docker xidməti işləmir ("docker ps" ilə yoxlayın); 2) Veb səhifə HTTPS üzərindədirsə, brauzer yerli HTTP bağlantısını (Mixed Content) bloklayır; 3) Firewall 48481 portunu bağlayır.'
        };
      }
    },

    exportData: async function () {
      var url = this.getBaseUrl() + '/api/export/data';
      try {
        var res = await fetch(url, { credentials: 'include' });
        if (!res.ok) {
          throw new Error('İxrac sorğusu uğursuz oldu: HTTP ' + res.status);
        }
        var blob = await res.blob();
        var downloadUrl = window.URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = downloadUrl;
        a.download = 'kargopilot_export_' + new Date().toISOString().slice(0, 10) + '.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        return { ok: true };
      } catch (err) {
        return { ok: false, error: err.message };
      }
    },

    subscribe: function (cb) {
      if (typeof cb === 'function') {
        this._listeners.push(cb);
      }
    },

    _emitChange: function () {
      var self = this;
      this._listeners.forEach(function (cb) {
        try { cb(self.getMode(), self.getBaseUrl()); } catch (e) {}
      });
      this.updateUIBadge();
    },

    updateUIBadge: function () {
      var mode = this.getMode();
      var baseUrl = this.getBaseUrl();
      var badges = document.querySelectorAll('[data-kp-connection-badge]');

      badges.forEach(function (el) {
        el.setAttribute('role', 'status');
        el.setAttribute('aria-live', 'polite');
        if (mode === 'cloud') {
          el.setAttribute('aria-label', 'Server bağlantı statusu: Bulud Serveri aktivdir');
          el.innerHTML =
            '<span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" aria-hidden="true"></span>' +
            '<span class="font-bold text-cyan-300">☁️ Bulud Serveri</span>' +
            '<span class="text-slate-400" aria-hidden="true">·</span>' +
            '<span class="text-slate-200">Rəsmi (7/24)</span>';
          el.className = el.className.replace(/border-[a-z0-9\/-]+/g, '') + ' border-cyan-500/30 bg-cyan-950/40';
        } else {
          var cleanHost = baseUrl.replace(/^https?:\/\//, '');
          el.setAttribute('aria-label', 'Server bağlantı statusu: Öz Serverim (' + cleanHost + ') aktivdir');
          el.innerHTML =
            '<span class="w-2 h-2 rounded-full bg-emerald-400" aria-hidden="true"></span>' +
            '<span class="font-bold text-emerald-300">🖥️ Öz Serverim</span>' +
            '<span class="text-slate-400" aria-hidden="true">·</span>' +
            '<span class="text-slate-200 truncate max-w-[120px]">' + cleanHost + '</span>';
          el.className = el.className.replace(/border-[a-z0-9\/-]+/g, '') + ' border-emerald-500/30 bg-emerald-950/40';
        }
      });
    }
  };

  // Auto-init badge on DOM load
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function () {
      ConnectionManager.updateUIBadge();
    });
  }

  global.KargoPilotConnection = ConnectionManager;
})(typeof window !== 'undefined' ? window : this);

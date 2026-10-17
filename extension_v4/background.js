/**
 * KargoPilot v6.5 — Background Service Worker (Manifest V3)
 * Handles background Quick-Bridge session dispatch and enforces SmartCustoms Read-Only Safe Mode.
 */
chrome.runtime.onInstalled.addListener(function () {
  chrome.storage.local.set({
    kp_version: '6.5.0',
    kp_mode: 'self-hosted',
    kp_server_url: 'http://127.0.0.1:48481',
    smartcustoms_read_only_safe_mode: true,
    declarations_created: 0
  });
});

chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
  if (!message || !message.action) return false;

  if (message.action === 'QUICK_BRIDGE_SYNC') {
    var serverUrl = (message.serverUrl || 'http://127.0.0.1:48481').replace(/\/+$/, '');
    var payload = {
      provider_type: message.provider_type || 'store',
      provider_key: message.provider_key || message.provider_code || 'trendyol',
      provider_name: message.provider_name || 'Trendyol',
      session_token: message.session_token || ('ext_v65_bg_' + Date.now()),
      account_identifier: message.account_identifier || 'extension_user@kargopilot.az',
      source: 'extension_v4',
      read_only_safe_mode: true
    };

    var headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
    if (message.authToken) {
      headers['Authorization'] = 'Bearer ' + message.authToken;
    }

    fetch(serverUrl + '/api/v1/user/sessions/quick-bridge', {
      method: 'POST',
      headers: headers,
      credentials: 'include',
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { sendResponse({ ok: true, data: data }); })
      .catch(function (err) { sendResponse({ ok: false, error: String(err) }); });

    return true;
  }
  return false;
});

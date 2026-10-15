/**
 * PCS Live Overlay — MV3 Content Script
 * Automatically injects the True Baku Landed Cost widget into Taobao, 1688, Trendyol, and Temu.
 */

(function () {
  if (window.__pcs_overlay_injected) return;
  window.__pcs_overlay_injected = true;

  const PCS_API_BASE = "http://127.0.0.1:48481";

  function detectPlatform() {
    const host = window.location.hostname.toLowerCase();
    if (host.includes("taobao.com")) return "Taobao";
    if (host.includes("1688.com")) return "1688";
    if (host.includes("trendyol.com")) return "Trendyol";
    if (host.includes("temu.com")) return "Temu";
    return "Unknown";
  }

  function extractProductInfo(platform) {
    let title = document.title || "Məhsul";
    let price = 0.0;
    let currency = "USD";

    if (platform === "Trendyol") {
      currency = "TRY";
      const prElem = document.querySelector(".prc-dsc, .product-price, .featured-price");
      if (prElem) {
        const txt = prElem.innerText.replace("TL", "").replace(".", "").replace(",", ".").trim();
        price = parseFloat(txt) || 0.0;
      }
    } else if (platform === "Taobao" || platform === "1688") {
      currency = "CNY";
      const prElem = document.querySelector(".price, .tb-rmb-num, [class*='price']");
      if (prElem) {
        const txt = prElem.innerText.replace("¥", "").replace(",", "").trim();
        price = parseFloat(txt) || 0.0;
      }
    } else if (platform === "Temu") {
      currency = "AZN";
      const prElem = document.querySelector("._3c_price, [data-tooltip*='AZN'], [class*='price']");
      if (prElem) {
        const txt = prElem.innerText.replace("AZN", "").replace("₼", "").replace(",", ".").trim();
        price = parseFloat(txt) || 0.0;
      }
    }

    return { platform, title, price, currency };
  }

  function injectOverlay(info) {
    const container = document.createElement("div");
    container.id = "pcs-live-overlay-root";
    container.innerHTML = `
      <div class="pcs-overlay-card">
        <div class="pcs-overlay-header">
          <span class="pcs-logo">⚡ PCS v4.0</span>
          <span class="pcs-badge">${info.platform}</span>
          <button class="pcs-close-btn" id="pcs-close-btn">×</button>
        </div>
        <div class="pcs-overlay-body">
          <div class="pcs-row">
            <span class="pcs-label">Orijinal Qiymət:</span>
            <span class="pcs-val">${info.price.toFixed(2)} ${info.currency}</span>
          </div>
          <div class="pcs-row pcs-highlight">
            <span class="pcs-label">Tam Bakı Maya Dəyəri:</span>
            <span class="pcs-val pcs-strong" id="pcs-landed-cost">Hesablanır...</span>
          </div>
          <div class="pcs-row">
            <span class="pcs-label">Tövsiyə olunan Kargo:</span>
            <span class="pcs-val" id="pcs-best-carrier">Starex / Camex</span>
          </div>
          <div class="pcs-actions">
            <button class="pcs-btn pcs-btn-primary" id="pcs-autofill-btn">⚡ 1-Kliklə Ünvanı Doldur</button>
            <button class="pcs-btn pcs-btn-secondary" id="pcs-watch-btn">📉 Qiymət Düşməsini İzlə</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(container);

    document.getElementById("pcs-close-btn")?.addEventListener("click", () => {
      container.style.display = "none";
    });

    // Fetch landed cost estimate from PCS local API
    fetch(`${PCS_API_BASE}/v4/api/arbitrage/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        offers: [{
          platform: info.platform,
          origin_country: info.platform === "Trendyol" ? "TR" : (info.platform === "Temu" ? "DIRECT_AZ" : "CN"),
          item_price: info.price || 50.0,
          currency: info.currency,
          estimated_weight_kg: 0.5,
        }]
      })
    })
    .then(r => r.json())
    .then(data => {
      if (data.quotes && data.quotes.length > 0) {
        const q = data.quotes[0];
        document.getElementById("pcs-landed-cost").innerText = `${q.net_landed_cost_azn.toFixed(2)} AZN`;
        document.getElementById("pcs-best-carrier").innerText = `${q.recommended_carrier} (${q.estimated_days} gün)`;
      }
    })
    .catch(() => {
      // Fallback local estimation if API connection offline
      const rate = info.currency === "TRY" ? 0.0485 : (info.currency === "CNY" ? 0.238 : 1.70);
      const estAzn = (info.price * rate) + (info.platform === "Temu" ? 0 : 7.50);
      document.getElementById("pcs-landed-cost").innerText = `~${estAzn.toFixed(2)} AZN`;
    });

    document.getElementById("pcs-autofill-btn")?.addEventListener("click", () => {
      window.open(`${PCS_API_BASE}/carriers`, "_blank");
    });
  }

  const platform = detectPlatform();
  if (platform !== "Unknown") {
    setTimeout(() => {
      const info = extractProductInfo(platform);
      injectOverlay(info);
    }, 1500);
  }
})();

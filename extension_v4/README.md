# KargoPilot v6.5 — `extension_v4` (1-Klik Quick-Bridge Brauzer Uzantısı)

**Versiya:** `6.5.0` (Manifest V3)

## Xüsusiyyətlər
- **1-Kliklə Sessiya Körpüsü (`POST /api/v1/user/sessions/quick-bridge`):** Trendyol, Temu, Starex, Camex, Limak, Dynamex və SmartCustoms saytlarında aktiv sessiyanı DevTools açmadan birbaşa seçilmiş serverə (`☁️ Bulud Serveri` və ya `🖥️ Öz Serverim http://127.0.0.1:48481`) təhlükəsiz şifrələnmiş formada ötürür.
- **SmartCustoms Bəyannaməsiz Təhlükəsiz Oxuma Rejimi (`read_only_safe_mode: True`):** SmartCustoms üzrə heç bir halda avtomatik bəyannamə yaradılmır və göndərilmir (`declarations_created: 0`); yalnız əlaqənin aktuallığı və 300 USD rüsumsuz DGK kvotası yoxlanılır.
- **4-Kanallı Əlaqə Sağlamlığı Matrisi (`GET /api/v1/user/channels/health-summary`):** Mağaza, Kargo, SmartCustoms (Read-Only) və WhatsApp şlüzlərinin canlı statusunu birbaşa uzantı pəncərəsində göstərir.

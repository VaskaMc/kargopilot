# ⚡ KargoPilot v5.5 Enterprise: Tam Memarlıq, Təhlükəsizlik və Funksionallıq Spesifikasiyası

**Sənəd Növü:** Rəsmi Sistem Spesifikasiyası və Təhlükəsizlik Arxitekturası  
**Versiya:** v5.5.0 Enterprise Release  
**Tarix:** 17 Oktyabr 2026  
**Müəllif:** Vasif Məcidli (Təsisçi & Baş Mühəndis) & Antigravity Agency Agent Squad  
**GitHub Repozitoriyası:** [https://github.com/VaskaMc/kargopilot](https://github.com/VaskaMc/kargopilot)  
**Canlı Portal:** [https://vaskamc.github.io/kargopilot](https://vaskamc.github.io/kargopilot)  
**Test Göstəricisi:** 85/85 Lokal Test (%100 Yaşıl) | 47/47 VPS İnteqrasiya Testi (%100 Yaşıl)

---

## 1. Giriş və Layihənin Təyinatı

**KargoPilot v5.5**, Azərbaycanın transsərhəd e-ticarət (Türkiyə, Çin, ABŞ, Avropa) və beynəlxalq logistika bazarı üçün hazırlanmış, süni intellekt dəstəkli avtonom kargo idarəetməsi, interaktiv sessiya anbarı və Dövlət Gömrük Komitəsinin (DGK) SmartCustoms avtomatlaşdırma platformasıdır.

Sistem istifadəçilərə daşıyıcı kargo şirkətləri (Starex, Expargo, Camex, Dynamex, Limak və s.) və xarici satıcı mağazaları (Trendyol, Temu, Amazon və s.) arasında real vaxt rejimində qiymət arbitrajı aparmağa, fərdi $300 USD rüsumsuz gömrük kvotasını nəzarətdə saxlamağa və tək kliklə rəsmi gömrük bəyannaməsi verməyə imkan yaradır.

---

## 2. İkili Yerləşdirmə Memarlığı (Dual-Hosting Architecture)

KargoPilot v5.5 məlumatların məxfiliyinə tam zəmanət verən və istifadəçilərin seçiminə hörmət edən iki fərqli rejimdə təqdim olunur:

```
                            ┌──────────────────────────────────────────────┐
                            │          KargoPilot v5.5 Platforması         │
                            └──────────────────────┬───────────────────────┘
                                                   │
                       ┌───────────────────────────┴───────────────────────────┐
                       ▼                                                       ▼
         ┌───────────────────────────┐                           ┌───────────────────────────┐
         │  Variant 1: MÜSTƏQİL      │                           │  Variant 2: BULUD         │
         │  Server (Self-Hosted)     │                           │  İdarəetməli (Cloud)      │
         ├───────────────────────────┤                           ├───────────────────────────┤
         │ • 100% Müstəqil VPS / PC  │                           │ • 7/24 Yüksək Əlçatanlıq  │
         │ • Sıfır Telemetriya       │                           │ • Avtomatik Arxa Fond     │
         │ • Şəxsi AES-256 Vault     │                           │   Sinxronizasiyası        │
         │ • Yerli SQLite WAL Bazası │                           │ • Təhlükəsiz Şifrələmə    │
         │ • Açıq Mənbə Nüvəsi       │                           │ • Daimi Yenilənmələr      │
         │ • Tam İxrac / İdxal / Sil │                           │ • Çoxistifadəçili Portal  │
         └───────────────────────────┘                           └───────────────────────────┘
```

### 2.1. Müstəqil Server (Self-Hosted / On-Premise)
- **Təyinatı:** Fərdi məlumatlarını (FİN kodlar, şifrələr, bağlama qaimələri) heç bir xarici serverə göndərmək istəməyən korporativ şirkətlər, dropshipperlər və qabaqcıl istifadəçilər.
- **İnfrastruktur:** İstifadəçinin öz serverində (Linux/Windows) və ya yerli mühitində işləyir. Bütün verilənlər bazası və Fernet şifrələmə açarları yalnız lokal serverdə saxlanılır.
- **Məlumat Müstəqilliyi və Portativliyi:** Tam JSON İxracı (Data Export), Təhlükəsiz İdxalı (Data Import) və Hesabın Bir Dəfəlik Təmizlənməsi (Account Wipe — Right to be Forgotten) imkanı.

### 2.2. Bulud İdarəetməli (Cloud Managed SaaS)
- **Təyinatı:** Texniki server quraşdırması ilə məşğul olmadan, brauzerdən dərhal istifadə etmək istəyən fərdi şəxslər və ailələr.
- **Təhlükəsizlik:** Hər bir istifadəçinin sessiya məlumatları Fernet AES-256 zərf şifrələməsi ilə bazada qorunur və xarici API sorğularında yalnız maskalanmış (`****`) şəkildə ötürülür.

---

## 3. Əsas Funksional Modullar (v5.5)

### 3.1. Xarici Sessiya Anbarı (Interactive Session Vault)
- **Modul:** `web_panel/app/routers/user_api.py` (`/sessions/*`)
- **Dəstəklənən Platformalar:** Trendyol, Temu, Amazon, Starex, Expargo, Camex, SmartCustoms.
- **Təhlükəsizlik Xüsusiyyətləri:**
  - `session_payload_encrypted`: Hər bir kuki və token açar verilənlər bazasında Fernet (AES-128-CBC + HMAC-SHA256) ilə şifrələnir.
  - `mask_identifier`: İstifadəçi identifikatorları interfeysdə və JSON cavablarında maskalanır (məsələn: `u***r@example.com`, `99450***1234`).
  - **Zero IP/PII Leak:** Canlı infrastruktur IP-ləri və fərdi sirlər heç vaxt açıq çıxışa buraxılmır.
  - **SSRF və IDOR Mühafizəsi:** Daxili şəbəkələrə (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, AWS metadata `169.254.169.254`) edilən cəhdlər dərhal bloklanır.

### 3.2. 1-Kliklə SmartCustoms Gömrük Bəyannaməsi
- **Hüquqi Əsas:** Azərbaycan Respublikası Nazirlər Kabinetinin 305 nömrəli Qərarı.
- **İş Prinsipi:** İstifadəçi sifariş etdiyi bağlamanı tək kliklə Dövlət Gömrük Komitəsinin sisteminə göndərə bilər.
- **Xüsusiyyətlər:** Avtomatik invoys generasiyası, SmartCustoms bəyanat statusunun izlənməsi (`bəyan edilib`, `gözləmədə`) və DGK kateqoriyalarının təyini.

### 3.3. Smart Arbitraj (Ağıllı Kargo Daşıyıcı Müqayisəsi)
- **Modul:** `POST /api/v1/user/arbitrage/calculate`
- **Məntiq:** 
  $$\text{Hesablanan Çəki} = \max\left(\text{Faktiki Çəki}, \frac{\text{Uzunluq} \times \text{En} \times \text{Hündürlük}}{6000}\right)$$
- **Valyuta:** USD və Mərkəzi Bankın (CBAR) rəsmi məzənnəsi (1.7000 AZN) üzrə canlı hesablama.
- **Nəticə:** Daşıyıcıların qiymət sıralaması, ən sərfəli (`best_value`) və ən sürətli variantın tövsiyəsi, qənaət edilən məbləğ (`savings_usd`, `savings_azn`).

### 3.4. Customs Supervisor (DGK 300$ Rüsumsuz Limit Nəzarəti)
- **Modul:** `GET /api/v1/user/customs/supervisor` və `POST /api/v1/user/customs/simulate-duty`
- **İş Prinsipi:** İstifadəçinin və onun qeydiyyatdan keçmiş ailə FİN kodlarının son 30 günlük dövriyyəsini hesablayır.
- **Təhlükə Şkalası:**
  - Yaşıl: Xərclənən < 250 USD (Təhlükəsiz zona).
  - Sarı: 250 – 290 USD (Xəbərdarlıq zonası).
  - Qırmızı: > 290 USD (Yüksək risk zonası, rüsum təhlükəsi).
- **Vahid Gömrük Rüsumu:** 300 USD limiti aşıldıqda aşılan məbləğə 36% vahid gömrük rüsumu + 15 AZN rəsmiləşdirmə haqqı avtomatik hesablanır.

### 3.5. AI Copilot (Azərbaycan Dilində Sərbəst Logistika Köməkçisi)
- **Modul:** `POST /api/v1/user/ai/chat`
- **Qabiliyyətlər:** İstifadəçinin bağlamalarının cari vəziyyətini, qadağan olunmuş malların siyahısını (dronlar, tezalışan mayelər, xüsusi avadanlıqlar) və gömrük qanunvericiliyini təhlil edərək Azərbaycan dilində peşəkar tövsiyələr verir.

### 3.6. Satıcılar və Daşıyıcılar Ekosistem Mərkəzi
- **Modul:** `/stores` və `/carriers` idarəetməsi.
- İstifadəçilər standart satıcılar (Trendyol, Temu, Amazon, Zara və s.) ilə yanaşı öz şəxsi dükanlarını və istədikləri kargo şirkətlərini platformaya inteqrasiya edə bilərlər.

---

## 4. Rəsmi Qiymət Modelləri (Tariflər)

Platforma həm fərdi alıcılar, həm peşəkar e-ticarət sahibkarları, həm də iri korporasiyalar üçün aydın və şəffaf qiymət modeli təklif edir:

| Plan | Qiymət | Əsas İmkanlar | Hədəf Auditoriya |
| :--- | :--- | :--- | :--- |
| **Fərdi Müştəri** | **Pulsuz (0 AZN / Həmişəlik)** | Şəxsi bağlamaların uçotu, Smart Arbitraj tarif kalkulyatoru, DGK 300$ kvota nəzarəti, əsas kargo izləməsi. | Ayda 1-5 bağlama sifariş edən fərdi vətəndaşlar |
| **Dropshipper** | **49 AZN / ay** | Çoxsaylı satıcı saytlarının inteqrasiyası, toplu gömrük bəyannamələri, xarici sessiya anbarı və avtomatik sinxronizasiya, prioritet AI Copilot dəstəyi. | Onlayn mağaza sahibləri, dropshipperlər və mikro-bizneslər |
| **Korporativ (Müstəqil Server)** | **590 AZN birdəfəlik + 119 AZN / il** | Müstəqil serverdə 100% lokal işləmə, limitsiz istifadəçi və bağlama, sıfır telemetriya, şəxsi loqo/brendinq, illik rəsmi yenilənmə və texniki dəstək. | Logistika şirkətləri, kuryer xidmətləri, iri idxalatçılar və korporativ müəssisələr |

---

## 5. Canlı Test və Nümayiş Hesabı (Demo Account)

Platformanın bütün imkanlarını canlı mühitdə dərhal sınaqdan keçirmək üçün rəsmi nümayiş hesabı aktivdir:

- **Daxilolma URL:** `/login` (və ya canlı portal vasitəsilə)
- **E-poçt:** `demo@kargopilot.az`
- **Şifrə:** `***REMOVED***`
- **FİN Kod:** `7KP2026`
- **Tərkib:** Aktiv Trendyol, Starex və SmartCustoms sessiyaları, həm bəyan edilmiş, həm də bəyannamə gözləyən nümunə bağlamalar, aktiv DGK rüsumsuz limit şkalası və AI Copilot dialoqu.

---

## 6. Müstəqil Serverdə Quraşdırma (Self-Hosted Quickstart)

```bash
# 1. Repozitoriyanı klonlayın
git clone https://github.com/VaskaMc/kargopilot.git
cd kargopilot

# 2. Virtual mühiti yaradın və aktivləşdirin
python -m venv .venv
source .venv/bin/activate  # Windows üçün: .venv\Scripts\activate

# 3. Asılılıqları quraşdırın
pip install -r requirements.txt

# 4. Mühit konfiqurasiyasını təyin edin
cp .env.sovereign.example .env

# 5. Avtomatlaşdırılmış testləri yoxlayın
python -m pytest tests/

# 6. Veb paneli işə salın
uvicorn web_panel.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 7. Təhlükəsizlik və Keyfiyyət Təminatı (Zero-Leak Policy)

KargoPilot v5.5 **10 ixtisaslaşmış agentdən ibarət təhlükəsizlik auditi** tərəfindən yoxlanılmışdır:
1. **Sıfır IP və Şəxsi Məlumat Sızması:** Repozitoriyada heç bir daxili server IP-si, SSH portu və ya şəxsi əlaqə nömrəsi mövcud deyil.
2. **Kriptoqrafik Qorunma:** Sessiyalar və şifrələr Fernet və Argon2id ilə qorunur.
3. **IDOR və SSRF Təcridi:** Bütün istifadəçi resursları yalnız autentifikasiya olunmuş sessiya sahibinə aiddir və kənar server çağırışları təhlükəsiz filtrlərdən keçirilir.

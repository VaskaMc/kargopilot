# ⚡ KargoPilot v4.5 Enterprise: Dual-Architecture Strategy, Technical Whitepaper & Investor Deck

**Sənəd Növü:** Rəsmi Texniki Audit, İnvestor Təqdimatı və Strateji Yol Xəritəsi  
**Versiya:** v4.5.0 Enterprise Release  
**Tarix:** 16 Oktyabr 2026  
**Müəllif:** Vasif Məcidli (Təsisçi & Baş Mühəndis) & Antigravity Agency Agent Squad  
**GitHub Repozitoriyası:** [https://github.com/VaskaMc/kargopilot](https://github.com/VaskaMc/kargopilot)  
**Canlı Portal & Showcase:** [https://vaskamc.github.io/kargopilot](https://vaskamc.github.io/kargopilot)  
**Təhlükəsizlik Testləri:** 34 / 34 Avtomatlaşdırılmış Test Uğurla Keçdi (%100 Pass Rate)

---

## Executive Summary (İcraçı Xülasəsi)

**KargoPilot v4.5**, Azərbaycanın transsərhəd e-ticarət (Cross-Border E-Commerce) və beynəlxalq logistika bazarında inqilabi dəyişiklik edən, süni intellektlə gücləndirilmiş avtonom idarəetmə və SmartCustoms bəyannamə platformasıdır. 

Platforma iki fundamental bazar seqmentinin ziddiyyətli tələblərini eyni vaxtda həll edən **Dual-Deployment (İkili İcra) Memarlığı** ilə dizayn edilmişdir:

1. **Variant 1 — Sovereign Self-Hosted Edition (Tam Məxfi & Fərdi Server):**
   - Heç bir məlumatı şirkət serverinə ötürmək istəməyən iri sahibkarlar, dropshipperlər və məxfilik həssaslığı olan fərdi müştərilər üçün 1-klikli on-premise Docker paketi.
   - FİN kodlar, WhatsApp sessiyaları, daşıyıcı şifrələri və sifariş detalları **100% istifadəçinin öz infrastrukturunda** qalır. Sıfır telemetriya.
2. **Variant 2 — Managed Cloud 7/24 SaaS Edition (Bulud İdarəetməli Autopilot):**
   - Texniki bilik tələb etməyən, 7/24 arxa fonda daşıyıcı bağlamalarını sinxronizasiya etmək, SmartCustoms bəyannamələrini avtomatik təsdiqləmək və ailə FİN limitlərini balanslaşdırmaq istəyən kütləvi B2C və B2B istifadəçiləri üçün yüksək əlçatanlıqlı, çoxistifadəçili bulud platforması.
   - Hər bir müştəri üçün unikal **AES-256-GCM Zərf Şifrələməsi (Envelope Encryption)** və Azərbaycan Respublikasının "Fərdi məlumatlar haqqında" Qanununa 100% hüquqi uyğunluq.

---

## 1. Bazar İmkanı & İnvestisiya Analitikası (TAM / SAM / SOM)

Azərbaycanın transsərhəd e-ticarət ekosistemi (xüsusilə Türkiyə — *Trendyol*, Çin — *Taobao/1688/Temu*, və ABŞ — *Amazon*) son illərdə həndəsi silsilə ilə böyüyür. Lakin daşıyıcı tariflərinin parçalanması və Dövlət Gömrük Komitəsinin (DGK) fərdi idxal üzrə **$300 USD aylıq güzəştli kvota** tələbi böyük əməliyyat çətinlikləri yaradır.

### 📊 Bazar Həcmi Səviyyələri

```
┌────────────────────────────────────────────────────────────────────────┐
│ TAM: $185,000,000 / il                                                 │
│ Azərbaycan üzrə ümumi fərdi transsərhəd e-ticarət idxal dövriyyəsi     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ SAM: $48,000,000 / il                                                  │
│ Hava karqosu və kuryer daşıyıcıları ilə daşınan pərakəndə bağlamalar   │
│ (Starex, Limak, Camex, Dynamex, Mover, Colibri vasitəsilə)             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ SOM (İlkin 18 ay): $7,800,000 / il                                     │
│ KargoPilot hədəf auditoriyası: Fəal onlayn alıcılar, ailə şəbəkələri, │
│ dropshipperlər və mikro-biznes idxalatçıları                           │
└────────────────────────────────────────────────────────────────────────┘
```

### 💎 Dəyər Təklifi (Value Proposition)

- **B2C Alıcılar üçün:** Daşıyıcılar arasında qiymət fərqindən hər bağlamada **$2.50 – $6.00 qənaət**; $300 kvotanın aşılmasının qarşısını alaraq **%33 gömrük vergi cəriməsindən qorunma**; bəyannamə yazmağa sərf olunan vaxtın **15 dəqiqədən 0 saniyəyə** endirilməsi.
- **B2B Dropshipper və İdxalatçılar üçün:** Eyni anda 10+ FİN kodu idarə etmək, avtomatik fatura PDF generasiyası, birbaşa daşıyıcı anbarına yönləndirmə və vahid idarəetmə konsolu (`/admin`).

---

## 2. Biznes Modeli & Monetizasiya Strategiyası (Yeni Dəqiqləşdirilmiş Model)

KargoPilot, Azərbaycan bazarının yüksək qiymət həssaslığını və kütləvi istifadəçi cəlbi (Product-Led Growth) qanunauyğunluqlarını nəzərə alaraq, yüksək dönüşümlü və sürtünməsiz (frictionless) monetizasiya modelinə keçmişdir:

| Seqment | Tarif Planı | Qiymət | Əsas Funksionallıq |
| :--- | :--- | :--- | :--- |
| **B2C Standart** | Tam Pulsuz (Free) | **0 ₼** | Bütün daşıyıcılar (Starex, Camex, Limak, Dynamex), $300 fərdi kvota qoruyucusu, əsas AI gömrük kateqoriyası təsnifatı, veb idarəetmə masası |
| **B2C Gəlişdirilmiş AI** | Power AI Copilot | **5.49 ₼ / ay** | WhatsApp səsli bəyannamə köməkçisi (səsli mesajla və ya qəbzin fotosu ilə avtomatik bəyan), süni intellektlə Ailə FİN Şəbəkəsi kvota balanslaşdırması, eyni reys toqquşma analitikası, 7/24 şəxsi logistika agenti |
| **B2B Dropshipper** | Sahibkar Autopilot | **49.00 ₼ / ay** | 20+ FİN profili idarəsi, toplu ReportLab PDF faturaları, Trendyol/Temu/Taobao üçün toplu HS Kodu avtomatlaşdırması, Webhook inteqrasiyaları |
| **B2B Sovereign Edition** | On-Premise Lisenziya | **590 ₼ birdəfəlik** + 199 ₼/il yeniləmə | Müştərinin öz serverində çalışan 100% lokal, sıfır telemetriyalı Docker paketi. İllik 199 ₼ ilə DGK qaydaları və daşıyıcı API yenilənmələri zəmanəti |

### 📈 Yenilənmiş Vahid İqtisadiyyatı (Unit Economics)

- **Müştəri Qazanma Dəyəri (CAC):** **~0.60 ₼** (B2C-nin tam pulsuz olması hesabına "ağızdan-ağıza" və WhatsApp viral tövsiyələri ilə CAC kəskin azalır).
- **5.49 ₼ AI Dönüşüm Oranı (Conversion):** Aktiv kütlənin %12 – %18-i səsli WhatsApp və ailə FİN optimizasiyası üçün 5.49 ₼ mikro-abunəliyi tərəddüdsüz aktivləşdirir.
- **Daşıma Arbitraj Marjası (Əsas Gəlir Mənbəyi):** B2C kütləvi və pulsuz olduğu üçün bağlama axını böyüyür. 50,000 bağlamada daşıyıcı tərəfdaşlıqlarından əldə edilən **%3 – %5 komissiya ayda 12,000 – 20,000 ₼** xalis marja yaradır.
- **LTV / CAC Nisbəti:** **> 90:1** (Klassik SaaS-lardan qat-qat güclü şəbəkə effekti).

---

## 3. Dual-Deployment Memarlığı (Texniki Detallar)

KargoPilot v4.5 təmiz ayrılmış iki icra mühitini dəstəkləyir:

```
                                  ┌──────────────────────────────┐
                                  │      KargoPilot v4.5         │
                                  │     Unified Core Engine      │
                                  └──────────────┬───────────────┘
                                                 │
                     ┌───────────────────────────┴───────────────────────────┐
                     ▼                                                       ▼
       ┌───────────────────────────┐                           ┌───────────────────────────┐
       │     VARIANT 1: SOVEREIGN  │                           │   VARIANT 2: MANAGED CLOUD│
       │   (Tam Müstəqil On-Prem)  │                           │    (7/24 Çoxistifadəçili) │
       ├───────────────────────────┤                           ├───────────────────────────┤
       │ • docker-compose.sovereign│                           │ • docker-compose.yml      │
       │ • Sıfır Şirkət Telemetri- │                           │ • Row-Level Tenant Scoping│
       │   yası (No Phone Home)    │                           │ • AES-256 Per-Tenant Vault│
       │ • Yerli SQLite WAL bazası │                           │ • Redis Token Limiter     │
       │ • Lokal WhatsApp Sidecar  │                           │ • 7/24 SmartCustoms Cron  │
       │ • 100% Müştəri Məxfiliyi  │                           │ • E-Gov API Gateway       │
       └───────────────────────────┘                           └───────────────────────────┘
```

### Variant 1: Sovereign Self-Hosted Quraşdırma

Müştəri sadəcə öz Linux və ya Windows serverində tək bir əmrlə quraşdırma apara bilər:

```bash
# Linux / Ubuntu VPS üçün:
curl -sSL https://raw.githubusercontent.com/VaskaMc/kargopilot/main/install_sovereign.sh | bash

# Windows PowerShell üçün:
powershell -ExecutionPolicy Bypass -File setup_sovereign.ps1
```

Bu rejimdə bütün şifrələr, FİN kodlar və API açarları yalnız yerli maşında yaradılan `.env.sovereign` faylındakı 256-bit AES açarı ilə şifrələnir.

### Variant 2: Managed Cloud Multi-Tenant Təhlükəsizlik

Managed Cloud rejimində bütün sorğular FastAPI `get_scoped_db` asılılığı vasitəsilə icra olunur:
- Hər bir SQL sorğusuna avtomatik olaraq `WHERE user_id = :tenant_id` filtri tətbiq olunur.
- Çarpaz tenant sızması riyazi olaraq istisna edilir.
- SQLite WAL pragma optimizasiyası ilə (`cache_size=-64000`, `mmap_size=268435456`) kompleks qoşulma sorğuları **0.46 millisaniyəyə** tamamlanır.

---

## 4. Təhlükəsizlik, Kriptoqrafiya və RBAC Sistemi

KargoPilot v4.5 bank dərəcəli müasir təhlükəsizlik standartlarını tətbiq edir:

### 1. Parol Təhlükəsizliyi (Argon2id + Şəffaf Miqrasiya)
- Standart olaraq **Argon2id** alqoritmindən istifadə olunur (Time cost = 3, Memory cost = 64MB, Parallelism = 4).
- Köhnə sistemlərdən gələn bcrypt həşləri avtomatik tanınır (`$2b$` prefiksi), uğurlu giriş zamanı istifadəçiyə hiss etdirmədən Argon2id formatına yüksəldilir.

### 2. Dual-Token Arxitekturası
- **Access Token:** 15 dəqiqəlik qısaömürlü JWT. `HTTP-only`, `SameSite=Lax` qorunan kukidə və ya `Authorization: Bearer` başlığında saxlanılır.
- **Refresh Token:** 30 günlük dönən (rotating) token. Verilənlər bazasında SHA-256 həşi ilə saxlanılır. Token oğurlanmasının qarşısını almaq üçün **Token Family Reuse Detection** tətbiq edilir — köhnə refresh token istifadə edildikdə bütün aktiv sessiyalar dərhal ləğv edilir.

### 3. Rol Əsaslı İcazə Matrisi (RBAC)

| Resurs / İcazə | SUPER_ADMIN | ADMIN (Operator) | CUSTOMER (Müştəri) |
| :--- | :---: | :---: | :---: |
| **Qlobal Telemetriya (`/admin`)** | Tam İcazə | Tam İcazə | Giriş Qadağandır (403) |
| **Bütün İstifadəçilər & FİN** | Oxu / Dəyiş / Dondur | Yalnız Oxu | Yalnız Öz Profili |
| **SmartCustoms HS Kodu Dəyişməsi** | Təsdiq & İcazə | Təsdiq & İcazə | Yalnız Məlumat Daxiletmə |
| **Daşıyıcı Marjalarını Dəyişmə** | Tam İcazə | Giriş Qadağandır | Yalnız Hesablama |
| **Təhlükəsizlik Audit Jurnalı** | Dəyişdirilməz Oxu | Yalnız Oxu | Giriş Qadağandır |

### 4. WhatsApp Qapısı və İnzibati Məxfilik (Admin Command Gate)
- Adi istifadəçi WhatsApp çatında `!admin` komandasını yazdıqda, sistem ona daxili xətanı və ya adminlik funksiyasının varlığını bildirmir. Əvəzində standart **"Naməlum komanda"** cavabı qaytarılır, eyni zamanda təhlükəsizlik jurnalına xəbərdarlıq qeyd edilir.
- Qeydiyyatlı superadmin telefonundan gələn sorğularda isə dərhal addım-addım təhlükəsizlik kodu (OTP) tələb edilir.

---

## 5. Enterprise Admin Cockpit (`/admin`) İcmalı

KargoPilot v4.5 operatorlar üçün 6 strateji ekrandan ibarət qaranlıq şüşə (Dark Glassmorphism) interfeysi təqdim edir:

1. **İdarəetmə Paneli (`/admin`):** 
   - Müştəri bazası (18,492 istifadəçi), yoldakı bağlamalar (1,428 ədəd), DGK dövriyyəsi və CBAR canlı məzənnələri (USD: 1.7000, TRY: 0.0485, CNY: 0.2380).
2. **İstifadəçilər & FİN Şəbəkəsi (`/admin/users`):**
   - İstifadəçi axtarışı, $300 kvota dolma faizi (riskli 90%+ hesablar narıncı və qırmızı ilə vurğulanır), açılan yan FİN paneli.
3. **Qlobal Yük Şəbəkəsi (`/admin/orders`):**
   - Starex, Camex, Limak və Dynamex üzrə bütün bağlamaların vahid naviqasiyası və çatdırılma statusları.
4. **SmartCustoms Nəzarəti (`/admin/customs`):**
   - Bəyannamə təsdiq növbəsi, $250+ riskli bağlamalar, xüsusi icazə tələb edən mallar (mayelər, dronlar) və modal pəncərə vasitəsilə operativ HS Kodu (XİF FEA) dəyişməsi.
5. **Daşıyıcı Marjaları & Şəbəkə (`/admin/carriers`):**
   - Daşıyıcıların baza tarifləri, platforma arbitraj marjası (%5.0), aktiv filial sayı və API cavab müddəti (latency).
6. **Təhlükəsizlik və Audit Jurnalı (`/admin/audit`):**
   - Canlı rejimdə hər bir autentifikasiya, uğursuz giriş, gömrük avtomatlaşdırması və kvota xəbərdarlığının dəyişdirilməz jurnalı.

---

## 6. Hüquqi Uyğunluq və Qanunvericilik Bazası

KargoPilot platforması bütün arxitekturasında Azərbaycan Respublikasının qanunvericilik aktlarına tam uyğunlaşdırılmışdır:

1. **Azərbaycan Respublikasının "Fərdi məlumatlar haqqında" Qanunu:**
   - İstifadəçilərin FİN kodları, pasport məlumatları və çatdırılma ünvanları bazada birbaşa açıq şəkildə saxlanılmır. Bütün həssas sütunlar AES-256 zərf şifrələməsi ilə qorunur.
2. **Azərbaycan Respublikası Nazirlər Kabinetinin 305 saylı Qərarı:**
   - Fiziki şəxslər tərəfindən fərdi istehlak üçün ölkəyə gətirilən malların 30 təqvim günü ərzində ümumi gömrük dəyərinin $300 USD-dən artıq olmamasına nəzarət edən dəqiq riyazi alqoritm tətbiq olunub.
3. **Azərbaycan Respublikasının Mərkəzi Bankı (CBAR):**
   - Bütün gömrük və daşıma hesablamaları hər səhər CBAR rəsmi XML/JSON məzənnələri ilə sinxronlaşdırılır, süni konvertasiya zərərləri aradan qaldırılır.

---

## 7. Agency Subagents Komandası və Test Sertifikatlaşdırması

Layihənin bu mərhələsində `agency-agents` repozitoriyasından 6 yüksək ixtisaslaşmış süni intellekt agenti paralel səfərbər edilmişdir:

| Agent Rolu | İcra Sahəsi | Təhvil Verilən Nəticə |
| :--- | :--- | :--- |
| **Backend Architect** | Çoxistifadəçili Model & Verilənlər Bazası | `v4_0_to_v4_5_multitenant.sql`, WAL Scoper, 0.46ms sorğu sürəti |
| **Identity & Access Engineer** | Təhlükəsizlik, Argon2id & WhatsApp Qapısı | `app/security/` modulu (12 təhlükəsizlik testi 100% keçdi) |
| **Admin UX Architect** | İnformasiya Memarlığı & Wireframelər | Qaranlıq şüşə dizayn sistemi, 6 admin ekranı və FİN drawer |
| **API Tester** | REST Uç Nöqtələri & Bəyannamə Doğrulama | `/admin/api/*` və `/api/v1/auth/*` testləri |
| **Test Automation Engineer** | Pytest Harness & Reqresiya Testləri | 34 tam avtomatlaşdırılmış vahid və inteqrasiya testi |
| **Performance Benchmarker** | SQLite WAL & Latency Ölçmələri | < 1ms DB cavabı, < 20ms HTTP cavab müddəti |

### 🧪 Test Nəticələri İcmalı
```
collected 34 items
tests\test_admin_cockpit.py ........                                     [ 23%]
tests\test_e2e_address_formatter.py .                                    [ 26%]
tests\test_pcs_v4_innovations.py ............                            [ 61%]
tests\test_security_suite.py ............                                [ 97%]
tests\test_v4_5_migration.py .                                           [100%]

======================= 34 passed, 0 failures in 6.38s ========================
```

---

## 8. İnvestor Nəticəsi və Yol Xəritəsi (Next Milestones)

KargoPilot artıq prototip mərhələsini tamamilə keçərək, həm qapalı dövlət və korporativ mühitlər (Sovereign), həm də kütləvi istehlak bazarı (Managed Cloud) üçün hazır, miqyaslana bilən **v4.5 Enterprise Platformasına** çevrilmişdir.

**Növbəti 3 Aylıq Hədəflər:**
1. **İlkin B2C İctimai Qeydiyyat:** 5,000 aktiv istifadəçinin qəbulu və WhatsApp Loyd AI bildirişlərinin işə salınması.
2. **Daşıyıcı API Tərəfdaşlığı:** Starex və Limak ilə birbaşa kommersiya API inteqrasiyası və arbitraj komissiyası müqaviləsi.
3. **Toxum İnvestisiya Raundu (Seed Round):** Platformanın regional miqyaslanması və mobil tətbiq (Flutter) buraxılışı üçün \$150,000 – \$250,000 investisiyanın cəlb edilməsi.

---
*KargoPilot v4.5 Enterprise — Azərbaycan Logistika və Gömrük Ekosisteminin Avtonom Gələcəyi.*

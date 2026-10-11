"""عرض وتخديم صفحة التطبيق المصغر الموحدة (Mini App View Renderer)."""
from __future__ import annotations

from aiohttp import web

HTML_SHELL = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>متجر الخدمات الرقمية</title>
  <link rel="stylesheet" href="/static/miniapp.css">
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script src="/static/vue.min.js"></script>
</head>
<body>
  <div id="app">
    <!-- شاشة التحميل الأولية -->
    <div v-if="loading" style="padding: 2rem 1rem;">
      <div class="skeleton" style="height: 48px; margin-bottom: 1rem;"></div>
      <div class="skeleton" style="height: 140px; margin-bottom: 1rem; border-radius: 1.25rem;"></div>
      <div class="skeleton" style="height: 44px; margin-bottom: 1.5rem; border-radius: 9999px;"></div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
        <div class="skeleton" style="height: 160px; border-radius: 1rem;"></div>
        <div class="skeleton" style="height: 160px; border-radius: 1rem;"></div>
        <div class="skeleton" style="height: 160px; border-radius: 1rem;"></div>
        <div class="skeleton" style="height: 160px; border-radius: 1rem;"></div>
      </div>
    </div>

    <!-- شاشة الخطأ -->
    <div v-else-if="errorMsg" style="text-align: center; padding: 4rem 1.5rem;">
      <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
      <h2 style="font-weight: 800; margin-bottom: 0.5rem;">تعذر فتح المتجر</h2>
      <p style="color: var(--text-muted); margin-bottom: 1.5rem;">{{ errorMsg }}</p>
      <button class="quick-charge-btn" @click="loadStore" style="margin: 0 auto;">🔄 إعادة المحاولة</button>
    </div>

    <!-- واجهة التطبيق الرئيسية -->
    <div v-else>
      <!-- الشريط العلوي الثابت -->
      <header class="top-header">
        <div class="brand-section">
          <img :src="themeData.logo_url || '/static/app.css'" class="brand-logo" onerror="this.src='https://api.dicebear.com/7.x/bottts/svg?seed='+botUsername">
          <div>
            <div class="brand-title">{{ themeData.store_name || botData.name }}</div>
            <span class="brand-badge" v-if="userData.role === 'seller'">مالك المتجر 👑</span>
            <span class="brand-badge" v-else-if="userData.role === 'admin'">المدير العام 🛡️</span>
            <span class="brand-badge" v-else>متجر موثق ⭐</span>
          </div>
        </div>
        <div class="header-actions">
          <button class="quick-charge-btn" @click="showDepositModal = true">
            <span>➕</span>
            <span>شحن</span>
          </button>
        </div>
      </header>

      <!-- ── التبويب 1: المتجر الرئيسي ── -->
      <main v-if="activeTab === 'store'">
        <!-- كرت المحفظة الذكية -->
        <div class="wallet-card">
          <div class="wallet-top">
            <div class="chip-icon"></div>
            <div class="wallet-notice">رصيد المتجر الداخلي</div>
          </div>
          <div class="wallet-balance-row">
            <div class="wallet-label">الرصيد المتاح للطلب</div>
            <div class="wallet-amount">{{ userData.balance_display || '$0.00' }}</div>
          </div>
          <div class="wallet-footer">
            <div>{{ userData.name }}</div>
            <div class="wallet-user-id">•••• {{ String(userData.uid).slice(-4) }}</div>
          </div>
        </div>

        <!-- شريط البحث الذكي -->
        <div class="search-bar-wrap">
          <span class="search-icon">🔍</span>
          <input type="search" class="search-input" v-model="searchQuery" placeholder="ابحث عن لعبة، اشتراك، أو باقة...">
        </div>

        <!-- العروض المؤقتة النشطة -->
        <div v-if="activeSales && activeSales.length > 0" style="margin: 0 1rem 1rem; padding: 0.75rem 1rem; border-radius: 1rem; background: linear-gradient(135deg, #ef4444, #b91c1c); color: #fff; display: flex; align-items: center; justify-content: space-between;">
          <div style="font-weight: 800; font-size: 0.9rem;">🔥 {{ activeSales[0].title }}</div>
          <div style="font-size: 0.75rem; background: rgba(0,0,0,0.25); padding: 0.2rem 0.6rem; border-radius: 9999px;">خصم {{ activeSales[0].discount_value }}%</div>
        </div>

        <!-- أزرار الأقسام -->
        <div class="cat-pills-wrap">
          <button class="cat-pill" :class="{ active: selectedCategory === 'all' }" @click="selectedCategory = 'all'">الكل</button>
          <button v-for="cat in categories" :key="cat.id" class="cat-pill" :class="{ active: selectedCategory === cat.id }" @click="selectedCategory = cat.id">
            {{ cat.icon }} {{ cat.name }}
          </button>
        </div>

        <!-- شبكة المنتجات -->
        <div class="products-grid">
          <div v-for="p in filteredProducts" :key="p.id" class="product-card" @click="openProduct(p)">
            <span class="product-badge badge-discount" v-if="p.has_discount">%{{ p.discount_percent }} خصم</span>
            <span class="product-badge badge-instant" v-else-if="p.is_instant">⚡ فوري</span>
            <img :src="p.image_url || 'https://api.dicebear.com/7.x/icons/svg?seed='+p.id" class="product-thumb">
            <div class="product-title">{{ p.name }}</div>
            <div class="product-price-row">
              <span class="price-current">${{ p.price_usd.toFixed(2) }}</span>
              <span class="price-old" v-if="p.has_discount">${{ p.original_price_usd.toFixed(2) }}</span>
            </div>
          </div>
        </div>

        <div v-if="filteredProducts.length === 0" style="text-align: center; padding: 3rem 1rem; color: var(--text-muted);">
          🔍 لا توجد نتائج مطابقة لبحثك
        </div>
      </main>

      <!-- ── التبويب 2: لوحة البائع (Seller Panel) ── -->
      <section v-else-if="activeTab === 'seller'" style="padding: 1rem;">
        <h2 style="font-size: 1.25rem; font-weight: 800; margin-bottom: 1rem;">⚙️ لوحة تحكم المتجر والتصميم</h2>

        <!-- كروت الإحصائيات -->
        <div v-if="sellerStats" style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 1.5rem;">
          <div style="background: var(--card-bg); border: 1px solid var(--card-border); padding: 1rem; border-radius: 1rem;">
            <div style="font-size: 0.75rem; color: var(--text-muted);">إجمالي الطلبات</div>
            <div style="font-size: 1.4rem; font-weight: 800;">{{ sellerStats.total_orders }}</div>
          </div>
          <div style="background: var(--card-bg); border: 1px solid var(--card-border); padding: 1rem; border-radius: 1rem;">
            <div style="font-size: 0.75rem; color: var(--text-muted);">المبيعات المكتملة</div>
            <div style="font-size: 1.4rem; font-weight: 800; color: var(--success);">${{ sellerStats.total_sales_usd }}</div>
          </div>
        </div>

        <!-- المساعد الذكي لتصميم المتجر -->
        <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 1rem; padding: 1rem; margin-bottom: 1.5rem;">
          <h3 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.5rem;">✨ المساعد الذكي لتخصيص المتجر</h3>
          <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem;">اكتب أسلوب التصميم وسيقوم المساعد بضبط الألوان والشكل بدقة:</p>
          <input type="text" class="search-input" v-model="aiPromptInput" placeholder="مثال: اجعل المتجر بألوان ذهبية داكنة وزوايا ناعمة" style="margin-bottom: 0.5rem;">
          <button class="quick-charge-btn" @click="requestAiCustomizer" :disabled="aiLoading" style="width: 100%; justify-content: center;">
            {{ aiLoading ? '⏳ جاري التوليد...' : '🚀 توليد التصميم الذكي' }}
          </button>
        </div>

        <!-- محرر الإعدادات المرئي -->
        <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 1rem; padding: 1rem;">
          <h3 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.75rem;">🎨 ألوان وخطوط المتجر</h3>
          <div style="display: flex; flex-direction: column; gap: 0.75rem;">
            <label style="font-size: 0.8rem;">اسم المتجر:
              <input type="text" class="search-input" v-model="themeDraft.store_name" style="margin-top: 0.25rem;">
            </label>
            <label style="font-size: 0.8rem;">اللون الأساسي:
              <input type="color" v-model="themeDraft.primary_color" style="width: 100%; height: 40px; border-radius: 0.5rem; border: none; cursor: pointer; margin-top: 0.25rem;">
            </label>
            <label style="font-size: 0.8rem;">نوع الخط:
              <select v-model="themeDraft.font_family" class="search-input" style="margin-top: 0.25rem;">
                <option value="Cairo">Cairo (القاهرة)</option>
                <option value="Tajawal">Tajawal (تجوال)</option>
                <option value="Almarai">Almarai (المراعي)</option>
                <option value="IBM Plex Sans Arabic">IBM Plex Sans Arabic</option>
              </select>
            </label>
            <button class="quick-charge-btn" @click="saveTheme" style="width: 100%; justify-content: center; margin-top: 0.5rem;">
              💾 حفظ ونشر التصميم
            </button>
          </div>
        </div>
      </section>

      <!-- ── التبويب 3: لوحة الأدمن المركزية ── -->
      <section v-else-if="activeTab === 'admin'" style="padding: 1rem;">
        <h2 style="font-size: 1.25rem; font-weight: 800; margin-bottom: 1rem;">🛡️ لوحة إدارة المنصة المركزية</h2>
        <div style="background: var(--card-bg); border: 1px solid var(--card-border); padding: 1rem; border-radius: 1rem;">
          <p style="font-size: 0.85rem; color: var(--text-muted);">أهلاً بك يا مدير المنصة. يمكنك مراقبة كافة العمليات والطلبات والحسابات من هنا.</p>
        </div>
      </section>

      <!-- ── نافذة تفاصيل المنتج والشراء (Bottom Sheet) ── -->
      <div class="modal-overlay" v-if="selectedProduct" @click.self="closeProduct">
        <div class="bottom-sheet">
          <div class="sheet-drag-handle"></div>
          <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 0.25rem;">{{ selectedProduct.name }}</h3>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">{{ selectedProduct.description }}</p>

          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1rem; padding: 0.75rem; background: rgba(255,255,255,0.03); border-radius: 0.75rem;">
            <span style="font-size: 0.85rem; color: var(--text-muted);">السعر الإجمالي:</span>
            <span style="font-size: 1.25rem; font-weight: 900; color: var(--success);">${{ selectedProduct.price_usd.toFixed(2) }}</span>
          </div>

          <!-- خانة البيانات المطلوبة -->
          <div v-if="selectedProduct.input_label" style="margin-bottom: 1rem;">
            <label style="font-size: 0.8rem; font-weight: 700; display: block; margin-bottom: 0.35rem;">{{ selectedProduct.input_label }}:</label>
            <input type="text" class="search-input" v-model="orderTargetInput" placeholder="أدخل البيانات المطلوبة بدقة...">
          </div>

          <!-- شرط قرأت وأوافق الإجباري -->
          <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; margin-bottom: 1.25rem; cursor: pointer;">
            <input type="checkbox" v-model="agreedToTerms" style="width: 18px; height: 18px; accent-color: var(--primary);">
            <span>قرأت وأوافق على شروط وسياسة الخدمة والتسليم الإلزامية</span>
          </label>

          <!-- نتيجة الطلب الناجح -->
          <div v-if="orderSuccessData" style="background: rgba(16,185,129,0.15); border: 1px solid var(--success); padding: 1rem; border-radius: 0.75rem; margin-bottom: 1rem; text-align: center;">
            <div style="font-weight: 800; color: var(--success); margin-bottom: 0.25rem;">🎉 تم تنفيذ الطلب بنجاح!</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">رقم الطلب: #{{ orderSuccessData.order_id }}</div>
            <div v-if="orderSuccessData.voucher" style="margin-top: 0.5rem; padding: 0.4rem; background: var(--card-bg); font-family: monospace; font-weight: 800;">
              كود القسيمة: {{ orderSuccessData.voucher }}
            </div>
          </div>

          <button class="quick-charge-btn" @click="submitOrder" :disabled="orderSubmitting || !agreedToTerms" style="width: 100%; justify-content: center; padding: 0.85rem; font-size: 1rem;">
            {{ orderSubmitting ? '⏳ جاري التنفيذ...' : '🛒 تأكيد الطلب والشراء' }}
          </button>
        </div>
      </div>

      <!-- ── نافذة شحن الرصيد ── -->
      <div class="modal-overlay" v-if="showDepositModal" @click.self="showDepositModal = false">
        <div class="bottom-sheet">
          <div class="sheet-drag-handle"></div>
          <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 0.5rem;">💳 شحن رصيد المحفظة</h3>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">اختر طريقة الشحن المفضلة لشحن محفظتك الفورية:</p>
          <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
            <button class="cat-pill" :class="{ active: depositMethod === 'stars' }" @click="depositMethod = 'stars'">⭐ نجوم تيليجرام</button>
            <button class="cat-pill" :class="{ active: depositMethod === 'manual' }" @click="depositMethod = 'manual'">🏦 تحويل يدوي</button>
          </div>
          <div v-if="depositMethod === 'stars'">
            <label style="font-size: 0.8rem; display: block; margin-bottom: 0.4rem;">عدد النجوم:</label>
            <input type="number" class="search-input" v-model="depositStarsAmount" min="50" step="50" style="margin-bottom: 1rem;">
            <button class="quick-charge-btn" @click="submitDeposit" style="width: 100%; justify-content: center; padding: 0.75rem;">
              ⭐ دفع النجوم فورياً
            </button>
          </div>
          <div v-else>
            <label style="font-size: 0.8rem; display: block; margin-bottom: 0.4rem;">رقم العملية / إثبات التحويل:</label>
            <textarea class="search-input" v-model="depositProofText" placeholder="اكتب رقم الحوالة أو بيانات التحويل..." style="height: 80px; margin-bottom: 1rem;"></textarea>
            <button class="quick-charge-btn" @click="submitDeposit" style="width: 100%; justify-content: center; padding: 0.75rem;">
              📤 إرسال الإشعار للمراجعة
            </button>
          </div>
        </div>
      </div>

      <!-- ── شريط التنقل السفلي الثابت ── -->
      <nav class="bottom-nav">
        <div class="nav-tab" :class="{ active: activeTab === 'store' }" @click="activeTab = 'store'">
          <span class="nav-tab-icon">🏪</span>
          <span>المتجر</span>
        </div>
        <div class="nav-tab" :class="{ active: activeTab === 'orders' }" @click="activeTab = 'store'">
          <span class="nav-tab-icon">📦</span>
          <span>طلباتي</span>
        </div>
        <div class="nav-tab" v-if="userData.role === 'seller' || userData.role === 'admin'" :class="{ active: activeTab === 'seller' }" @click="activeTab = 'seller'">
          <span class="nav-tab-icon">⚙️</span>
          <span>لوحة البائع</span>
        </div>
        <div class="nav-tab" v-if="userData.role === 'admin'" :class="{ active: activeTab === 'admin' }" @click="activeTab = 'admin'">
          <span class="nav-tab-icon">🛡️</span>
          <span>الأدمن</span>
        </div>
      </nav>
    </div>
  </div>

  <script src="/static/miniapp.js"></script>
</body>
</html>
"""


async def render_miniapp_view(req: web.Request) -> web.Response:
    """يعيد صفحة HTML الكاملة للتطبيق المصغر مع رؤوس الأمان."""
    headers = {
        "Content-Type": "text/html; charset=utf-8",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": (
            "default-src 'self' https: data: blob: 'unsafe-inline' 'unsafe-eval'; "
            "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://*.t.me;"
        ),
        "Cache-Control": "no-cache",
    }
    return web.Response(text=HTML_SHELL, headers=headers)

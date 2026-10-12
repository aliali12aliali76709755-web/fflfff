"""عرض وتخديم صفحة التطبيق المصغر الموحدة (Mini App View Renderer)."""
from __future__ import annotations

from aiohttp import web

HTML_SHELL = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>متجر الخدمات الرقمية المعتمد</title>
  <link rel="stylesheet" href="/static/miniapp.css">
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script src="/static/vue.min.js"></script>
</head>
<body>
  <div id="app">
    <!-- شاشة التحميل الأولية -->
    <div v-if="loading" class="skeleton-wrap">
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
          <img :src="themeData.logo_url || '/static/app.css'" class="brand-logo" onerror="this.src='https://api.dicebear.com/7.x/bottts/svg?seed='+(botUsername||'bot')">
          <div>
            <div class="brand-title">{{ themeData.store_name || botData.name || 'متجر الخدمات' }}</div>
            <span class="brand-badge" v-if="userData.role === 'admin'">المدير العام 🛡️</span>
            <span class="brand-badge" v-else-if="userData.role === 'seller'">مالك المتجر 👑</span>
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

      <!-- ── 1. تبويب المتجر الرئيسي (Store) ── -->
      <main v-if="activeTab === 'store'">
        <!-- كرت المحفظة الذكية -->
        <div class="wallet-card">
          <div class="wallet-top">
            <div class="chip-icon"></div>
            <div class="wallet-notice">المحفظة الفورية</div>
          </div>
          <div class="wallet-balance-row">
            <div class="wallet-label">الرصيد المتاح للطلب</div>
            <div class="wallet-amount">{{ userData.balance_display || '$0.00' }}</div>
          </div>
          <div class="wallet-footer">
            <div>{{ userData.name || 'مشتري معتمد' }}</div>
            <div class="wallet-user-id">•••• {{ String(userData.uid || '0000').slice(-4) }}</div>
          </div>
        </div>

        <!-- شريط البحث الذكي -->
        <div class="search-bar-wrap">
          <span class="search-icon">🔍</span>
          <input type="search" class="search-input" v-model="searchQuery" placeholder="ابحث عن لعبة، اشتراك، أو باقة...">
        </div>

        <!-- العروض المؤقتة النشطة -->
        <div v-if="activeSales && activeSales.length > 0" class="active-sale-banner">
          <div style="font-weight: 800; font-size: 0.9rem;">🔥 {{ activeSales[0].title }}</div>
          <div style="font-size: 0.75rem; background: rgba(0,0,0,0.25); padding: 0.2rem 0.6rem; border-radius: 9999px;">خصم {{ activeSales[0].discount_value }}%</div>
        </div>

        <!-- أزرار الأقسام -->
        <div class="cat-pills-wrap">
          <button class="cat-pill" :class="{ active: selectedCategory === 'all' }" @click="selectedCategory = 'all'">الكل</button>
          <button v-for="cat in categories" :key="cat.id" class="cat-pill" :class="{ active: selectedCategory === cat.id }" @click="selectedCategory = cat.id">
            {{ cat.icon || '📦' }} {{ cat.name }}
          </button>
        </div>

        <!-- شبكة المنتجات -->
        <div class="products-grid">
          <div v-for="p in filteredProducts" :key="p.id" class="product-card" @click="openProduct(p)">
            <span class="product-badge badge-discount" v-if="p.has_discount">%{{ p.discount_percent }} خصم</span>
            <span class="product-badge badge-instant" v-else-if="p.is_instant">⚡ فوري</span>
            <img :src="p.image_url || 'https://api.dicebear.com/7.x/icons/svg?seed='+p.id" class="product-thumb" onerror="this.src='https://api.dicebear.com/7.x/icons/svg?seed='+p.id">
            <div class="product-title">{{ p.name }}</div>
            <div class="product-price-row">
              <span class="price-current">${{ Number(p.price_usd).toFixed(2) }}</span>
              <span class="price-old" v-if="p.has_discount">${{ Number(p.original_price_usd).toFixed(2) }}</span>
            </div>
          </div>
        </div>

        <div v-if="filteredProducts.length === 0" class="empty-state">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔍</div>
          <div>لا توجد منتجات مطابقة لبحثك</div>
        </div>

        <!-- تذييل المتجر (الدعم والشروط) -->
        <footer class="store-footer">
          <div class="footer-links">
            <a href="javascript:void(0)" @click="openSupportChat" class="footer-link">
              <span>💬</span>
              <span>الدعم الفني المباشر</span>
            </a>
            <span class="footer-sep">•</span>
            <a href="javascript:void(0)" @click="showTermsModal = true" class="footer-link">
              <span>📜</span>
              <span>شروط وسياسات المتجر</span>
            </a>
          </div>
          <div class="footer-copy">⚡ جميع المعاملات مشفرة ومحمية بالضمان الذهبي</div>
        </footer>
      </main>

      <!-- ── 2. تبويب طلباتي (Orders) ── -->
      <section v-else-if="activeTab === 'orders'" class="tab-content-wrap">
        <div class="section-header">
          <h2 class="section-title">📦 طلباتي ومتابعة الحالات</h2>
          <button class="refresh-pill-btn" @click="loadOrders">🔄 تحديث</button>
        </div>

        <div v-if="ordersLoading" style="padding: 1rem 0;">
          <div class="skeleton" style="height: 90px; margin-bottom: 0.75rem; border-radius: 1rem;"></div>
          <div class="skeleton" style="height: 90px; margin-bottom: 0.75rem; border-radius: 1rem;"></div>
        </div>

        <div v-else-if="userOrders.length === 0" class="empty-state">
          <div style="font-size: 3rem; margin-bottom: 0.5rem;">🛒</div>
          <h3 style="font-weight: 800; margin-bottom: 0.25rem;">لا توجد لديك طلبات سابقة</h3>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">تصفح المتجر واطلب الآن بكل سهولة وسرعة!</p>
          <button class="quick-charge-btn" @click="activeTab = 'store'" style="margin: 0 auto;">🛍️ الذهاب للمتجر</button>
        </div>

        <div v-else class="orders-list">
          <div v-for="ord in userOrders" :key="ord.order_id" class="order-card">
            <div class="order-card-header">
              <div class="order-prod-name">{{ ord.product_name || 'طلب رقمي' }}</div>
              <span class="order-status-pill" :class="'status-' + ord.status">
                {{ formatOrderStatus(ord.status) }}
              </span>
            </div>

            <div class="order-details-grid">
              <div class="order-meta-item">
                <span class="meta-label">رقم الطلب:</span>
                <span class="meta-val">#{{ ord.order_id }}</span>
              </div>
              <div class="order-meta-item">
                <span class="meta-label">التاريخ:</span>
                <span class="meta-val">{{ ord.created || 'مؤخراً' }}</span>
              </div>
              <div class="order-meta-item" v-if="ord.target">
                <span class="meta-label">البيانات:</span>
                <span class="meta-val">{{ ord.target }}</span>
              </div>
              <div class="order-meta-item">
                <span class="meta-label">المبلغ:</span>
                <span class="meta-val" style="color: var(--success); font-weight: 800;">${{ Number(ord.price_usd).toFixed(2) }}</span>
              </div>
            </div>

            <!-- كود القسيمة / التسليم الفوري إن وجد -->
            <div v-if="ord.voucher" class="order-voucher-box">
              <div class="voucher-title">⚡ كود التفعيل / البطاقة:</div>
              <div class="voucher-val-row">
                <code class="voucher-code-text">{{ ord.voucher }}</code>
                <button class="copy-voucher-btn" @click="copyText(ord.voucher, 'تم نسخ كود التفعيل بنجاح! ✅')">📋 نسخ</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ── 3. تبويب حسابي (Account) ── -->
      <section v-else-if="activeTab === 'account'" class="tab-content-wrap">
        <h2 class="section-title" style="margin-bottom: 1rem;">👤 الملف الشخصي والمحفظة</h2>

        <!-- كرت هوية الحساب -->
        <div class="profile-card">
          <img :src="'https://api.dicebear.com/7.x/identicon/svg?seed=' + (userData.uid || 'user')" class="profile-avatar">
          <div class="profile-info">
            <div class="profile-name">{{ userData.name || 'مستخدم تيليجرام' }}</div>
            <div class="profile-sub">
              <span>@{{ userData.username || 'بدون معرف' }}</span>
              <span class="profile-id-pill">ID: {{ userData.uid }}</span>
            </div>
          </div>
          <div class="profile-role-badge">
            {{ userData.role === 'admin' ? '🛡️ مدير' : (userData.role === 'seller' ? '👑 بائع' : '⭐ مشتري') }}
          </div>
        </div>

        <!-- كرت المحفظة والشحن -->
        <div class="account-wallet-card">
          <div class="acc-wallet-head">
            <div style="font-size: 0.85rem; color: var(--text-muted);">رصيد محفظتي المتاح</div>
            <div class="acc-wallet-num">{{ userData.balance_display || '$0.00' }}</div>
          </div>
          <button class="quick-charge-btn" @click="showDepositModal = true" style="padding: 0.6rem 1.25rem;">
            <span>➕</span>
            <span>شحن المحفظة فورياً</span>
          </button>
        </div>

        <!-- كرت نظام الإحالة والأرباح -->
        <div class="referral-card">
          <div class="ref-card-header">
            <div class="ref-card-title">🎁 برنامج الإحالة والأرباح</div>
            <span class="ref-badge">عمولة فورية</span>
          </div>
          <p class="ref-desc">شارك رابطك الحصري مع أصدقائك واكسب أرباحاً تُضاف لمحفظتك مع كل طلب يقومون به!</p>

          <div class="ref-link-box">
            <input type="text" readonly :value="accountData.referral_link || ('https://t.me/'+botUsername+'?start=sl_'+userData.uid)" class="ref-input">
            <button class="ref-copy-btn" @click="copyText(accountData.referral_link || ('https://t.me/'+botUsername+'?start=sl_'+userData.uid), 'تم نسخ رابط الإحالة! 🎁')">
              📋 نسخ الرابط
            </button>
          </div>

          <div class="ref-stats-grid">
            <div class="ref-stat-box">
              <div class="ref-stat-num">{{ accountData.invited_count || 0 }}</div>
              <div class="ref-stat-label">👥 الأصدقاء المسجلين</div>
            </div>
            <div class="ref-stat-box">
              <div class="ref-stat-num" style="color: var(--success);">${{ Number(accountData.earned_usd || 0).toFixed(2) }}</div>
              <div class="ref-stat-label">💰 الأرباح المكتسبة</div>
            </div>
          </div>
        </div>

        <!-- بطاقات الخدمات والمعلومات -->
        <div class="acc-actions-list">
          <div class="acc-action-item" @click="openSupportChat">
            <div class="action-item-left">
              <span class="action-item-icon">💬</span>
              <div>
                <div class="action-item-title">الدعم الفني للمتجر</div>
                <div class="action-item-sub">تواصل مع خدمة العملاء لحل أي استفسار</div>
              </div>
            </div>
            <span class="action-arrow">❮</span>
          </div>

          <div class="acc-action-item" @click="showTermsModal = true">
            <div class="action-item-left">
              <span class="action-item-icon">📜</span>
              <div>
                <div class="action-item-title">شروط وسياسات المتجر</div>
                <div class="action-item-sub">شروط التسليم وسياسة الضمان والاسترجاع</div>
              </div>
            </div>
            <span class="action-arrow">❮</span>
          </div>
        </div>
      </section>

      <!-- ── 4. تبويب لوحة البائع (Seller Panel) ── -->
      <!-- يظهر حصراً لمالك البوت أو الأدمن -->
      <section v-else-if="activeTab === 'seller' && (userData.role === 'seller' || userData.role === 'admin')" class="tab-content-wrap">
        <div class="section-header">
          <h2 class="section-title">👑 لوحة تحكم وإدارة المتجر</h2>
        </div>

        <!-- القائمة الفرعية لأقسام البائع -->
        <div class="cat-pills-wrap" style="margin-bottom: 1rem;">
          <button class="cat-pill" :class="{ active: sellerSubTab === 'analytics' }" @click="sellerSubTab = 'analytics'">📊 الإحصائيات والمخطط</button>
          <button class="cat-pill" :class="{ active: sellerSubTab === 'products' }" @click="sellerSubTab = 'products'">📦 إدارة المنتجات</button>
          <button class="cat-pill" :class="{ active: sellerSubTab === 'settings' }" @click="sellerSubTab = 'settings'">⚙️ الشروط والدعم</button>
          <button class="cat-pill" :class="{ active: sellerSubTab === 'theme' }" @click="sellerSubTab = 'theme'">🎨 المظهر والتصميم</button>
        </div>

        <!-- ── أ. قسم المخطط التحليلي والإحصائيات ── -->
        <div v-if="sellerSubTab === 'analytics'">
          <!-- كروت الـ KPIs -->
          <div class="kpi-grid">
            <div class="kpi-card">
              <div class="kpi-label">إجمالي الطلبات</div>
              <div class="kpi-value">{{ sellerAnalytics.summary?.total_orders || 0 }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">مكتملة بنجاح</div>
              <div class="kpi-value" style="color: var(--success);">{{ sellerAnalytics.summary?.completed_orders || 0 }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">قيد التنفيذ</div>
              <div class="kpi-value" style="color: var(--warning);">{{ sellerAnalytics.summary?.pending_orders || 0 }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">ملغية / مسترجعة</div>
              <div class="kpi-value" style="color: var(--danger);">{{ sellerAnalytics.summary?.canceled_orders || 0 }}</div>
            </div>
            <div class="kpi-card highlight-card">
              <div class="kpi-label">إجمالي الإيرادات</div>
              <div class="kpi-value">${{ Number(sellerAnalytics.summary?.total_revenue_usd || 0).toFixed(2) }}</div>
            </div>
            <div class="kpi-card highlight-card">
              <div class="kpi-label">صافي الأرباح</div>
              <div class="kpi-value" style="color: #38bdf8;">${{ Number(sellerAnalytics.summary?.net_profit_usd || 0).toFixed(2) }}</div>
            </div>
          </div>

          <!-- المخطط التحليلي التفاعلي والمتحرك -->
          <div class="chart-container-card">
            <div class="chart-header">
              <div class="chart-title">📈 حركة التفاعل والطلبات خلال 7 أيام</div>
              <div class="chart-hint">المس العمود لعرض التفاصيل</div>
            </div>

            <!-- عرض تفاصيل اليوم المحدد -->
            <div v-if="selectedChartDay" class="chart-tooltip-banner">
              <strong>{{ selectedChartDay.day_name }} ({{ selectedChartDay.date }})</strong>:
              <span>الطلبات: {{ selectedChartDay.orders }}</span> |
              <span>المكتملة: {{ selectedChartDay.completed }}</span> |
              <span style="color: var(--success);">المبيعات: ${{ selectedChartDay.revenue }}</span>
            </div>

            <div class="chart-bars-wrap">
              <div v-for="day in (sellerAnalytics.chart_days || [])" :key="day.date" class="chart-col" @click="selectedChartDay = day">
                <div class="chart-bar-outer">
                  <div class="chart-bar-fill" :style="{ height: getBarHeightPercent(day.orders) + '%' }" :class="{ active: selectedChartDay && selectedChartDay.date === day.date }">
                    <span class="bar-val-top" v-if="day.orders > 0">{{ day.orders }}</span>
                  </div>
                </div>
                <div class="chart-day-label">{{ day.day_name }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── ب. قسم إدارة المنتجات المخصصة ── -->
        <div v-else-if="sellerSubTab === 'products'">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h3 style="font-weight: 800; font-size: 1rem;">المنتجات المخصصة بالمتجر</h3>
            <button class="quick-charge-btn" @click="showAddProductModal = true">➕ إضافة منتج جديد</button>
          </div>

          <div v-if="sellerProducts.length === 0" class="empty-state">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📦</div>
            <div>لم تقم بإضافة منتجات مخصصة بعد</div>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">أضف ألعابك وخدماتك وحساباتك الآن لتبدأ المبيعات!</p>
          </div>

          <div v-else class="seller-prods-list">
            <div v-for="sp in sellerProducts" :key="sp.id" class="seller-prod-item">
              <img :src="sp.image_url || 'https://api.dicebear.com/7.x/icons/svg?seed='+sp.id" class="seller-prod-thumb" onerror="this.src='https://api.dicebear.com/7.x/icons/svg?seed='+sp.id">
              <div class="seller-prod-meta">
                <div class="seller-prod-title">{{ sp.name }}</div>
                <div class="seller-prod-sub">
                  <span class="seller-prod-price">${{ Number(sp.price_usd).toFixed(2) }}</span>
                  <span class="seller-prod-cat">{{ sp.category_name || 'عام' }}</span>
                  <span v-if="sp.is_instant" class="seller-prod-tag">⚡ فوري</span>
                </div>
              </div>
              <button class="delete-prod-btn" @click="deleteProduct(sp.id)" title="حذف المنتج">🗑️</button>
            </div>
          </div>
        </div>

        <!-- ── ج. قسم الشروط والدعم الفني ── -->
        <div v-else-if="sellerSubTab === 'settings'">
          <div class="settings-form-card">
            <h3 style="font-weight: 800; font-size: 1rem; margin-bottom: 0.75rem;">⚙️ إعدادات الدعم والشروط والسياسات</h3>

            <div class="form-group">
              <label class="form-label">📞 رابط أو يوزر الدعم الفني المباشر:</label>
              <input type="text" class="search-input" v-model="sellerSettings.support_url" placeholder="مثال: https://t.me/YourSupportUser">
              <small class="form-hint">يظهر للمشتري في أسفل المتجر وفي صفحة حسابه للتواصل السريع معك.</small>
            </div>

            <div class="form-group">
              <label class="form-label">📜 شروط وأحكام الخدمة والتسليم:</label>
              <textarea class="search-input text-area-h" v-model="sellerSettings.terms_text" placeholder="اكتب شروط متجرك بدقة..."></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">🛡️ سياسة الاسترجاع والضمان:</label>
              <textarea class="search-input text-area-h" v-model="sellerSettings.policy_text" placeholder="اكتب سياسة استرجاع الأموال والضمان..."></textarea>
            </div>

            <button class="quick-charge-btn" @click="saveSettings" :disabled="savingSettings" style="width: 100%; justify-content: center; padding: 0.75rem; margin-top: 0.5rem;">
              {{ savingSettings ? '⏳ جاري الحفظ...' : '💾 حفظ الإعدادات والسياسات' }}
            </button>
          </div>
        </div>

        <!-- ── د. قسم المظهر والذكاء الاصطناعي ── -->
        <div v-else-if="sellerSubTab === 'theme'">
          <!-- المساعد الذكي لتصميم المتجر -->
          <div class="settings-form-card" style="margin-bottom: 1.25rem;">
            <h3 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.5rem;">✨ المساعد الذكي لتخصيص المتجر</h3>
            <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem;">اكتب أسلوب التصميم وسيقوم المساعد بضبط الألوان والشكل بدقة:</p>
            <input type="text" class="search-input" v-model="aiPromptInput" placeholder="مثال: اجعل المتجر بألوان ذهبية داكنة وزوايا ناعمة" style="margin-bottom: 0.5rem;">
            <button class="quick-charge-btn" @click="requestAiCustomizer" :disabled="aiLoading" style="width: 100%; justify-content: center;">
              {{ aiLoading ? '⏳ جاري التوليد...' : '🚀 توليد التصميم الذكي' }}
            </button>
          </div>

          <!-- محرر الإعدادات المرئي -->
          <div class="settings-form-card">
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
        </div>
      </section>

      <!-- ── 5. تبويب الأدمن المركزي (Admin Panel) ── -->
      <!-- يظهر حصراً للأدمن العام للمنصة -->
      <section v-else-if="activeTab === 'admin' && userData.role === 'admin'" class="tab-content-wrap">
        <h2 class="section-title" style="margin-bottom: 1rem;">🛡️ لوحة إدارة المنصة المركزية</h2>

        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">إجمالي البوتات</div>
            <div class="kpi-value">{{ adminOverview.stats?.total_bots || 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">إجمالي المشتركين</div>
            <div class="kpi-value">{{ adminOverview.stats?.total_users || 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">إجمالي الطلبات</div>
            <div class="kpi-value">{{ adminOverview.stats?.total_orders || 0 }}</div>
          </div>
          <div class="kpi-card highlight-card">
            <div class="kpi-label">حجم التداول الكلي</div>
            <div class="kpi-value">${{ Number(adminOverview.stats?.total_volume_usd || 0).toFixed(2) }}</div>
          </div>
        </div>

        <div style="margin-top: 1.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <h3 style="font-weight: 800; font-size: 1rem;">أحدث طلبات المنصة</h3>
            <button class="refresh-pill-btn" @click="loadAdminData">🔄 تحديث</button>
          </div>

          <div v-if="adminOrders.length === 0" class="empty-state">
            <div>لا توجد طلبات مسجلة حالياً</div>
          </div>

          <div v-else class="orders-list">
            <div v-for="ao in adminOrders" :key="ao.order_id" class="order-card">
              <div class="order-card-header">
                <div class="order-prod-name">{{ ao.service_name || 'طلب منصة' }}</div>
                <span class="order-status-pill" :class="'status-' + ao.status">{{ formatOrderStatus(ao.status) }}</span>
              </div>
              <div class="order-details-grid">
                <div class="order-meta-item"><span class="meta-label">الطلب:</span><span class="meta-val">#{{ ao.order_id }}</span></div>
                <div class="order-meta-item"><span class="meta-label">المستخدم:</span><span class="meta-val">{{ ao.user_id }}</span></div>
                <div class="order-meta-item"><span class="meta-label">المبلغ:</span><span class="meta-val">${{ Number(ao.price_usd).toFixed(2) }}</span></div>
                <div class="order-meta-item"><span class="meta-label">التاريخ:</span><span class="meta-val">{{ ao.created }}</span></div>
              </div>
              <div v-if="ao.status !== 'refunded'" style="margin-top: 0.5rem; text-align: left;">
                <button class="dual-refund-btn" @click="performDualRefund(ao.order_id)">↩️ استرجاع مزدوج ذري</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ── نافذة تفاصيل وشراء المنتج (Bottom Sheet) ── -->
      <div class="modal-overlay" v-if="selectedProduct" @click.self="closeProduct">
        <div class="bottom-sheet">
          <div class="sheet-drag-handle"></div>
          <div style="text-align: center; margin-bottom: 1rem;">
            <img :src="selectedProduct.image_url || 'https://api.dicebear.com/7.x/icons/svg?seed='+selectedProduct.id" style="width: 72px; height: 72px; border-radius: 1rem; object-fit: cover;" onerror="this.src='https://api.dicebear.com/7.x/icons/svg?seed='+selectedProduct.id">
            <h3 style="font-size: 1.2rem; font-weight: 800; margin-top: 0.5rem;">{{ selectedProduct.name }}</h3>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">{{ selectedProduct.description || 'خدمة رقمية سريعة ومضمونة' }}</p>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1rem; padding: 0.75rem 1rem; background: rgba(255,255,255,0.04); border-radius: 0.75rem; border: 1px solid var(--card-border);">
            <span style="font-size: 0.85rem; color: var(--text-muted);">السعر الإجمالي:</span>
            <span style="font-size: 1.3rem; font-weight: 900; color: var(--success);">${{ Number(selectedProduct.price_usd).toFixed(2) }}</span>
          </div>

          <!-- خانة البيانات المطلوبة -->
          <div v-if="selectedProduct.input_label" style="margin-bottom: 1rem;">
            <label style="font-size: 0.8rem; font-weight: 700; display: block; margin-bottom: 0.35rem;">{{ selectedProduct.input_label }}:</label>
            <input type="text" class="search-input" v-model="orderTargetInput" placeholder="أدخل البيانات المطلوبة بدقة...">
          </div>

          <!-- شرط الموافقة على الشروط -->
          <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; margin-bottom: 1.25rem; cursor: pointer;">
            <input type="checkbox" v-model="agreedToTerms" style="width: 18px; height: 18px; accent-color: var(--primary);">
            <span>أوافق على <a href="javascript:void(0)" @click.stop="showTermsModal = true" style="color: var(--primary); text-decoration: underline;">شروط وسياسات المتجر</a> وسياسة الاسترجاع</span>
          </label>

          <!-- نتيجة الشراء الناجح -->
          <div v-if="orderSuccessData" style="background: rgba(16,185,129,0.15); border: 1px solid var(--success); padding: 1rem; border-radius: 0.75rem; margin-bottom: 1rem; text-align: center;">
            <div style="font-weight: 800; color: var(--success); margin-bottom: 0.25rem;">🎉 تم تنفيذ الطلب بنجاح!</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">رقم الطلب: #{{ orderSuccessData.order_id }}</div>
            <div v-if="orderSuccessData.voucher" class="order-voucher-box" style="margin-top: 0.5rem;">
              <div class="voucher-title">⚡ كود التفعيل:</div>
              <div class="voucher-val-row">
                <code class="voucher-code-text">{{ orderSuccessData.voucher }}</code>
                <button class="copy-voucher-btn" @click="copyText(orderSuccessData.voucher, 'تم نسخ الكود! ✅')">📋 نسخ</button>
              </div>
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

      <!-- ── نافذة إضافة منتج جديد للبائع ── -->
      <div class="modal-overlay" v-if="showAddProductModal" @click.self="showAddProductModal = false">
        <div class="bottom-sheet">
          <div class="sheet-drag-handle"></div>
          <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 1rem;">➕ إضافة منتج جديد للمتجر</h3>

          <div class="form-group">
            <label class="form-label">اسم المنتج:</label>
            <input type="text" class="search-input" v-model="newProductForm.name" placeholder="مثال: شحن 60 شدة ببجي">
          </div>

          <div class="form-group">
            <label class="form-label">الفئة:</label>
            <select class="search-input" v-model="newProductForm.category_id">
              <option value="games">🎮 ألعاب وشحن</option>
              <option value="subscriptions">🎬 اشتراكات وبرامج</option>
              <option value="cards">💳 بطاقات وقسائم</option>
              <option value="numbers">📱 أرقام وتفعيل</option>
              <option value="custom">⭐ منتجات حصرية</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">السعر بالدولار ($):</label>
            <input type="number" step="0.1" class="search-input" v-model="newProductForm.price_usd" placeholder="1.00">
          </div>

          <div class="form-group">
            <label class="form-label">وصف المنتج:</label>
            <textarea class="search-input" style="height: 60px;" v-model="newProductForm.description" placeholder="اكتب وصفاً جذاباً ومختصراً..."></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">البيانات المطلوبة من المشتري:</label>
            <input type="text" class="search-input" v-model="newProductForm.input_label" placeholder="مثال: آيدي الحساب (ID) أو رقم الهاتف">
          </div>

          <div class="form-group">
            <label class="form-label">رابط صورة المنتج:</label>
            <input type="text" class="search-input" v-model="newProductForm.image_url" placeholder="https://example.com/image.png (اختياري)">
          </div>

          <div class="form-group">
            <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; cursor: pointer; margin-bottom: 0.5rem;">
              <input type="checkbox" v-model="newProductForm.is_instant" style="width: 16px; height: 16px;">
              <span>تسليم فوري (أكواد وقسائم جاهزة)</span>
            </label>
            <div v-if="newProductForm.is_instant">
              <textarea class="search-input" style="height: 70px;" v-model="newProductForm.raw_codes" placeholder="أدخل الأكواد الجاهزة (كود في كل سطر)..."></textarea>
            </div>
          </div>

          <button class="quick-charge-btn" @click="submitAddProduct" :disabled="savingProduct" style="width: 100%; justify-content: center; padding: 0.8rem; margin-top: 0.5rem;">
            {{ savingProduct ? '⏳ جاري الحفظ...' : '✅ نشر المنتج في المتجر' }}
          </button>
        </div>
      </div>

      <!-- ── نافذة شروط وسياسات المتجر ── -->
      <div class="modal-overlay" v-if="showTermsModal" @click.self="showTermsModal = false">
        <div class="bottom-sheet">
          <div class="sheet-drag-handle"></div>
          <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 1rem;">📜 شروط وسياسات المتجر</h3>

          <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 1rem; padding: 1rem; margin-bottom: 1rem;">
            <div style="font-weight: 800; font-size: 0.9rem; color: var(--primary); margin-bottom: 0.35rem;">شروط تقديم الخدمة:</div>
            <p style="font-size: 0.82rem; color: var(--text); line-height: 1.6; white-space: pre-wrap;">{{ sellerSettings.terms_text || 'جميع الخدمات الرقمية يتم تنفيذها بأعلى معايير الأمان والسرعة. يرجى التأكد من صحة البيانات المدخلة قبل الدفع.' }}</p>
          </div>

          <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 1rem; padding: 1rem; margin-bottom: 1rem;">
            <div style="font-weight: 800; font-size: 0.9rem; color: var(--success); margin-bottom: 0.35rem;">🛡️ سياسة الاسترجاع والضمان:</div>
            <p style="font-size: 0.82rem; color: var(--text); line-height: 1.6; white-space: pre-wrap;">{{ sellerSettings.policy_text || 'في حال تعذر إكمال الطلب أو حدوث أي خطأ تقني، يحق للمشتري استرجاع كامل المبلغ تلقائياً وفورياً إلى رصيد محفظته بالبوت.' }}</p>
          </div>

          <button class="quick-charge-btn" @click="showTermsModal = false" style="width: 100%; justify-content: center; padding: 0.75rem;">
            فهمت وموافق 👍
          </button>
        </div>
      </div>

      <!-- ── شريط التنقل السفلي الثابت (Bottom Nav) ── -->
      <!-- يظهر للمشتري فقط: المتجر، طلباتي، حسابي -->
      <!-- يظهر للبائع: + لوحة البائع -->
      <!-- يظهر للأدمن: + الأدمن -->
      <nav class="bottom-nav">
        <div class="nav-tab" :class="{ active: activeTab === 'store' }" @click="activeTab = 'store'">
          <span class="nav-tab-icon">🏪</span>
          <span>المتجر</span>
        </div>
        <div class="nav-tab" :class="{ active: activeTab === 'orders' }" @click="activeTab = 'orders'">
          <span class="nav-tab-icon">📦</span>
          <span>طلباتي</span>
        </div>
        <div class="nav-tab" :class="{ active: activeTab === 'account' }" @click="activeTab = 'account'">
          <span class="nav-tab-icon">👤</span>
          <span>حسابي</span>
        </div>
        <div class="nav-tab" v-if="userData.role === 'seller' || userData.role === 'admin'" :class="{ active: activeTab === 'seller' }" @click="activeTab = 'seller'">
          <span class="nav-tab-icon">👑</span>
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

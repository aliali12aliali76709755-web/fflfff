"""عرض وتخديم صفحة التطبيق المصغر الموحدة الشاملة (Unified Mini App View Renderer)."""
from __future__ import annotations

from aiohttp import web

HTML_SHELL = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>متجر الخدمات الرقمية المعتمد</title>

  <!-- Telegram WebApp SDK -->
  <script src="https://telegram.org/js/telegram-web-app.js"></script>

  <!-- Tailwind CSS & Lucide Icons -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Vue 3 Production -->
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>

  <!-- Google Fonts: Tajawal & Cairo -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Tajawal:wght@400;500;700;800;900&display=swap" rel="stylesheet">

  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Tajawal', 'Cairo', 'sans-serif'],
          },
          colors: {
            brand: {
              50: '#eff6ff',
              100: '#dbeafe',
              400: '#60a5fa',
              500: '#3b82f6',
              600: '#2563eb',
              700: '#1d4ed8',
              900: '#1e3a8a',
            },
            dark: {
              900: '#0b0f19',
              850: '#0f172a',
              800: '#1e293b',
              750: '#243046',
              700: '#334155',
            }
          }
        }
      }
    }
  </script>

  <style>
    * {
      -webkit-tap-highlight-color: transparent;
      user-select: none;
      box-sizing: border-box;
    }
    input, textarea {
      user-select: text;
    }
    body {
      font-family: 'Tajawal', sans-serif;
      background-color: #0b0f19;
      color: #f8fafc;
      overflow-x: hidden;
      padding-bottom: 84px;
    }
    .safe-top {
      padding-top: max(env(safe-area-inset-top), 12px);
    }
    .safe-bottom {
      padding-bottom: max(env(safe-area-inset-bottom), 16px);
    }
    .glass-panel {
      background: rgba(30, 41, 59, 0.75);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .wallet-card-sheen {
      background: linear-gradient(135deg, #1e3a8a 0%, #1e1b4b 50%, #0f172a 100%);
      position: relative;
      overflow: hidden;
      box-shadow: 0 10px 25px -5px rgba(30, 58, 138, 0.45), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .wallet-card-sheen::after {
      content: '';
      position: absolute;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background: linear-gradient(
        60deg,
        rgba(255, 255, 255, 0) 30%,
        rgba(255, 255, 255, 0.08) 50%,
        rgba(255, 255, 255, 0) 70%
      );
      transform: rotate(25deg);
      pointer-events: none;
      animation: sheen 6s infinite linear;
    }
    @keyframes sheen {
      0% { transform: translateX(-100%) rotate(25deg); }
      100% { transform: translateX(100%) rotate(25deg); }
    }
    ::-webkit-scrollbar {
      width: 4px;
      height: 4px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.15);
      border-radius: 4px;
    }
    .skeleton-box {
      background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
      background-size: 200% 100%;
      animation: skeleton-loading 1.5s infinite;
    }
    @keyframes skeleton-loading {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    [v-cloak] { display: none; }
  </style>
</head>
<body class="bg-dark-900 text-slate-100">

  <div id="app" v-cloak>
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- 1. LOADING SKELETON STATE                                             -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="loading" class="p-4 space-y-4 max-w-md mx-auto safe-top">
      <div class="flex items-center justify-between">
        <div class="h-10 w-32 skeleton-box rounded-xl"></div>
        <div class="h-10 w-24 skeleton-box rounded-xl"></div>
      </div>
      <div class="h-44 w-full skeleton-box rounded-2xl"></div>
      <div class="h-12 w-full skeleton-box rounded-xl"></div>
      <div class="grid grid-cols-2 gap-3">
        <div class="h-48 skeleton-box rounded-2xl"></div>
        <div class="h-48 skeleton-box rounded-2xl"></div>
        <div class="h-48 skeleton-box rounded-2xl"></div>
        <div class="h-48 skeleton-box rounded-2xl"></div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- 2. MAINTENANCE MODE STATE                                            -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-else-if="store?.maintenanceMode && role !== 'admin' && role !== 'seller'" class="min-h-screen flex flex-col items-center justify-center p-6 text-center">
      <div class="w-20 h-20 bg-amber-500/20 text-amber-400 rounded-full flex items-center justify-center mb-4 text-3xl">
        🛠️
      </div>
      <h2 class="text-2xl font-bold mb-2">المتجر في وضع الصيانة</h2>
      <p class="text-slate-400 text-sm max-w-xs mb-6">
        نقوم حالياً بإجراء تحديثات وتحسينات لخدمتكم بشكل أفضل، يرجى المحاولة بعد قليل.
      </p>
      <button @click="initApp" class="px-6 py-2.5 bg-brand-600 rounded-xl font-bold text-sm shadow-lg shadow-brand-600/30">
        إعادة المحاولة 🔄
      </button>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- 3. MAIN APPLICATION VIEW                                              -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-else class="max-w-md mx-auto min-h-screen flex flex-col">

      <!-- ── TOP HEADER (Fixed / Sticky) ─────────────────────────────────── -->
      <header class="sticky top-0 z-40 glass-panel border-b border-slate-800/80 px-4 py-3 safe-top flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <img :src="store.logoUrl || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=120&q=80'" class="w-9 h-9 rounded-xl object-cover ring-1 ring-white/10 shadow-sm" alt="logo" onerror="this.src='https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=120&q=80'">
          <div>
            <h1 class="font-black text-sm text-slate-100 leading-tight">{{ store.storeName || 'متجر الخدمات الرقمية' }}</h1>
            <span class="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              متصل الآن
            </span>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- Balance Pill -->
          <div class="bg-dark-800/90 border border-slate-700/60 rounded-xl px-2.5 py-1.5 flex items-center gap-1.5 shadow-inner">
            <span class="text-xs text-amber-400">💰</span>
            <span class="text-xs font-black tracking-tight text-slate-100">${{ (user.balance || 0).toFixed(2) }}</span>
          </div>
          <!-- Quick Recharge Button -->
          <button @click="showDepositModal = true" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs px-3 py-1.5 rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-1 transition active:scale-95">
            <span>+</span>
            <span>شحن</span>
          </button>
        </div>
      </header>

      <!-- ── MAIN CONTENT TABS ───────────────────────────────────────────── -->
      <main class="flex-1 p-4 space-y-4">

        <!-- ──────────────────────────────────────────────────────────────── -->
        <!-- TAB 1: STOREFRONT (🛍️ المتجر)                                    -->
        <!-- ──────────────────────────────────────────────────────────────── -->
        <div v-if="currentTab === 'store'" class="space-y-4">

          <!-- WALLET CARD (Credit/Debit Card Sheen Style) -->
          <div class="wallet-card-sheen rounded-2xl p-4 text-white relative flex flex-col justify-between min-h-[160px] border border-blue-500/20">
            <!-- Top Card Row -->
            <div class="flex items-center justify-between z-10">
              <div class="flex items-center gap-2">
                <!-- Golden Smart Chip -->
                <div class="w-9 h-7 rounded-md bg-gradient-to-tr from-amber-400 via-amber-200 to-amber-500 shadow-sm flex items-center justify-center p-0.5 ring-1 ring-amber-300/40">
                  <div class="w-full h-full border border-amber-700/40 rounded flex flex-col justify-around py-0.5">
                    <div class="h-px bg-amber-800/30 w-full"></div>
                    <div class="h-px bg-amber-800/30 w-full"></div>
                  </div>
                </div>
                <span class="text-xs font-semibold text-blue-200 tracking-wide">رصيد المتجر الإلكتروني</span>
              </div>
              <span class="text-[11px] font-bold text-emerald-300 bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-500/30">
                {{ store.currency || 'USD' }}
              </span>
            </div>

            <!-- Middle Card Row: Balance -->
            <div class="my-2 z-10">
              <div class="text-[11px] text-blue-300/80 mb-0.5">الرصيد المتاح للاستخدام:</div>
              <div class="text-3xl font-black tracking-tight text-white flex items-baseline gap-1">
                <span class="text-xl font-bold text-emerald-400">$</span>
                <span>{{ (user.balance || 0).toFixed(2) }}</span>
              </div>
            </div>

            <!-- Bottom Card Row: User Info & Masked ID -->
            <div class="flex items-end justify-between z-10 pt-2 border-t border-white/10 text-xs">
              <div>
                <div class="font-bold text-slate-100">{{ user.firstName || 'عميل المتجر' }}</div>
                <div class="text-[10px] text-blue-200/70 font-mono">@{{ user.username || 'user' }}</div>
              </div>
              <div class="font-mono text-xs tracking-widest text-slate-300">
                •••• {{ String(user.telegramId || 9062).slice(-4) }}
              </div>
            </div>
          </div>

          <!-- BANNER CAROUSEL -->
          <div v-if="themeSettings.banners && themeSettings.banners.length" class="relative rounded-2xl overflow-hidden shadow-lg border border-slate-800">
            <div class="relative h-32 w-full overflow-hidden">
              <img :src="themeSettings.banners[activeBannerIndex]?.imageUrl" class="w-full h-full object-cover transition-all duration-500" alt="banner">
              <div class="absolute inset-0 bg-gradient-to-t from-dark-900/90 via-dark-900/30 to-transparent flex items-end p-3">
                <h3 class="text-xs font-bold text-white line-clamp-1">
                  {{ themeSettings.banners[activeBannerIndex]?.title }}
                </h3>
              </div>
            </div>
            <!-- Indicators -->
            <div v-if="themeSettings.banners.length > 1" class="absolute bottom-2 left-3 flex gap-1">
              <span v-for="(_, idx) in themeSettings.banners" :key="idx" 
                    @click="activeBannerIndex = idx"
                    :class="['w-1.5 h-1.5 rounded-full transition-all cursor-pointer', activeBannerIndex === idx ? 'bg-white w-4' : 'bg-white/40']">
              </span>
            </div>
          </div>

          <!-- SMART FUZZY SEARCH BAR -->
          <div class="space-y-2">
            <div class="relative">
              <input v-model="searchQuery" 
                     type="text" 
                     placeholder="ابحث عن لعبة، اشتراك، خدمة، رقم تفعيل..." 
                     class="w-full bg-dark-800/90 border border-slate-700/80 rounded-xl px-9 py-2.5 text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:border-brand-500 transition shadow-inner">
              <span class="absolute right-3 top-3 text-slate-400 text-xs">🔍</span>
              <button v-if="searchQuery" @click="searchQuery = ''" class="absolute left-3 top-3 text-slate-400 text-xs">✕</button>
            </div>

            <!-- Recent Searches Pills -->
            <div v-if="recentSearches.length && !searchQuery" class="flex items-center gap-1.5 overflow-x-auto py-1 text-[11px]">
              <span class="text-slate-400 text-[10px] whitespace-nowrap">مقترحات:</span>
              <button v-for="term in recentSearches" :key="term" @click="searchQuery = term" class="bg-dark-800 border border-slate-700/60 px-2 py-0.5 rounded-lg text-slate-300 hover:text-white whitespace-nowrap">
                {{ term }}
              </button>
            </div>
          </div>

          <!-- CATEGORIES FILTER -->
          <div class="flex gap-2 overflow-x-auto pb-1 text-xs">
            <button @click="selectedCategory = 'all'" 
                    :class="['px-3.5 py-2 rounded-xl font-bold whitespace-nowrap transition shadow-sm', 
                            selectedCategory === 'all' ? 'bg-brand-600 text-white' : 'bg-dark-800 text-slate-300 border border-slate-700/60']">
              🌟 جميع الأقسام
            </button>
            <button v-for="cat in categories" :key="cat.name || cat.id" 
                    @click="selectedCategory = cat.id || cat.name" 
                    :class="['px-3.5 py-2 rounded-xl font-bold whitespace-nowrap transition shadow-sm', 
                            (selectedCategory === cat.id || selectedCategory === cat.name) ? 'bg-brand-600 text-white' : 'bg-dark-800 text-slate-300 border border-slate-700/60']">
              {{ cat.icon || '' }} {{ cat.nameAr || cat.name }}
            </button>
          </div>

          <!-- PRODUCTS GRID -->
          <div v-if="filteredProducts.length" class="grid grid-cols-2 gap-3">
            <div v-for="prod in filteredProducts" :key="prod.id" 
                 @click="openProductModal(prod)"
                 class="bg-dark-800/90 border border-slate-700/60 rounded-2xl p-2.5 flex flex-col justify-between hover:border-slate-600 transition active:scale-98 shadow-sm cursor-pointer relative overflow-hidden group">
              
              <!-- Badge: Discount -->
              <span v-if="prod.discountPercent > 0" class="absolute top-2 right-2 z-10 bg-rose-600 text-white text-[10px] font-black px-1.5 py-0.5 rounded-md shadow">
                خصم {{ prod.discountPercent }}% 🔥
              </span>

              <!-- Product Image -->
              <div class="w-full h-28 rounded-xl bg-dark-900 overflow-hidden mb-2 relative">
                <img :src="(prod.mediaUrls && prod.mediaUrls[0]) || prod.image_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=300&q=80'" 
                     class="w-full h-full object-cover group-hover:scale-105 transition duration-300" 
                     alt="product"
                     onerror="this.src='https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=300&q=80'">
              </div>

              <!-- Product Info -->
              <div class="flex-1 flex flex-col justify-between">
                <div>
                  <h4 class="font-bold text-xs text-slate-100 line-clamp-1 mb-1">{{ prod.nameAr || prod.name }}</h4>
                  <p class="text-[10px] text-slate-400 line-clamp-1 mb-2">{{ prod.description }}</p>
                </div>

                <!-- Price & Order Action -->
                <div class="flex items-center justify-between pt-1 border-t border-slate-700/40">
                  <div>
                    <div v-if="prod.discountPercent > 0" class="text-[9px] text-slate-400 line-through">
                      ${{ getOriginalPrice(prod) }}
                    </div>
                    <div class="text-xs font-black text-emerald-400">
                      ${{ getEffectivePrice(prod) }}
                    </div>
                  </div>
                  <button class="bg-brand-600/30 text-brand-400 border border-brand-500/30 w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs group-hover:bg-brand-600 group-hover:text-white transition">
                    🛒
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div v-else class="text-center py-12 bg-dark-800/40 rounded-2xl border border-dashed border-slate-800">
            <span class="text-3xl mb-2 block">🔍</span>
            <h4 class="font-bold text-sm text-slate-300">لا توجد منتجات مطابقة للبحث</h4>
            <p class="text-xs text-slate-500 mt-1">جرب البحث بكلمات أخرى أو اختر قسماً آخر</p>
          </div>

        </div>

        <!-- ──────────────────────────────────────────────────────────────── -->
        <!-- TAB 2: MY ORDERS (📦 طلباتي)                                      -->
        <!-- ──────────────────────────────────────────────────────────────── -->
        <div v-if="currentTab === 'orders'" class="space-y-3">
          <div class="flex items-center justify-between mb-2">
            <h3 class="font-black text-sm text-slate-100">سجل طلباتي</h3>
            <span class="text-xs text-slate-400">{{ myOrders.length }} طلبات</span>
          </div>

          <div v-if="myOrders.length" class="space-y-2.5">
            <div v-for="order in myOrders" :key="order.id" class="bg-dark-800/90 border border-slate-700/60 rounded-xl p-3 space-y-2 shadow-sm">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-slate-100">{{ order.product_name }}</span>
                <!-- Status Badge -->
                <span :class="['text-[10px] font-bold px-2 py-0.5 rounded-full border', getStatusBadgeClass(order.status)]">
                  {{ getStatusLabelAr(order.status) }}
                </span>
              </div>

              <div class="flex items-center justify-between text-[11px] text-slate-400">
                <span>رقم الطلب: <span class="font-mono text-slate-300">{{ order.order_ref }}</span></span>
                <span class="font-black text-emerald-400">${{ Number(order.total_price).toFixed(2) }}</span>
              </div>

              <!-- Delivery details if completed -->
              <div v-if="order.delivery_data && order.status === 'completed'" class="bg-emerald-950/40 border border-emerald-500/30 rounded-lg p-2 text-xs text-emerald-200">
                <div class="font-bold mb-1 flex items-center justify-between">
                  <span>بيانات التسليم:</span>
                  <button @click="copyToClipboard(order.delivery_data)" class="text-[10px] text-emerald-300 bg-emerald-800/40 px-1.5 py-0.5 rounded">نسخ 📋</button>
                </div>
                <div class="font-mono text-[11px] break-all">{{ order.delivery_data }}</div>
              </div>

              <!-- Rejection note if canceled / refunded -->
              <div v-if="order.rejection_reason" class="bg-rose-950/40 border border-rose-500/30 rounded-lg p-2 text-xs text-rose-200">
                <span class="font-bold">ملاحظة: </span>{{ order.rejection_reason }}
              </div>
            </div>
          </div>

          <div v-else class="text-center py-12 bg-dark-800/40 rounded-2xl border border-dashed border-slate-800">
            <span class="text-3xl mb-2 block">📦</span>
            <h4 class="font-bold text-sm text-slate-300">لم تقم بإجراء أي طلبات حتى الآن</h4>
            <button @click="currentTab = 'store'" class="mt-3 px-4 py-2 bg-brand-600 rounded-xl text-xs font-bold shadow">
              تصفح المنتجات الآن
            </button>
          </div>
        </div>

        <!-- ──────────────────────────────────────────────────────────────── -->
        <!-- TAB 3: MY ACCOUNT (👤 حسابي) - المشتري والإحالة والدعم والضمان     -->
        <!-- ──────────────────────────────────────────────────────────────── -->
        <div v-if="currentTab === 'account'" class="space-y-4">

          <!-- User Profile Card -->
          <div class="bg-gradient-to-br from-dark-800 via-dark-850 to-dark-800 border border-slate-700/80 rounded-2xl p-4 shadow-lg flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center text-xl font-black text-white shadow-md shadow-brand-600/30 ring-2 ring-white/10">
                {{ (user.firstName || 'U')[0] }}
              </div>
              <div>
                <h3 class="font-black text-sm text-white">{{ user.firstName || 'عميل المتجر' }}</h3>
                <div class="text-[11px] text-slate-400 font-mono">@{{ user.username || 'user' }}</div>
                <div class="text-[10px] text-slate-500 font-mono">ID: {{ user.telegramId || '0' }}</div>
              </div>
            </div>

            <span :class="['text-[10px] font-bold px-2.5 py-1 rounded-full border',
                           role === 'admin' ? 'bg-rose-950/60 text-rose-300 border-rose-500/40' :
                           role === 'seller' ? 'bg-amber-950/60 text-amber-300 border-amber-500/40' :
                           'bg-blue-950/60 text-blue-300 border-blue-500/40']">
              {{ role === 'admin' ? 'مدير المنصة 🛡️' : (role === 'seller' ? 'مالك المتجر 👑' : 'مشتري معتمد ⭐') }}
            </span>
          </div>

          <!-- Quick Balance & Top-up Card -->
          <div class="bg-dark-800/90 border border-slate-700/60 rounded-2xl p-4 flex items-center justify-between shadow-sm">
            <div>
              <span class="text-xs text-slate-400">رصيدك المتاح الحالي:</span>
              <div class="text-2xl font-black text-emerald-400">${{ (user.balance || 0).toFixed(2) }}</div>
            </div>
            <button @click="showDepositModal = true" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-1.5 transition active:scale-95">
              <span>➕</span>
              <span>شحن المحفظة</span>
            </button>
          </div>

          <!-- Referral System Box -->
          <div class="bg-gradient-to-br from-indigo-950/70 via-dark-850 to-purple-950/60 border border-indigo-500/30 rounded-2xl p-4 space-y-3">
            <div class="flex items-center gap-2">
              <span class="text-2xl">🎁</span>
              <div>
                <h4 class="font-black text-xs text-white">نظام الإحالة والمكافآت المالية</h4>
                <p class="text-[10px] text-indigo-200">احصل على نسبة 5% رصيد فوري في محفظتك عن كل طلب يقوم به أصدقاؤك!</p>
              </div>
            </div>

            <div class="bg-dark-900/90 border border-slate-700/80 rounded-xl p-2.5 flex items-center justify-between gap-2">
              <span class="text-xs font-mono text-slate-300 truncate max-w-[200px]">
                {{ getReferralLink() }}
              </span>
              <button @click="copyToClipboard(getReferralLink())" class="bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg shadow whitespace-nowrap active:scale-95 transition">
                نسخ الرابط 📋
              </button>
            </div>
          </div>

          <!-- Technical Support VIP Card -->
          <div class="bg-gradient-to-br from-emerald-950/60 via-dark-850 to-teal-950/50 border border-emerald-500/40 rounded-2xl p-4 space-y-3 shadow-lg">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-2xl">💬</span>
                <div>
                  <h4 class="font-black text-xs text-white">مركز خدمة العملاء والدعم الفني</h4>
                  <p class="text-[10px] text-slate-300">متواجدون على مدار الساعة لخدمتكم فورياً</p>
                </div>
              </div>
              <span class="text-[10px] bg-emerald-500/20 text-emerald-400 font-bold px-2 py-0.5 rounded-full border border-emerald-500/30 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                24/7 متاح الآن
              </span>
            </div>

            <p class="text-[11px] text-slate-300 leading-relaxed">
              إذا كان لديك أي استفسار أو واجهت أي مشكلة في طلبك، فريق الدعم الفني جاهز لمساعدتك والرد خلال دقائق معدودة.
            </p>

            <div class="grid grid-cols-2 gap-2 pt-1">
              <a :href="store.supportUrl || ('https://t.me/' + (store.botUsername || 'bot'))" target="_blank" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs py-2 px-3 rounded-xl shadow text-center flex items-center justify-center gap-1 transition">
                <span>تواصل مع الدعم</span>
                <span>↗️</span>
              </a>
              <button @click="copyToClipboard(store.supportUrl || ('@' + (store.botUsername || 'bot')))" class="bg-dark-800 hover:bg-dark-750 border border-emerald-500/30 text-emerald-300 font-bold text-xs py-2 px-3 rounded-xl transition text-center">
                نسخ معرف الدعم 📋
              </button>
            </div>
          </div>

          <!-- Store Terms & Golden Guarantee Card -->
          <div class="bg-dark-800/90 border border-amber-500/30 rounded-2xl p-4 space-y-3 shadow-sm">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-2xl">🛡️</span>
                <div>
                  <h4 class="font-black text-xs text-amber-300">الضمان الذهبي وسياسة الاستخدام</h4>
                  <p class="text-[10px] text-slate-400">حماية كاملة وحقوق مضمونة 100%</p>
                </div>
              </div>
              <span class="text-[10px] bg-amber-500/20 text-amber-300 font-bold px-2 py-0.5 rounded-full border border-amber-500/30">
                ضمان ذهبي ⭐
              </span>
            </div>

            <!-- Guarantee Policy -->
            <div class="bg-dark-900/80 border border-amber-500/20 rounded-xl p-3 text-xs text-amber-200 leading-relaxed">
              <div class="font-bold mb-1 text-amber-300 flex items-center gap-1">
                <span>✅</span> سياسة الاسترجاع الفوري:
              </div>
              <p class="text-[11px] text-slate-300">
                {{ store.policyText || 'في حال تعذر تنفيذ أي طلب أو حدوث أي خطأ تقني، يحق للمشتري استرجاع كامل المبلغ تلقائياً وفورياً إلى رصيد محفظته بالبوت دون أي خصومات.' }}
              </p>
            </div>

            <!-- Terms -->
            <div class="text-[11px] text-slate-400 space-y-1">
              <div class="font-bold text-slate-300">شروط تقديم الخدمة:</div>
              <p class="leading-relaxed">
                {{ store.termsText || 'جميع الخدمات الرقمية يتم تنفيذها بأعلى معايير الأمان والسرعة. يرجى التأكد من صحة البيانات المدخلة قبل الدفع.' }}
              </p>
            </div>
          </div>

        </div>

        <!-- ──────────────────────────────────────────────────────────────── -->
        <!-- TAB 4: SELLER IN-APP DASHBOARD (⚙️ إدارتي - للمالك فقط)           -->
        <!-- ──────────────────────────────────────────────────────────────── -->
        <div v-if="currentTab === 'seller' && (role === 'seller' || role === 'admin')" class="space-y-4">
          <div class="flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 class="font-black text-sm text-slate-100 flex items-center gap-1.5">
              <span>⚙️</span> لوحة إدارة المتجر (خاصة بالمالك)
            </h3>
            <span class="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full font-bold">بائع معتمد ⭐</span>
          </div>

          <!-- Stats Grid -->
          <div class="grid grid-cols-2 gap-2.5">
            <div class="bg-dark-800/90 border border-slate-700/60 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">إجمالي الطلبات</span>
              <div class="text-xl font-black text-slate-100">{{ sellerStats.totalOrders || 0 }}</div>
            </div>
            <div class="bg-dark-800/90 border border-slate-700/60 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">المبيعات الكلية</span>
              <div class="text-xl font-black text-emerald-400">${{ (sellerStats.totalSales || 0).toFixed(2) }}</div>
            </div>
            <div class="bg-dark-800/90 border border-slate-700/60 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">صافي الأرباح</span>
              <div class="text-xl font-black text-teal-400">${{ (sellerStats.totalProfit || 0).toFixed(2) }}</div>
            </div>
            <div class="bg-dark-800/90 border border-slate-700/60 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">طلبات بانتظار التسليم</span>
              <div class="text-xl font-black text-amber-400">{{ sellerStats.pendingOrders || 0 }}</div>
            </div>
          </div>

          <!-- Interactive Analytics Chart Card -->
          <div class="bg-dark-800/90 border border-slate-700/70 rounded-2xl p-4 space-y-3 shadow-lg">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1.5">
                <span class="text-base">📈</span>
                <div>
                  <h4 class="font-black text-xs text-white">المخطط التحليلي وتفاعل البوت</h4>
                  <p class="text-[10px] text-slate-400">تحليل حي لحركة الطلبات والأرباح ونسب الإلغاء</p>
                </div>
              </div>
              <div class="flex items-center gap-1 bg-dark-900/80 p-0.5 rounded-xl border border-slate-700">
                <button @click="chartMetric = 'orders'" :class="['px-2 py-1 rounded-lg text-[10px] font-bold transition', chartMetric === 'orders' ? 'bg-brand-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
                  الطلبات 📦
                </button>
                <button @click="chartMetric = 'profit'" :class="['px-2 py-1 rounded-lg text-[10px] font-bold transition', chartMetric === 'profit' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
                  الأرباح 💰
                </button>
                <button @click="chartMetric = 'canceled'" :class="['px-2 py-1 rounded-lg text-[10px] font-bold transition', chartMetric === 'canceled' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
                  الإلغاءات ❌
                </button>
              </div>
            </div>

            <!-- SVG Animated Chart -->
            <div class="relative w-full h-36 bg-dark-900/90 rounded-xl p-2 border border-slate-800 overflow-hidden flex flex-col justify-between">
              <svg viewBox="0 0 320 100" class="w-full h-24 overflow-visible">
                <defs>
                  <linearGradient id="chartGradOrders" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.45" />
                    <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.0" />
                  </linearGradient>
                  <linearGradient id="chartGradProfit" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#10b981" stop-opacity="0.45" />
                    <stop offset="100%" stop-color="#10b981" stop-opacity="0.0" />
                  </linearGradient>
                  <linearGradient id="chartGradCanceled" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#f43f5e" stop-opacity="0.45" />
                    <stop offset="100%" stop-color="#f43f5e" stop-opacity="0.0" />
                  </linearGradient>
                </defs>

                <!-- Grid lines -->
                <line x1="10" y1="20" x2="310" y2="20" stroke="#334155" stroke-dasharray="3 3" stroke-width="0.5" />
                <line x1="10" y1="50" x2="310" y2="50" stroke="#334155" stroke-dasharray="3 3" stroke-width="0.5" />
                <line x1="10" y1="80" x2="310" y2="80" stroke="#334155" stroke-dasharray="3 3" stroke-width="0.5" />

                <!-- Area Fill -->
                <polygon :points="getChartAreaPoints()" :fill="chartMetric === 'profit' ? 'url(#chartGradProfit)' : (chartMetric === 'canceled' ? 'url(#chartGradCanceled)' : 'url(#chartGradOrders)')" />

                <!-- Line -->
                <polyline :points="getChartLinePoints()" fill="none" :stroke="chartMetric === 'profit' ? '#10b981' : (chartMetric === 'canceled' ? '#f43f5e' : '#3b82f6')" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />

                <!-- Data Points -->
                <circle v-for="(pt, idx) in getChartPointsList()" :key="idx" :cx="pt.x" :cy="pt.y" r="3.5" :fill="chartMetric === 'profit' ? '#10b981' : (chartMetric === 'canceled' ? '#f43f5e' : '#3b82f6')" stroke="#0f172a" stroke-width="1.5" class="cursor-pointer transition-all hover:r-5" @mouseenter="hoveredPoint = pt" @click="hoveredPoint = pt" />
              </svg>

              <!-- X-Axis Labels -->
              <div class="flex justify-between items-center text-[9px] text-slate-400 px-1 pt-1 border-t border-slate-800/80">
                <span v-for="d in (sellerStats.recentChart || [])" :key="d.date">{{ d.day_name?.slice(0, 3) || d.date.slice(5) }}</span>
              </div>
            </div>

            <!-- Active Point Details Strip -->
            <div v-if="hoveredPoint" class="bg-dark-900/80 rounded-xl p-2 border border-slate-700/60 flex items-center justify-between text-[11px]">
              <span class="text-slate-300 font-bold">📅 {{ hoveredPoint.day_name }} ({{ hoveredPoint.date }}):</span>
              <span class="font-mono font-black" :class="chartMetric === 'profit' ? 'text-emerald-400' : (chartMetric === 'canceled' ? 'text-rose-400' : 'text-blue-400')">
                {{ chartMetric === 'profit' ? '+$' + hoveredPoint.profit : (chartMetric === 'canceled' ? hoveredPoint.canceled + ' ملغي' : hoveredPoint.orders + ' طلب') }}
              </span>
            </div>

            <!-- KPI Micro Breakdown -->
            <div class="grid grid-cols-3 gap-2 pt-1 text-center">
              <div class="bg-dark-900/60 p-2 rounded-xl border border-slate-800">
                <span class="text-[9px] text-slate-400">نسبة النجاح</span>
                <div class="text-xs font-black text-emerald-400">{{ getSuccessRate() }}%</div>
              </div>
              <div class="bg-dark-900/60 p-2 rounded-xl border border-slate-800">
                <span class="text-[9px] text-slate-400">معدل الإلغاء</span>
                <div class="text-xs font-black text-rose-400">{{ getCancellationRate() }}%</div>
              </div>
              <div class="bg-dark-900/60 p-2 rounded-xl border border-slate-800">
                <span class="text-[9px] text-slate-400">تفاعل حي</span>
                <div class="text-xs font-black text-sky-400 flex items-center justify-center gap-1">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  نشط 🟢
                </div>
              </div>
            </div>
          </div>

          <!-- AI Assistant Banner for Seller -->
          <div class="bg-gradient-to-r from-purple-900/60 to-indigo-900/60 border border-purple-500/40 rounded-2xl p-3 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-2xl">🤖</span>
              <div>
                <h4 class="text-xs font-black text-white">المساعد الذكي لتصميم المتجر</h4>
                <p class="text-[10px] text-purple-200">توليد ألوان وهوية بصرية وبانرات جذابة بنقرة واحدة</p>
              </div>
            </div>
            <button @click="applyAiSuggestions" :disabled="aiLoading" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow transition flex items-center gap-1">
              <span v-if="aiLoading">...⏳</span>
              <span v-else>💡 اقتراح</span>
            </button>
          </div>

          <!-- Seller Action Buttons Grid -->
          <div class="grid grid-cols-4 gap-2">
            <button @click="openCustomizer" class="bg-indigo-600/30 hover:bg-indigo-600 border border-indigo-500/40 text-indigo-200 hover:text-white font-bold text-[10px] py-2.5 rounded-xl transition flex flex-col items-center justify-center gap-1">
              <span class="text-base">🎨</span>
              <span>المظهر</span>
            </button>
            <button @click="openMasterCatalog" class="bg-emerald-600/30 hover:bg-emerald-600 border border-emerald-500/40 text-emerald-200 hover:text-white font-bold text-[10px] py-2.5 rounded-xl transition flex flex-col items-center justify-center gap-1">
              <span class="text-base">📥</span>
              <span>كتالوج</span>
            </button>
            <button @click="openNewProductModal" class="bg-blue-600/30 hover:bg-blue-600 border border-blue-500/40 text-blue-200 hover:text-white font-bold text-[10px] py-2.5 rounded-xl transition flex flex-col items-center justify-center gap-1">
              <span class="text-base">➕</span>
              <span>منتج جديد</span>
            </button>
            <button @click="openBulkModal" class="bg-amber-600/30 hover:bg-amber-600 border border-amber-500/40 text-amber-200 hover:text-white font-bold text-[10px] py-2.5 rounded-xl transition flex flex-col items-center justify-center gap-1">
              <span class="text-base">📑</span>
              <span>إكسل / CSV</span>
            </button>
          </div>

          <!-- Seller Settings Form (Support & Terms & Channel) -->
          <div class="bg-dark-800/90 border border-slate-700/80 rounded-2xl p-4 space-y-3">
            <h4 class="font-bold text-xs text-slate-200 flex items-center gap-1.5">
              <span>⚙️</span> تعديل روابط الدعم الفني وشروط المتجر وقناة الإشعارات
            </h4>

            <div class="space-y-1">
              <label class="text-[11px] font-bold text-slate-300">رابط أو معرف الدعم الفني للعملاء:</label>
              <input v-model="sellerSettingsForm.support_url" type="text" placeholder="https://t.me/support_user أو @support_channel" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
            </div>

            <div class="space-y-1">
              <label class="text-[11px] font-bold text-slate-300">قناة إشعارات الطلبات الفورية (@username أو -100xxx):</label>
              <input v-model="sellerSettingsForm.order_channel" type="text" placeholder="@my_orders_channel أو -100123456789" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
              <p class="text-[10px] text-slate-400">أضف البوت مشرفاً بالقناة، وستصلك كل الطلبات الجديدة فورياً مع أزرار التسليم والاسترجاع داخل القناة.</p>
            </div>

            <div class="space-y-1">
              <label class="text-[11px] font-bold text-slate-300">شروط المتجر وسياسة الاستخدام:</label>
              <textarea v-model="sellerSettingsForm.terms_text" rows="2" placeholder="اكتب شروط تقديم الخدمة..." class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"></textarea>
            </div>

            <div class="space-y-1">
              <label class="text-[11px] font-bold text-slate-300">سياسة الاسترجاع والضمان الذهبي:</label>
              <textarea v-model="sellerSettingsForm.policy_text" rows="2" placeholder="اكتب سياسة استرجاع الأموال والضمان..." class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"></textarea>
            </div>

            <button @click="saveSellerSettingsForm" :disabled="savingSettings" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs py-2.5 rounded-xl shadow transition">
              <span v-if="savingSettings">جاري الحفظ... ⏳</span>
              <span v-else>حفظ إعدادات المتجر والدعم والقناة 💾</span>
            </button>
          </div>

          <!-- Seller Products Management Section -->
          <div class="space-y-2 pt-1">
            <div class="flex items-center justify-between">
              <h4 class="font-bold text-xs text-slate-200 flex items-center gap-1.5">
                <span>📦</span> إدارة منتجات المتجر
              </h4>
              <span class="text-[10px] text-slate-400">{{ sellerProducts.length }} منتج</span>
            </div>

            <div v-if="sellerProducts.length" class="space-y-2">
              <div v-for="prod in sellerProducts" :key="prod.id" class="bg-dark-800 border border-slate-700/80 p-3 rounded-xl flex items-center justify-between text-xs">
                <div class="flex items-center gap-2.5">
                  <div class="w-10 h-10 rounded-lg bg-dark-750 flex items-center justify-center overflow-hidden border border-slate-700">
                    <img v-if="(prod.mediaUrls && prod.mediaUrls[0]) || prod.image_url" :src="(prod.mediaUrls && prod.mediaUrls[0]) || prod.image_url" class="w-full h-full object-cover">
                    <span v-else class="text-base">🛍️</span>
                  </div>
                  <div>
                    <div class="font-bold text-white">{{ prod.nameAr || prod.name }}</div>
                    <div class="text-[10px] text-slate-400">
                      التكلفة: ${{ prod.cost_price || prod.priceOptions?.[0]?.costPrice || 0 }} | البيع: ${{ prod.price_usd || prod.priceOptions?.[0]?.userPrice || 0 }}
                      <span class="text-emerald-400 font-bold mr-1">
                        (ربح: +${{ (((prod.price_usd || prod.priceOptions?.[0]?.userPrice || 0) - (prod.cost_price || prod.priceOptions?.[0]?.costPrice || 0))).toFixed(2) }})
                      </span>
                    </div>
                  </div>
                </div>

                <div class="flex items-center gap-2">
                  <button @click="toggleProductActive(prod.id)" :class="['px-2 py-1 rounded-lg text-[10px] font-bold transition', prod.active !== false ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' : 'bg-slate-800 text-slate-400 border border-slate-700']">
                    {{ prod.active !== false ? 'نشط ✅' : 'معطل ⏸️' }}
                  </button>
                  <button @click="deleteSellerProduct(prod.id)" class="text-rose-400 hover:text-rose-300 p-1">
                    🗑️
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-6 text-xs text-slate-500 bg-dark-800/40 rounded-xl">
              لا توجد منتجات مسجلة، اضغط على "استيراد كتالوج" أو "إضافة منتج" للبدء فوراً!
            </div>
          </div>
        </div>

        <!-- ──────────────────────────────────────────────────────────────── -->
        <!-- TAB 5: SUPER ADMIN DASHBOARD (👑 الأدمن - للأدمن فقط)             -->
        <!-- ──────────────────────────────────────────────────────────────── -->
        <div v-if="currentTab === 'admin' && role === 'admin'" class="space-y-4">
          <div class="flex items-center justify-between border-b border-rose-900/40 pb-2">
            <h3 class="font-black text-sm text-rose-300 flex items-center gap-1.5">
              <span>👑</span> لوحة الأدمن الأعلى للمنصة
            </h3>
            <span class="text-[10px] bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded-full font-bold">Admin Only</span>
          </div>

          <!-- Admin Overview Stats Grid -->
          <div class="grid grid-cols-2 gap-2.5">
            <div class="bg-dark-800/90 border border-rose-900/40 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">إجمالي المتاجر</span>
              <div class="text-xl font-black text-rose-300">{{ adminOverview.totalStores || 1 }}</div>
            </div>
            <div class="bg-dark-800/90 border border-rose-900/40 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">حجم تعاملات المنصة</span>
              <div class="text-xl font-black text-emerald-400">${{ (adminOverview.totalPlatformVolume || 0).toFixed(2) }}</div>
            </div>
            <div class="bg-dark-800/90 border border-rose-900/40 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">إجمالي طلبات المنصة</span>
              <div class="text-xl font-black text-white">{{ adminOverview.totalOrders || 0 }}</div>
            </div>
            <div class="bg-dark-800/90 border border-rose-900/40 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">طلبات معلقة للتنفيذ</span>
              <div class="text-xl font-black text-amber-400">{{ adminOverview.pendingManualOrders || 0 }}</div>
            </div>
          </div>

          <!-- Admin Manual Orders Queue -->
          <div class="space-y-3">
            <h4 class="font-bold text-xs text-slate-300">الطلبات اليدوية والخدمات المعلقة</h4>
            <div v-if="adminOrders.length" class="space-y-2">
              <div v-for="ord in adminOrders" :key="ord.id" class="bg-dark-800 border border-slate-700 p-3 rounded-xl space-y-2 text-xs">
                <div class="flex items-center justify-between">
                  <span class="font-bold text-white">{{ ord.service_name || ord.product_name }}</span>
                  <span class="font-mono text-emerald-400">${{ ord.total_price || ord.price_usd }}</span>
                </div>
                <div class="text-[11px] text-slate-400">
                  العميل: {{ ord.user_id || ord.user_telegram_id }} | المرجع: {{ ord.order_ref || ord.order_id }}
                </div>
                <!-- Target input -->
                <div v-if="ord.target" class="bg-dark-900 p-2 rounded text-[11px] font-mono text-slate-300">
                  بيانات العميل: {{ ord.target }}
                </div>
                <!-- Actions -->
                <div class="flex items-center gap-2 pt-1 border-t border-slate-700/60">
                  <button @click="handleAdminOrderAction(ord.order_ref || ord.order_id, 'deliver')" class="flex-1 bg-emerald-600 hover:bg-emerald-500 py-1.5 rounded-lg text-white font-bold text-[11px]">
                    تسليم ✅
                  </button>
                  <button @click="handleAdminOrderAction(ord.order_ref || ord.order_id, 'refund_both')" class="flex-1 bg-purple-600 hover:bg-purple-500 py-1.5 rounded-lg text-white font-bold text-[11px]">
                    استرجاع 🔄
                  </button>
                  <button @click="handleAdminOrderAction(ord.order_ref || ord.order_id, 'reject')" class="flex-1 bg-rose-600 hover:bg-rose-500 py-1.5 rounded-lg text-white font-bold text-[11px]">
                    رفض ❌
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-6 text-xs text-slate-500 bg-dark-800/30 rounded-xl">
              لا توجد طلبات يدوية معلقة حالياً
            </div>
          </div>
        </div>

      </main>

      <!-- ── BOTTOM NAVIGATION DOCK ──────────────────────────────────────── -->
      <!-- Role isolation: Buyers only see Store, Orders, Account -->
      <nav class="fixed bottom-0 left-0 right-0 z-40 glass-panel border-t border-slate-800 safe-bottom">
        <div class="max-w-md mx-auto flex items-center justify-around py-2">
          <!-- Store Tab -->
          <button @click="currentTab = 'store'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'store' ? 'text-brand-400' : 'text-slate-400']">
            <span class="text-base">🛍️</span>
            <span>المتجر</span>
          </button>
          <!-- Orders Tab -->
          <button @click="currentTab = 'orders'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'orders' ? 'text-brand-400' : 'text-slate-400']">
            <span class="text-base">📦</span>
            <span>طلباتي</span>
          </button>
          <!-- My Account Tab -->
          <button @click="currentTab = 'account'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'account' ? 'text-brand-400' : 'text-slate-400']">
            <span class="text-base">👤</span>
            <span>حسابي</span>
          </button>
          <!-- Seller Tab (Owner/Admin only) -->
          <button v-if="role === 'seller' || role === 'admin'" @click="currentTab = 'seller'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'seller' ? 'text-brand-400' : 'text-slate-400']">
            <span class="text-base">⚙️</span>
            <span>إدارتي</span>
          </button>
          <!-- Admin Tab (Admin only) -->
          <button v-if="role === 'admin'" @click="currentTab = 'admin'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'admin' ? 'text-rose-400' : 'text-slate-400']">
            <span class="text-base">👑</span>
            <span>الأدمن</span>
          </button>
        </div>
      </nav>

      <!-- ════════════════════════════════════════════════════════════════════ -->
      <!-- 4. MODALS & SUB-SCREENS                                              -->
      <!-- ════════════════════════════════════════════════════════════════════ -->

      <!-- A. PRODUCT DETAILS & CHECKOUT MODAL -->
      <div v-if="activeProduct" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
        <div class="bg-dark-850 w-full max-w-md rounded-t-3xl sm:rounded-3xl border border-slate-700/80 p-5 space-y-4 max-h-[90vh] overflow-y-auto">
          
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <h3 class="font-black text-sm text-white">{{ activeProduct.nameAr || activeProduct.name }}</h3>
            <button @click="activeProduct = null" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Product Image -->
          <div class="w-full h-40 rounded-2xl bg-dark-900 overflow-hidden">
            <img :src="(activeProduct.mediaUrls && activeProduct.mediaUrls[0]) || activeProduct.image_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&q=80'" class="w-full h-full object-cover" alt="product">
          </div>

          <p class="text-xs text-slate-300 leading-relaxed">{{ activeProduct.description }}</p>

          <!-- Pricing Options -->
          <div v-if="activeProduct.priceOptions && activeProduct.priceOptions.length" class="space-y-1.5">
            <label class="text-xs font-bold text-slate-300">اختر الباقة أو الفئة:</label>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in activeProduct.priceOptions" :key="opt.id"
                      @click="selectedPriceOption = opt"
                      :class="['p-2.5 rounded-xl border text-xs font-bold transition flex flex-col justify-between items-start',
                              selectedPriceOption?.id === opt.id ? 'border-brand-500 bg-brand-900/30 text-white ring-1 ring-brand-500' : 'border-slate-700 bg-dark-800 text-slate-300']">
                <span>{{ opt.label }}</span>
                <span class="text-emerald-400 font-mono mt-1">${{ opt.userPrice || opt.price }}</span>
              </button>
            </div>
          </div>

          <!-- Quantity Slider for SMM -->
          <div v-if="activeProduct.templateType === 'smm_boost'" class="space-y-2 bg-dark-800/80 p-3 rounded-xl border border-slate-700">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-300 font-bold">الكمية المطلوبة:</span>
              <span class="text-emerald-400 font-mono font-black">{{ smmQuantity }}</span>
            </div>
            <input type="range" min="100" max="10000" step="100" v-model="smmQuantity" class="w-full accent-brand-500">
            <div class="text-[11px] text-slate-400">رابط الحساب أو المنشور:</div>
            <input type="url" v-model="smmUrl" placeholder="https://..." class="w-full bg-dark-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
          </div>

          <!-- Custom Requirements Fields -->
          <div v-if="activeProduct.requirements && activeProduct.requirements.length" class="space-y-2">
            <div v-for="reqField in activeProduct.requirements" :key="reqField.name" class="space-y-1">
              <label class="text-xs font-bold text-slate-300 flex items-center justify-between">
                <span>{{ reqField.label || reqField.name }} <span v-if="reqField.required" class="text-rose-500">*</span></span>
              </label>
              <input v-model="userFormInputs[reqField.name]" 
                     :type="reqField.type || 'text'" 
                     :placeholder="reqField.placeholder || ''"
                     class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500">
            </div>
          </div>

          <!-- Terms Agreement Checkbox -->
          <div class="flex items-center gap-2 pt-2">
            <input type="checkbox" id="termsCheck" v-model="termsAgreed" class="accent-brand-500 w-4 h-4 rounded">
            <label for="termsCheck" class="text-[11px] text-slate-300">
              قرأت الشروط وسياسة الضمان الذهبي وأوافق عليها بالكامل
            </label>
          </div>

          <!-- Submit Order Button -->
          <button @click="submitOrder" 
                  :disabled="isSubmitting || !termsAgreed"
                  class="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 text-white font-black py-3 rounded-xl shadow-lg transition flex items-center justify-center gap-2 text-sm">
            <span v-if="isSubmitting">جاري التنفيذ... ⏳</span>
            <span v-else>تأكيد ودفع ${{ getCalculatedTotal() }} 💳</span>
          </button>
        </div>
      </div>

      <!-- B. DEPOSIT / TOP-UP MODAL -->
      <div v-if="showDepositModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
        <div class="bg-dark-850 w-full max-w-md rounded-t-3xl sm:rounded-3xl border border-slate-700/80 p-5 space-y-4">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <h3 class="font-black text-sm text-white">شحن رصيد المحفظة</h3>
            <button @click="showDepositModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <p class="text-xs text-slate-400">اختر طريقة الشحن لتزويد محفظتك بالرصيد فورياً:</p>

          <div class="space-y-2">
            <button @click="payWithStars" class="w-full bg-dark-800 hover:bg-dark-750 border border-amber-500/30 p-3 rounded-xl flex items-center justify-between text-xs font-bold text-white transition">
              <div class="flex items-center gap-2.5">
                <span class="text-xl">⭐️</span>
                <div class="text-right">
                  <div>نجوم تيليجرام (Telegram Stars)</div>
                  <div class="text-[10px] text-slate-400">دفع فوري وآمن داخل التطبيق</div>
                </div>
              </div>
              <span class="text-amber-400">شحن نجوم ↗️</span>
            </button>

            <button @click="payWithExternalGateway" class="w-full bg-dark-800 hover:bg-dark-750 border border-slate-700 p-3 rounded-xl flex items-center justify-between text-xs font-bold text-white transition">
              <div class="flex items-center gap-2.5">
                <span class="text-xl">💳</span>
                <div class="text-right">
                  <div>بطاقات الدفع ومدى والعملات الرقمية</div>
                  <div class="text-[10px] text-slate-400">فيزا، ماستركارد، Apple Pay، كريبتو</div>
                </div>
              </div>
              <span class="text-emerald-400">بوابة الدفع ↗️</span>
            </button>
          </div>
        </div>
      </div>

      <!-- C. VISUAL THEME CUSTOMIZER MODAL -->
      <div v-if="showThemeCustomizer" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-lg rounded-3xl border border-slate-700/80 p-5 space-y-4 my-auto max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <h3 class="font-black text-sm text-white flex items-center gap-2">
              <span>🎨</span> مخصص المظهر والهوية البصرية
            </h3>
            <button @click="showThemeCustomizer = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Color Customization -->
          <div class="space-y-3">
            <label class="block text-xs font-bold text-slate-200">الألوان الأساسية للهوية:</label>
            <div class="grid grid-cols-2 gap-3">
              <div class="bg-dark-800 p-2.5 rounded-xl border border-slate-700 space-y-1">
                <span class="text-[11px] text-slate-400">اللون الرئيسي (Primary)</span>
                <div class="flex items-center gap-2">
                  <input type="color" v-model="customizerTheme.primaryColor" class="w-7 h-7 rounded border-0 bg-transparent cursor-pointer">
                  <input type="text" v-model="customizerTheme.primaryColor" class="w-full bg-dark-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono">
                </div>
              </div>
              <div class="bg-dark-800 p-2.5 rounded-xl border border-slate-700 space-y-1">
                <span class="text-[11px] text-slate-400">اللون الثانوي (Secondary)</span>
                <div class="flex items-center gap-2">
                  <input type="color" v-model="customizerTheme.secondaryColor" class="w-7 h-7 rounded border-0 bg-transparent cursor-pointer">
                  <input type="text" v-model="customizerTheme.secondaryColor" class="w-full bg-dark-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono">
                </div>
              </div>
            </div>

            <!-- Ready Palette Presets -->
            <div class="flex items-center gap-2 text-[11px] text-slate-400 pt-1">
              <span>قوالب جاهزة:</span>
              <button @click="setPresetPalette('#3b82f6', '#10b981')" class="px-2 py-0.5 rounded bg-blue-600/30 text-blue-300 border border-blue-500/40 text-[10px]">نيترو أزرق</button>
              <button @click="setPresetPalette('#8b5cf6', '#ec4899')" class="px-2 py-0.5 rounded bg-purple-600/30 text-purple-300 border border-purple-500/40 text-[10px]">ألعاب بنفسجي</button>
              <button @click="setPresetPalette('#f59e0b', '#3b82f6')" class="px-2 py-0.5 rounded bg-amber-600/30 text-amber-300 border border-amber-500/40 text-[10px]">نجوم ذهبي</button>
              <button @click="setPresetPalette('#10b981', '#06b6d4')" class="px-2 py-0.5 rounded bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 text-[10px]">تفاعل زمردي</button>
            </div>
          </div>

          <!-- Typography -->
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1">
              <label class="block text-xs font-bold text-slate-200">نوع الخط العربي:</label>
              <select v-model="customizerTheme.fontFamily" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                <option value="Tajawal">تجوال (Tajawal)</option>
                <option value="Cairo">كايرو (Cairo)</option>
                <option value="Almarai">المراعي (Almarai)</option>
              </select>
            </div>
            <div class="space-y-1">
              <label class="block text-xs font-bold text-slate-200">نمط البطاقات:</label>
              <select v-model="customizerTheme.cardStyle" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                <option value="modern">حديث (Modern)</option>
                <option value="glassmorphism">زجاجي (Glassmorphism)</option>
                <option value="minimal">بسيط (Minimal)</option>
              </select>
            </div>
          </div>

          <!-- Version History & Rollback -->
          <div v-if="themeHistoryList.length" class="space-y-1.5 border-t border-slate-700/60 pt-3">
            <label class="block text-xs font-bold text-slate-300">سجل النسخ السابقة (Rollback):</label>
            <div class="flex items-center gap-2">
              <select v-model="selectedRollbackVersion" class="flex-1 bg-dark-800 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white">
                <option v-for="h in themeHistoryList" :key="h.version" :value="h.version">
                  النسخة #{{ h.version }} ({{ h.created || new Date(h.publishedAt).toLocaleDateString('ar-SA') }})
                </option>
              </select>
              <button @click="rollbackToVersion" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-xs font-bold transition">
                استعادة 🔄
              </button>
            </div>
          </div>

          <!-- Save Button -->
          <button @click="saveCustomizerTheme" :disabled="savingTheme" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs py-3 rounded-xl transition shadow">
            <span v-if="savingTheme">جاري الحفظ والنشر... ⏳</span>
            <span v-else>حفظ ونشر التعديلات على المتجر 🚀</span>
          </button>
        </div>
      </div>

      <!-- D. MASTER CATALOG IMPORT MODAL -->
      <div v-if="showMasterModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-lg rounded-3xl border border-slate-700/80 p-5 space-y-4 my-auto max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <h3 class="font-black text-sm text-white flex items-center gap-2">
              <span>📥</span> استيراد المنتجات من الكتالوج العام
            </h3>
            <button @click="showMasterModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Margin selector -->
          <div class="bg-dark-800 p-3 rounded-xl border border-slate-700 space-y-2">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-300 font-bold">نسبة هامش الربح المضافة:</span>
              <span class="text-emerald-400 font-mono font-black">+{{ importMarginPercent }}%</span>
            </div>
            <input type="range" min="5" max="50" step="5" v-model="importMarginPercent" class="w-full accent-emerald-500">
            <div class="text-[10px] text-slate-400">يتم احتساب سعر بيع المنتجات تلقائياً بناءً على سعر التكلفة مضافاً إليه نسبة الربح.</div>
          </div>

          <!-- Select All & List -->
          <div class="space-y-2">
            <div class="flex items-center justify-between text-xs text-slate-400">
              <span>اختر المنتجات المراد استيرادها:</span>
              <button @click="toggleSelectAllMaster" class="text-emerald-400 font-bold hover:underline">
                {{ selectedMasterIds.length === masterCatalogItems.length ? 'إلغاء التحديد' : 'تحديد الكل' }}
              </button>
            </div>

            <div class="space-y-1.5 max-h-60 overflow-y-auto pr-1">
              <label v-for="item in masterCatalogItems" :key="item.id" class="flex items-center justify-between p-2.5 rounded-xl bg-dark-800 hover:bg-dark-750 border border-slate-700 cursor-pointer">
                <div class="flex items-center gap-2.5">
                  <input type="checkbox" :value="item.id" v-model="selectedMasterIds" class="accent-emerald-500 rounded">
                  <div>
                    <div class="font-bold text-xs text-white">{{ item.name_ar || item.name }}</div>
                    <div class="text-[10px] text-slate-400">التكلفة: ${{ item.price_options?.[0]?.costPrice || 0 }} | مقترح: ${{ ((item.price_options?.[0]?.costPrice || 0) * (1 + importMarginPercent/100)).toFixed(2) }}</div>
                  </div>
                </div>
                <span class="text-[10px] bg-slate-700 text-slate-300 px-2 py-0.5 rounded">{{ item.template_type }}</span>
              </label>
            </div>
          </div>

          <!-- Submit Button -->
          <button @click="submitImportMaster" :disabled="!selectedMasterIds.length || importingMaster" class="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-black text-xs py-3 rounded-xl transition shadow">
            <span v-if="importingMaster">جاري الاستيراد... ⏳</span>
            <span v-else>استيراد {{ selectedMasterIds.length }} منتج محدد إلى متجري ✨</span>
          </button>
        </div>
      </div>

      <!-- E. ADD / EDIT PRODUCT MODAL -->
      <div v-if="showProductModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-lg rounded-3xl border border-slate-700/80 p-5 space-y-4 my-auto max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <h3 class="font-black text-sm text-white flex items-center gap-2">
              <span>➕</span> إضافة / تعديل منتج بالمتجر
            </h3>
            <button @click="showProductModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <div class="space-y-3">
            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">اسم المنتج بالعربية:</label>
              <input type="text" v-model="editingProduct.nameAr" placeholder="مثال: شحن بطاقة نتفليكس 100$" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">اسم المنتج بالإنجليزية:</label>
              <input type="text" v-model="editingProduct.name" placeholder="Netflix Gift Card $100" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">الفئة (Category):</label>
                <select v-model="editingProduct.category" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                  <option value="gaming">ألعاب (Gaming)</option>
                  <option value="subscriptions">اشتراكات (Subscriptions)</option>
                  <option value="telegram">تيليجرام (Telegram)</option>
                  <option value="numbers">أرقام تفعيل (Numbers)</option>
                  <option value="smm">تفاعل ودعم (SMM)</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">نوع القالب:</label>
                <select v-model="editingProduct.templateType" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                  <option value="manual_subs">اشتراكات وشحن ألعاب</option>
                  <option value="stars_premium_gifts">نجوم وبريميوم وهدايا</option>
                  <option value="virtual_numbers">أرقام تفعيل</option>
                  <option value="smm_boost">زيادة تفاعل ودعم</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">سعر التكلفة ($):</label>
                <input type="number" step="0.01" v-model.number="editingProduct.costPrice" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">سعر البيع للعميل ($):</label>
                <input type="number" step="0.01" v-model.number="editingProduct.userPrice" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
              </div>
            </div>

            <!-- Floor Price Security Alert -->
            <div v-if="editingProduct.userPrice < editingProduct.costPrice" class="p-2.5 rounded-xl bg-rose-950/70 border border-rose-500/50 text-[11px] text-rose-300">
              ⚠️ تنبيه أمني: سعر البيع لا يمكن أن يكون أقل من سعر التكلفة لحماية أرباحك.
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">رابط صورة المنتج (URL):</label>
              <input type="text" v-model="editingProduct.imageUrl" placeholder="https://..." class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">وصف المنتج:</label>
              <textarea v-model="editingProduct.description" rows="2" placeholder="أدخل تفاصيل ومميزات المنتج..." class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"></textarea>
            </div>
          </div>

          <button @click="saveSellerProduct" :disabled="savingProduct || editingProduct.userPrice < editingProduct.costPrice" class="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-black text-xs py-3 rounded-xl transition shadow">
            <span v-if="savingProduct">جاري الحفظ... ⏳</span>
            <span v-else>حفظ وإضافة المنتج للمتجر ✅</span>
          </button>
        </div>
      </div>

      <!-- F. EXCEL / CSV BULK IMPORT MODAL -->
      <div v-if="showBulkModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-lg rounded-3xl border border-slate-700/80 p-5 space-y-4 my-auto max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <h3 class="font-black text-sm text-white flex items-center gap-2">
              <span>📑</span> استيراد منتجات سريعة من ملف إكسل / CSV
            </h3>
            <button @click="showBulkModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <div class="space-y-3">
            <p class="text-[11px] text-slate-300 leading-relaxed">
              يمكنك نسخ الصفوف مباشرة من ملف Excel أو Google Sheets ولصقها هنا، أو رفع ملف <code>.csv</code> لإضافة المنتجات دفعة واحدة.
            </p>

            <div class="flex items-center gap-2">
              <label class="cursor-pointer bg-dark-800 hover:bg-dark-750 border border-slate-700 px-3 py-2 rounded-xl text-xs font-bold text-white flex items-center gap-1.5 transition">
                <span>📁 رفع ملف CSV</span>
                <input type="file" accept=".csv,.txt,.tsv" @change="handleBulkFileUpload" class="hidden">
              </label>
              <span class="text-[10px] text-slate-400">أو الصق الجدول أدناه مباشرة:</span>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">بيانات الجدول (الاسم، القسم، التكلفة، البيع، الصورة):</label>
              <textarea v-model="bulkCsvText" rows="6" placeholder="اسم المنتج,القسم,سعر التكلفة,سعر البيع,رابط الصورة,الوصف&#10;شحن ببجي 60 شدة,gaming,0.85,1.20,https://...,شحن فوري بالمعرف&#10;اشتراك نتفلكس شهر,subscriptions,3.0,4.50,,حساب رسمي" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white leading-relaxed"></textarea>
            </div>

            <!-- Preview parsed items -->
            <div v-if="parsedBulkItems.length" class="space-y-1.5">
              <div class="flex items-center justify-between text-xs">
                <span class="text-slate-300 font-bold">معاينة المنتجات المستخرجة ({{ parsedBulkItems.length }}):</span>
                <span class="text-emerald-400 font-bold">جاهز للاستيراد ✅</span>
              </div>
              <div class="max-h-36 overflow-y-auto space-y-1 border border-slate-800 rounded-xl p-2 bg-dark-900/60">
                <div v-for="(it, i) in parsedBulkItems" :key="i" class="flex items-center justify-between text-[11px] border-b border-slate-800/60 pb-1">
                  <span class="text-white font-bold">{{ it.name }}</span>
                  <span class="text-slate-400 font-mono">تكلفة: ${{ it.costPrice }} | بيع: ${{ it.userPrice }}</span>
                </div>
              </div>
            </div>
          </div>

          <button @click="submitBulkImport" :disabled="!bulkCsvText.trim() || importingBulk" class="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-black text-xs py-3 rounded-xl transition shadow">
            <span v-if="importingBulk">جاري الاستيراد... ⏳</span>
            <span v-else>استيراد المنتجات إلى متجري فوراً 🚀</span>
          </button>
        </div>
      </div>

    </div>
  </div>

  <!-- ══════════════════════════════════════════════════════════════════════ -->
  <!-- 5. VUE APPLICATION LOGIC                                              -->
  <!-- ══════════════════════════════════════════════════════════════════════ -->
  <script>
    const { createApp, ref, computed, onMounted } = Vue;

    createApp({
      setup() {
        const loading = ref(true);
        const currentTab = ref('store');
        const role = ref('buyer');
        const store = ref({});
        const user = ref({ balance: 0 });
        const categories = ref([]);
        const products = ref([]);
        const myOrders = ref([]);
        const sellerStats = ref({});
        const adminOrders = ref([]);
        const adminOverview = ref({});
        const themeSettings = ref({});

        const selectedCategory = ref('all');
        const searchQuery = ref('');
        const recentSearches = ref(['ببجي', 'نتفلكس', 'تيليجرام', 'أرقام', 'انستغرام']);
        const activeBannerIndex = ref(0);

        // Modals & checkout state
        const activeProduct = ref(null);
        const selectedPriceOption = ref(null);
        const userFormInputs = ref({});
        const smmQuantity = ref(1000);
        const smmUrl = ref('');
        const termsAgreed = ref(false);
        const isSubmitting = ref(false);
        const showDepositModal = ref(false);
        const showThemeCustomizer = ref(false);

        // Seller Settings, Analytics Chart & Bulk Import state
        const chartMetric = ref('orders');
        const hoveredPoint = ref(null);
        const showBulkModal = ref(false);
        const bulkCsvText = ref('');
        const importingBulk = ref(false);

        const sellerProducts = ref([]);
        const masterCatalogItems = ref([]);
        const showMasterModal = ref(false);
        const showProductModal = ref(false);
        const savingSettings = ref(false);
        const sellerSettingsForm = ref({
          support_url: '',
          terms_text: '',
          policy_text: '',
          order_channel: ''
        });

        const editingProduct = ref({
          name: '',
          nameAr: '',
          category: 'subscriptions',
          templateType: 'manual_subs',
          costPrice: 1.0,
          userPrice: 1.5,
          imageUrl: '',
          description: ''
        });

        const customizerTheme = ref({
          primaryColor: '#3b82f6',
          secondaryColor: '#10b981',
          fontFamily: 'Tajawal',
          cardStyle: 'modern'
        });
        const themeHistoryList = ref([]);
        const selectedRollbackVersion = ref(null);
        const aiLoading = ref(false);
        const savingTheme = ref(false);
        const importingMaster = ref(false);
        const savingProduct = ref(false);
        const selectedMasterIds = ref([]);
        const importMarginPercent = ref(15);

        // Telegram WebApp Instance
        const tg = window.Telegram?.WebApp;

        // Initialize App
        const initApp = async () => {
          try {
            if (tg) {
              tg.ready();
              tg.expand();
            }

            const urlParams = new URLSearchParams(window.location.search);
            const pathParts = window.location.pathname.split('/').filter(Boolean);
            let storeId = urlParams.get('store_id') || urlParams.get('start_param') || '';
            if (!storeId && pathParts.length > 1 && (pathParts[0] === 'store' || pathParts[0] === 'app')) {
              storeId = pathParts[1];
            }
            if (!storeId) {
              storeId = 'default';
            }

            // 1. Fetch store info
            const storeRes = await fetch(`/api/miniapp/store-info?store_id=${storeId}`);
            const storeJson = await storeRes.json();
            if (storeJson.success && storeJson.data) {
              store.value = storeJson.data;
              themeSettings.value = storeJson.data.themeSettings || {};
              sellerSettingsForm.value.support_url = storeJson.data.supportUrl || '';
              sellerSettingsForm.value.terms_text = storeJson.data.termsText || '';
              sellerSettingsForm.value.policy_text = storeJson.data.policyText || '';
              sellerSettingsForm.value.order_channel = storeJson.data.orderChannel || storeJson.data.order_channel || '';
            }

            // 2. Authenticate user via Telegram initData
            const initData = tg?.initData || '';
            const authRes = await fetch('/api/miniapp/auth', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ initData, storeId })
            });
            const authJson = await authRes.json();
            if (authJson.success && authJson.data) {
              user.value = authJson.data.user || {};
              role.value = authJson.data.role || 'buyer';
            }

            // Tab routing from URL or pathname
            const tabParam = urlParams.get('tab');
            if (window.location.pathname.includes('/admin_app') && role.value === 'admin') {
              currentTab.value = 'admin';
            } else if (tabParam && ['store', 'orders', 'account', 'seller', 'admin'].includes(tabParam)) {
              if (tabParam === 'admin' && role.value !== 'admin') {
                currentTab.value = 'store';
              } else if (tabParam === 'seller' && role.value !== 'seller' && role.value !== 'admin') {
                currentTab.value = 'store';
              } else {
                currentTab.value = tabParam;
              }
            }

            // 3. Load catalog
            const catRes = await fetch(`/api/miniapp/catalog?store_id=${storeId}`);
            const catJson = await catRes.json();
            if (catJson.success && catJson.data) {
              categories.value = catJson.data.categories || [];
              products.value = catJson.data.products || [];

              const catParam = urlParams.get('cat') || urlParams.get('category');
              if (catParam) selectedCategory.value = catParam;
            }

            // 4. Load initial orders & stats
            await loadOrders();
            if (role.value === 'seller' || role.value === 'admin') {
              await loadSellerSettings();
              await loadSellerStats();
              await loadSellerProducts();
              await loadThemeVersions();
            }
            if (role.value === 'admin') {
              await loadAdminOverview();
              await loadAdminOrders();
            }

          } catch (err) {
            console.error('Init error:', err);
          } finally {
            loading.value = false;
          }
        };

        const loadOrders = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/orders/my', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.success && json.data) myOrders.value = json.data;
          } catch {}
        };

        const loadSellerStats = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/stats', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.success && json.data) sellerStats.value = json.data;
          } catch {}
        };

        const loadAdminOverview = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/overview', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.success && json.data) adminOverview.value = json.data;
          } catch {}
        };

        const loadAdminOrders = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/orders', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.success && json.data) adminOrders.value = json.data;
          } catch {}
        };

        // Fuzzy search & normalization ignoring Tashkeel & Hamza
        const normalizeArabic = (text) => {
          if (!text) return '';
          return text
            .replace(/[\u064B-\u065F]/g, '')
            .replace(/[أإآ]/g, 'ا')
            .replace(/ة/g, 'ه')
            .replace(/ى/g, 'ي')
            .toLowerCase();
        };

        const filteredProducts = computed(() => {
          return products.value.filter(p => {
            if (selectedCategory.value !== 'all' && p.category !== selectedCategory.value && p.category_id !== selectedCategory.value) {
              return false;
            }
            if (searchQuery.value) {
              const queryNorm = normalizeArabic(searchQuery.value);
              const nameNorm = normalizeArabic(p.nameAr || p.name);
              const descNorm = normalizeArabic(p.description || '');
              return nameNorm.includes(queryNorm) || descNorm.includes(queryNorm);
            }
            return true;
          });
        });

        const getEffectivePrice = (prod) => {
          const opt = prod.priceOptions?.[0];
          const base = opt ? Number(opt.userPrice || opt.price || 1) : Number(prod.price_usd || 1);
          if (prod.discountPercent > 0) {
            return (base * (100 - prod.discountPercent) / 100).toFixed(2);
          }
          return base.toFixed(2);
        };

        const getOriginalPrice = (prod) => {
          const opt = prod.priceOptions?.[0];
          return (opt ? Number(opt.userPrice || opt.price || 1) : Number(prod.price_usd || 1)).toFixed(2);
        };

        const openProductModal = (prod) => {
          activeProduct.value = prod;
          selectedPriceOption.value = prod.priceOptions?.[0] || null;
          userFormInputs.value = {};
          termsAgreed.value = false;
        };

        const getCalculatedTotal = () => {
          if (!activeProduct.value) return '0.00';
          if (activeProduct.value.templateType === 'smm_boost') {
            const base = selectedPriceOption.value?.userPrice || activeProduct.value.price_usd || 1.0;
            return ((base * smmQuantity.value) / 1000).toFixed(2);
          }
          const base = selectedPriceOption.value?.userPrice || activeProduct.value.price_usd || 1.0;
          if (activeProduct.value.discountPercent > 0) {
            return (base * (100 - activeProduct.value.discountPercent) / 100).toFixed(2);
          }
          return Number(base).toFixed(2);
        };

        const submitOrder = async () => {
          if (!termsAgreed.value) return;
          isSubmitting.value = true;
          try {
            const initData = tg?.initData || '';
            const payload = {
              productId: activeProduct.value.id,
              priceOptionId: selectedPriceOption.value?.id,
              quantity: activeProduct.value.templateType === 'smm_boost' ? smmQuantity.value : 1,
              targetUrl: smmUrl.value,
              userInputs: userFormInputs.value,
              idempotencyKey: `IDEMP-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
            };

            const res = await fetch('/api/miniapp/order/create', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify(payload)
            });

            const json = await res.json();
            if (json.success || json.ok) {
              if (json.data && json.data.remainingBalance !== undefined) {
                user.value.balance = Number(json.data.remainingBalance);
              } else if (json.new_balance_usd !== undefined) {
                user.value.balance = Number(json.new_balance_usd);
              }
              activeProduct.value = null;
              currentTab.value = 'orders';
              await loadOrders();
              alert(json.message || 'تم تأكيد طلبك بنجاح!');
            } else {
              alert(json.error || json.message || 'فشل إتمام الطلب');
            }
          } catch (err) {
            alert('حدث خطأ أثناء معالجة الطلب');
          } finally {
            isSubmitting.value = false;
          }
        };

        const getStatusLabelAr = (status) => {
          const map = {
            pending: 'بانتظار التنفيذ ⏳',
            queued: 'بانتظار التنفيذ ⏳',
            processing: 'قيد التنفيذ ⚙️',
            completed: 'مكتمل بنجاح ✅',
            refunded: 'مُسترجع للرصيد 🔄',
            rejected: 'مرفوض ❌',
            canceled: 'ملغي ❌'
          };
          return map[status] || status;
        };

        const getStatusBadgeClass = (status) => {
          if (status === 'completed') return 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40';
          if (status === 'processing') return 'bg-blue-950/60 text-blue-300 border-blue-500/40';
          if (status === 'pending' || status === 'queued') return 'bg-amber-950/60 text-amber-300 border-amber-500/40';
          if (status === 'refunded') return 'bg-purple-950/60 text-purple-300 border-purple-500/40';
          return 'bg-rose-950/60 text-rose-300 border-rose-500/40';
        };

        const getReferralLink = () => {
          return `https://t.me/${store.value?.botUsername || 'bot'}?start=sl_${user.value.telegramId || 1}`;
        };

        const copyToClipboard = (text) => {
          if (!text) return;
          navigator.clipboard.writeText(text);
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
          alert('تم النسخ إلى الحافظة بنجاح! 📋');
        };

        const payWithStars = () => {
          alert('لشحن نجوم تيليجرام Telegram Stars، أرسل أمر /deposit داخل محادثة البوت الرئيسية وسيتم تزويدك بالفاتورة فوراً.');
        };

        const payWithExternalGateway = () => {
          const link = store.value?.supportUrl || `https://t.me/${store.value?.botUsername || 'bot'}`;
          if (tg?.openLink) {
            tg.openLink(link);
          } else {
            window.open(link, '_blank');
          }
        };

        const handleAdminOrderAction = async (orderRef, action) => {
          const note = prompt(action === 'deliver' ? 'أدخل بيانات التسليم والكود للعميل:' : 'أدخل سبب الإجراء:');
          if (note === null) return;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/orders/action', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({
                orderRef,
                action,
                deliveryData: action === 'deliver' ? note : undefined,
                rejectionReason: action !== 'deliver' ? note : undefined
              })
            });
            const json = await res.json();
            alert(json.message || 'تم الإجراء بنجاح');
            await loadAdminOrders();
            await loadAdminOverview();
          } catch (e) {
            alert('حدث خطأ أثناء تنفيذ الإجراء');
          }
        };

        const loadSellerProducts = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/products', {
              headers: { 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.success && json.data) sellerProducts.value = json.data;
          } catch {}
        };

        const loadThemeVersions = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/theme/versions', {
              headers: { 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.success && json.data) {
              themeHistoryList.value = json.data;
              if (themeHistoryList.value.length) {
                selectedRollbackVersion.value = themeHistoryList.value[0].version;
              }
            }
          } catch {}
        };

        const saveSellerSettingsForm = async () => {
          savingSettings.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/settings', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify(sellerSettingsForm.value)
            });
            const json = await res.json();
            if (json.success || json.ok) {
              store.value.supportUrl = sellerSettingsForm.value.support_url;
              store.value.termsText = sellerSettingsForm.value.terms_text;
              store.value.policyText = sellerSettingsForm.value.policy_text;
              alert(json.message || 'تم حفظ الإعدادات والشروط بنجاح ✅');
            } else {
              alert(json.error || 'فشل حفظ الإعدادات');
            }
          } catch {
            alert('حدث خطأ أثناء حفظ الإعدادات');
          } finally {
            savingSettings.value = false;
          }
        };

        const openCustomizer = () => {
          if (store.value?.themeSettings) {
            customizerTheme.value = { ...store.value.themeSettings };
          }
          showThemeCustomizer.value = true;
        };

        const setPresetPalette = (p, s) => {
          customizerTheme.value.primaryColor = p;
          customizerTheme.value.secondaryColor = s;
        };

        const applyAiSuggestions = async () => {
          aiLoading.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/ai-suggest', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify({ category: store.value?.templateType === 'smm' ? 'smm' : (store.value?.templateType === 'sms' ? 'numbers' : 'gaming') })
            });
            const json = await res.json();
            if (json.success && json.data) {
              if (json.data.palette) {
                customizerTheme.value.primaryColor = json.data.palette.primaryColor;
                customizerTheme.value.secondaryColor = json.data.palette.secondaryColor;
              }
              if (json.data.cardStyle) customizerTheme.value.cardStyle = json.data.cardStyle;
              if (json.data.fontFamily) customizerTheme.value.fontFamily = json.data.fontFamily;
              alert('✨ تم تطبيق اقتراح الذكاء الاصطناعي بنجاح!');
            } else {
              alert(json.error || 'تعذر جلب اقتراح الذكاء الاصطناعي');
            }
          } catch {
            alert('حدث خطأ أثناء التواصل مع المساعد الذكي');
          } finally {
            aiLoading.value = false;
          }
        };

        const saveCustomizerTheme = async () => {
          savingTheme.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/theme', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify({ themeSettings: customizerTheme.value })
            });
            const json = await res.json();
            if (json.success || json.ok) {
              alert(json.message || 'تم حفظ ونشر المظهر بنجاح!');
              showThemeCustomizer.value = false;
              window.location.reload();
            } else {
              alert(json.error || 'فشل حفظ المظهر');
            }
          } catch {
            alert('حدث خطأ أثناء حفظ المظهر');
          } finally {
            savingTheme.value = false;
          }
        };

        const rollbackToVersion = async () => {
          if (!selectedRollbackVersion.value) return;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/theme/rollback', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify({ version: selectedRollbackVersion.value })
            });
            const json = await res.json();
            if (json.success || json.ok) {
              alert(json.message || 'تمت استعادة النسخة بنجاح!');
              window.location.reload();
            } else {
              alert(json.error || 'فشل استعادة النسخة');
            }
          } catch {
            alert('حدث خطأ أثناء الاستعادة');
          }
        };

        const openMasterCatalog = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/master-catalog', {
              headers: { 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.success && json.data) {
              masterCatalogItems.value = json.data;
              selectedMasterIds.value = json.data.map(i => i.id);
              showMasterModal.value = true;
            }
          } catch {
            alert('حدث خطأ أثناء جلب الكتالوج العام');
          }
        };

        const toggleSelectAllMaster = () => {
          if (selectedMasterIds.value.length === masterCatalogItems.value.length) {
            selectedMasterIds.value = [];
          } else {
            selectedMasterIds.value = masterCatalogItems.value.map(i => i.id);
          }
        };

        const submitImportMaster = async () => {
          importingMaster.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/import-master', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify({ masterIds: selectedMasterIds.value, marginPercent: importMarginPercent.value })
            });
            const json = await res.json();
            if (json.success || json.ok) {
              alert(json.message || 'تم استيراد المنتجات بنجاح!');
              showMasterModal.value = false;
              await loadSellerProducts();
            } else {
              alert(json.error || 'فشل الاستيراد');
            }
          } catch {
            alert('حدث خطأ أثناء الاستيراد');
          } finally {
            importingMaster.value = false;
          }
        };

        const openNewProductModal = () => {
          editingProduct.value = {
            name: '',
            nameAr: '',
            category: 'subscriptions',
            templateType: store.value?.templateType || 'manual_subs',
            costPrice: 1.0,
            userPrice: 1.5,
            imageUrl: '',
            description: ''
          };
          showProductModal.value = true;
        };

        const saveSellerProduct = async () => {
          if (!editingProduct.value.nameAr && !editingProduct.value.name) {
            alert('الرجاء كتابة اسم المنتج');
            return;
          }
          if (editingProduct.value.userPrice < editingProduct.value.costPrice) {
            alert('سعر البيع لا يمكن أن يكون أقل من التكلفة!');
            return;
          }
          savingProduct.value = true;
          try {
            const initData = tg?.initData || '';
            const payload = {
              name: editingProduct.value.name || editingProduct.value.nameAr,
              nameAr: editingProduct.value.nameAr || editingProduct.value.name,
              category: editingProduct.value.category,
              templateType: editingProduct.value.templateType,
              description: editingProduct.value.description,
              imageUrl: editingProduct.value.imageUrl,
              costPrice: Number(editingProduct.value.costPrice),
              userPrice: Number(editingProduct.value.userPrice),
              priceOptions: [{
                id: 'opt_1',
                label: editingProduct.value.nameAr || editingProduct.value.name,
                costPrice: Number(editingProduct.value.costPrice),
                userPrice: Number(editingProduct.value.userPrice)
              }]
            };
            const res = await fetch('/api/miniapp/seller/products/upsert', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (json.success || json.ok) {
              alert(json.message || 'تم حفظ المنتج بنجاح!');
              showProductModal.value = false;
              await loadSellerProducts();
            } else {
              alert(json.error || 'فشل حفظ المنتج');
            }
          } catch {
            alert('حدث خطأ أثناء حفظ المنتج');
          } finally {
            savingProduct.value = false;
          }
        };

        const toggleProductActive = async (id) => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/products/toggle', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify({ id })
            });
            const json = await res.json();
            if (json.success || json.ok) await loadSellerProducts();
          } catch {}
        };

        const deleteSellerProduct = async (id) => {
          if (!confirm('هل أنت متأكد من حذف هذا المنتج نهائياً من متجرك؟')) return;
          try {
            const initData = tg?.initData || '';
            const res = await fetch(`/api/miniapp/seller/products/${id}`, {
              method: 'DELETE',
              headers: { 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.success || json.ok) await loadSellerProducts();
          } catch {}
        };

        const loadSellerSettings = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/settings', {
              headers: { 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.success && json.data) {
              sellerSettingsForm.value.support_url = json.data.support_url || '';
              sellerSettingsForm.value.terms_text = json.data.terms_text || '';
              sellerSettingsForm.value.policy_text = json.data.policy_text || '';
              sellerSettingsForm.value.order_channel = json.data.order_channel || '';
            }
          } catch {}
        };

        // Chart Methods
        const getChartPointsList = () => {
          const list = sellerStats.value?.recentChart || [];
          if (!list.length) return [];
          const values = list.map(d => {
            if (chartMetric.value === 'profit') return Number(d.profit || 0);
            if (chartMetric.value === 'canceled') return Number(d.canceled || 0);
            return Number(d.orders || 0);
          });
          const maxVal = Math.max(...values, 4);
          const stepX = 300 / Math.max(list.length - 1, 1);
          return list.map((d, i) => {
            const val = values[i];
            const x = 10 + i * stepX;
            const y = 80 - (val / maxVal) * 60;
            return { x, y, val, day_name: d.day_name, date: d.date, orders: d.orders, profit: d.profit || 0, canceled: d.canceled || 0 };
          });
        };

        const getChartLinePoints = () => {
          const pts = getChartPointsList();
          if (!pts.length) return '10,80 310,80';
          return pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
        };

        const getChartAreaPoints = () => {
          const pts = getChartPointsList();
          if (!pts.length) return '10,80 310,80 310,95 10,95';
          const lineStr = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
          const lastX = pts[pts.length - 1].x.toFixed(1);
          const firstX = pts[0].x.toFixed(1);
          return `${lineStr} ${lastX},95 ${firstX},95`;
        };

        const getSuccessRate = () => {
          const total = sellerStats.value?.totalOrders || 0;
          const canceled = sellerStats.value?.canceledOrders || 0;
          if (!total) return 100;
          return Math.max(0, Math.round(((total - canceled) / total) * 100));
        };

        const getCancellationRate = () => {
          const total = sellerStats.value?.totalOrders || 0;
          const canceled = sellerStats.value?.canceledOrders || 0;
          if (!total) return 0;
          return Math.min(100, Math.round((canceled / total) * 100));
        };

        // Bulk CSV Import Methods
        const openBulkModal = () => {
          showBulkModal.value = true;
        };

        const parsedBulkItems = computed(() => {
          if (!bulkCsvText.value.trim()) return [];
          const lines = bulkCsvText.value.trim().split('\n');
          const firstLine = lines[0];
          const delim = firstLine.includes('\t') ? '\t' : (firstLine.includes(';') ? ';' : ',');
          const items = [];
          for (let i = 0; i < lines.length; i++) {
            const row = lines[i].split(delim).map(c => c.trim().replace(/^["']|["']$/g, ''));
            if (!row[0] || (i === 0 && (row[0].toLowerCase() === 'name' || row[0] === 'اسم' || row[0] === 'الاسم'))) continue;
            const name = row[0];
            const cat = row[1] || 'subscriptions';
            const cost = parseFloat((row[2] || '1.0').replace('$', '')) || 1.0;
            const price = parseFloat((row[3] || (cost * 1.2).toString()).replace('$', '')) || (cost * 1.2);
            const img = row[4] || '';
            const desc = row[5] || '';
            items.push({ name, category: cat, costPrice: cost, userPrice: Math.max(cost, price), imageUrl: img, description: desc });
          }
          return items;
        });

        const handleBulkFileUpload = (evt) => {
          const file = evt.target.files?.[0];
          if (!file) return;
          const reader = new FileReader();
          reader.onload = (e) => {
            bulkCsvText.value = e.target.result || '';
          };
          reader.readAsText(file);
        };

        const submitBulkImport = async () => {
          if (!bulkCsvText.value.trim()) return;
          importingBulk.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/products/bulk', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({ csv_text: bulkCsvText.value })
            });
            const json = await res.json();
            if (json.success || json.ok) {
              alert(json.message || `تم استيراد ${json.imported_count || 0} منتج بنجاح!`);
              showBulkModal.value = false;
              bulkCsvText.value = '';
              await loadSellerProducts();
            } else {
              alert(json.error || 'فشل الاستيراد');
            }
          } catch {
            alert('حدث خطأ أثناء معالجة الملف');
          } finally {
            importingBulk.value = false;
          }
        };

        onMounted(() => {
          initApp();
        });

        return {
          loading,
          currentTab,
          role,
          store,
          user,
          categories,
          products,
          myOrders,
          sellerStats,
          adminOrders,
          adminOverview,
          themeSettings,
          selectedCategory,
          searchQuery,
          recentSearches,
          activeBannerIndex,
          filteredProducts,
          activeProduct,
          selectedPriceOption,
          userFormInputs,
          smmQuantity,
          smmUrl,
          termsAgreed,
          isSubmitting,
          showDepositModal,
          showThemeCustomizer,
          getEffectivePrice,
          getOriginalPrice,
          openProductModal,
          getCalculatedTotal,
          submitOrder,
          getStatusLabelAr,
          getStatusBadgeClass,
          getReferralLink,
          copyToClipboard,
          payWithStars,
          payWithExternalGateway,
          handleAdminOrderAction,
          sellerProducts,
          masterCatalogItems,
          showMasterModal,
          showProductModal,
          editingProduct,
          customizerTheme,
          themeHistoryList,
          selectedRollbackVersion,
          aiLoading,
          savingTheme,
          importingMaster,
          savingProduct,
          selectedMasterIds,
          importMarginPercent,
          loadSellerProducts,
          openCustomizer,
          setPresetPalette,
          applyAiSuggestions,
          saveCustomizerTheme,
          rollbackToVersion,
          openMasterCatalog,
          toggleSelectAllMaster,
          submitImportMaster,
          openNewProductModal,
          saveSellerProduct,
          toggleProductActive,
          deleteSellerProduct,
          sellerSettingsForm,
          savingSettings,
          saveSellerSettingsForm,
          loadSellerSettings,
          chartMetric,
          hoveredPoint,
          getChartPointsList,
          getChartLinePoints,
          getChartAreaPoints,
          getSuccessRate,
          getCancellationRate,
          showBulkModal,
          bulkCsvText,
          importingBulk,
          parsedBulkItems,
          openBulkModal,
          handleBulkFileUpload,
          submitBulkImport,
          initApp
        };
      }
    }).mount('#app');
  </script>
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

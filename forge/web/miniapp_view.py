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
              {{ t('online') }}
            </span>
          </div>
        </div>

        <div class="flex items-center gap-1.5 sm:gap-2">
          <!-- Language Selector (5 Languages) -->
          <div class="relative">
            <select v-model="currentLang" class="bg-dark-800/90 border border-slate-700/60 text-[10px] font-bold text-slate-200 rounded-xl px-1.5 py-1.5 focus:outline-none cursor-pointer shadow-inner">
              <option value="ar">🇸🇦 العربية</option>
              <option value="en">🇬🇧 English</option>
              <option value="ru">🇷🇺 Русский</option>
              <option value="fa">🇮🇷 فارسی</option>
              <option value="tr">🇹🇷 Türkçe</option>
            </select>
          </div>

          <!-- Currency Selector (All Currencies) -->
          <div class="relative">
            <select v-model="currentCurrency" class="bg-dark-800/90 border border-slate-700/60 text-[10px] font-bold text-amber-300 rounded-xl px-1.5 py-1.5 focus:outline-none cursor-pointer shadow-inner max-w-[85px]">
              <option v-for="c in currencyOptions" :key="c.code" :value="c.code">
                {{ c.symbol }} {{ c.code }}
              </option>
            </select>
          </div>

          <!-- Shopping Cart Button with Dynamic Badge -->
          <button @click="showCartDrawer = true" class="relative bg-dark-800/90 border border-slate-700/60 rounded-xl p-2 text-slate-200 hover:text-white transition active:scale-95 flex items-center justify-center shadow-inner">
            <span class="text-sm">🛒</span>
            <span v-if="cartTotalCount > 0" class="absolute -top-1.5 -right-1.5 bg-rose-600 text-white text-[10px] font-black w-4 h-4 rounded-full flex items-center justify-center shadow">
              {{ cartTotalCount }}
            </span>
          </button>

          <!-- Balance Pill -->
          <div class="bg-dark-800/90 border border-slate-700/60 rounded-xl px-2.5 py-1.5 flex items-center gap-1.5 shadow-inner">
            <span class="text-xs text-amber-400">💰</span>
            <span class="text-xs font-black tracking-tight text-slate-100">{{ formatPrice(user.balance || 0) }}</span>
          </div>
          <!-- Quick Recharge Button -->
          <button @click="showDepositModal = true" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs px-2.5 py-1.5 rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-1 transition active:scale-95">
            <span>+</span>
            <span>{{ t('recharge') }}</span>
          </button>
        </div>
      </header>

      <!-- ── MAIN CONTENT TABS ───────────────────────────────────────────── -->
      <main class="flex-1 p-4 space-y-4">

        <!-- 🛒 Abandoned Cart Recovery Floating Alert -->
        <div v-if="cartTotalCount > 0 && currentTab === 'store'" @click="showCartDrawer = true" class="cursor-pointer bg-gradient-to-r from-amber-600/30 via-orange-600/20 to-amber-600/30 border border-amber-500/40 rounded-2xl p-3 flex items-center justify-between shadow-lg transition active:scale-98 animate-pulse">
          <div class="flex items-center gap-2.5">
            <span class="text-2xl">🛒</span>
            <div>
              <div class="text-xs font-black text-amber-200">سلتك بانتظارك! ({{ cartTotalCount }} عناصر جاهزة)</div>
              <div class="text-[10px] text-amber-300/80">أكمل سلتك واشترِ الآن واستفد من العروض الحصرية ⚡</div>
            </div>
          </div>
          <button class="bg-amber-500 hover:bg-amber-400 text-slate-900 font-black text-xs px-3 py-1.5 rounded-xl shadow whitespace-nowrap">
            إكمال السلة ←
          </button>
        </div>

        <!-- 🎡 Floating Fortune Wheel Badge (When Enabled by Seller) -->
        <button v-if="store.wheelEnabled" @click="openWheelModal" class="fixed bottom-20 right-4 z-40 bg-gradient-to-r from-purple-600 via-pink-600 to-amber-500 text-white font-black text-xs px-3.5 py-2.5 rounded-full shadow-2xl flex items-center gap-2 border border-white/20 active:scale-95 transition-all hover:scale-105">
          <span class="text-lg animate-spin" style="animation-duration: 8s;">🎡</span>
          <span>عجلة الحظ</span>
          <span class="bg-amber-400 text-slate-900 text-[9px] font-black px-1.5 py-0.5 rounded-full">اربح!</span>
        </button>

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
                      {{ formatPrice(getOriginalPrice(prod)) }}
                    </div>
                    <div class="text-xs font-black text-emerald-400 font-mono">
                      {{ formatPrice(getEffectivePrice(prod)) }}
                    </div>
                  </div>
                  <button @click.stop="addToCart(prod)" class="bg-brand-600/30 text-brand-400 border border-brand-500/30 w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs hover:bg-brand-600 hover:text-white transition active:scale-95 shadow-sm" title="أضف إلى السلة">
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
                <span class="font-black text-emerald-400">{{ formatPrice(order.total_price) }}</span>
              </div>

              <!-- 4-Step Order Progress Tracker -->
              <div class="py-2 border-y border-slate-800/80 my-1">
                <div class="flex items-center justify-between text-[9px] text-slate-400 mb-1 px-1">
                  <span class="text-emerald-400 font-bold">1. استلام 📝</span>
                  <span :class="{'text-emerald-400 font-bold': order.status !== 'queued'}">2. مراجعة ⏳</span>
                  <span :class="{'text-emerald-400 font-bold': order.status === 'processing' || order.status === 'completed'}">3. تجهيز ⚙️</span>
                  <span :class="{'text-emerald-400 font-bold': order.status === 'completed'}">4. تسليم ✅</span>
                </div>
                <div class="w-full bg-dark-900 h-1.5 rounded-full overflow-hidden flex">
                  <div class="h-full bg-emerald-500 transition-all duration-500" :style="{ width: order.status === 'completed' ? '100%' : (order.status === 'processing' ? '70%' : (order.status === 'pending' ? '40%' : '20%')) }"></div>
                </div>
              </div>

              <!-- Gift Order Badge & Modal Trigger -->
              <div v-if="order.details && order.details.is_gift" class="bg-purple-950/40 border border-purple-500/30 rounded-lg p-2 text-xs text-purple-200 flex items-center justify-between">
                <div>
                  <span class="font-bold">🎁 طلب مهداة إلى: </span>{{ order.details.gift_recipient }}
                  <div class="text-[10px] text-purple-300 italic mt-0.5" v-if="order.details.gift_message">"{{ order.details.gift_message }}"</div>
                </div>
                <button @click="openGiftCard(order)" class="text-[10px] bg-purple-700/60 hover:bg-purple-600 px-2.5 py-1 rounded-md text-white font-bold whitespace-nowrap">
                  عرض كرت الهدية 💌
                </button>
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
        <!-- TAB 3: MY ACCOUNT (👤 حسابي) - تصميم أنيق ومرتب بـ 4 أقسام رئيسية   -->
        <!-- ──────────────────────────────────────────────────────────────── -->
        <div v-if="currentTab === 'account'" class="space-y-4">

          <!-- القسم 1: بطاقة الهوية والملف الشخصي VIP Identity Card -->
          <div class="bg-gradient-to-br from-dark-800 via-dark-850 to-dark-800 border border-slate-700/80 rounded-2xl p-4 shadow-lg flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="relative">
                <div class="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 via-indigo-600 to-purple-600 flex items-center justify-center text-xl font-black text-white shadow-lg shadow-brand-600/30 ring-2 ring-white/10">
                  {{ (user.firstName || 'U')[0] }}
                </div>
                <span class="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 border-2 border-dark-850 rounded-full flex items-center justify-center text-[9px] text-white">✓</span>
              </div>
              <div class="space-y-0.5">
                <div class="flex items-center gap-1.5">
                  <h3 class="font-black text-sm text-white">{{ user.firstName || 'عميل المتجر' }}</h3>
                  <span class="text-[10px] text-amber-400">⭐</span>
                </div>
                <div class="text-[11px] text-slate-400 font-mono">@{{ user.username || 'user' }}</div>
                <div class="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                  <span>ID:</span>
                  <span class="bg-dark-900 px-1.5 py-0.5 rounded text-slate-400">{{ user.telegramId || '0' }}</span>
                </div>
              </div>
            </div>

            <span :class="['text-[10px] font-bold px-3 py-1.5 rounded-xl border shadow-sm',
                           role === 'admin' ? 'bg-rose-950/60 text-rose-300 border-rose-500/40' :
                           role === 'seller' ? 'bg-amber-950/60 text-amber-300 border-amber-500/40' :
                           'bg-blue-950/60 text-blue-300 border-blue-500/40']">
              {{ role === 'admin' ? t('role_admin') : (role === 'seller' ? t('role_seller') : t('role_buyer')) }}
            </span>
          </div>

          <!-- القسم 2: مركز المحفظة والرصيد Digital Wallet & Balance Hub -->
          <div class="bg-gradient-to-br from-emerald-950/60 via-dark-850 to-teal-950/50 border border-emerald-500/30 rounded-2xl p-4 shadow-md space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <span class="text-xs text-emerald-300/80 font-medium flex items-center gap-1">
                  <span>💳</span> {{ t('available_balance') }}
                </span>
                <div class="text-3xl font-black text-emerald-400 tracking-tight font-mono mt-0.5">
                  {{ formatPrice(user.balance || 0) }}
                </div>
                <div v-if="currentCurrency !== 'USD'" class="text-[10px] text-slate-400 font-mono mt-0.5">
                  ≈ ${{ (user.balance || 0).toFixed(2) }} USD
                </div>
              </div>
              <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-2xl shadow-inner">
                💰
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2.5 pt-1 border-t border-slate-700/40">
              <button @click="showDepositModal = true" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs py-2.5 px-3 rounded-xl shadow-md shadow-emerald-600/20 flex items-center justify-center gap-1.5 transition active:scale-95">
                <span>➕</span>
                <span>{{ t('wallet_topup') }}</span>
              </button>
              <button @click="scrollToStatement" class="bg-dark-800 hover:bg-dark-750 border border-slate-700 text-slate-200 font-bold text-xs py-2.5 px-3 rounded-xl flex items-center justify-center gap-1.5 transition active:scale-95">
                <span>📜</span>
                <span>{{ t('statement') }}</span>
              </button>
            </div>
          </div>

          <!-- القسم 3: شبكة الخدمات السريعة والمساعدة Quick Services 4-Grid -->
          <div class="grid grid-cols-2 gap-2.5">
            <!-- البطاقة 1: طلباتي السابقة -->
            <button @click="currentTab = 'orders'" class="bg-dark-800/90 hover:bg-dark-750 border border-slate-700/70 p-3.5 rounded-2xl text-right transition active:scale-95 flex flex-col justify-between space-y-2 shadow-sm">
              <div class="flex items-center justify-between w-full">
                <span class="text-2xl">📦</span>
                <span class="text-[10px] bg-brand-500/20 text-brand-300 font-mono font-bold px-2 py-0.5 rounded-full">
                  {{ (userOrders || []).length }}
                </span>
              </div>
              <div>
                <div class="font-black text-xs text-white">{{ t('my_orders') }}</div>
                <div class="text-[10px] text-slate-400 mt-0.5">متابعة الطلبات السابقة</div>
              </div>
            </button>

            <!-- البطاقة 2: الدعم الفني VIP -->
            <a :href="store.supportUrl || ('https://t.me/' + (store.botUsername || 'bot'))" target="_blank" class="bg-dark-800/90 hover:bg-dark-750 border border-slate-700/70 p-3.5 rounded-2xl text-right transition active:scale-95 flex flex-col justify-between space-y-2 shadow-sm">
              <div class="flex items-center justify-between w-full">
                <span class="text-2xl">💬</span>
                <span class="text-[10px] bg-emerald-500/20 text-emerald-400 font-bold px-2 py-0.5 rounded-full">
                  {{ t('support_available') }}
                </span>
              </div>
              <div>
                <div class="font-black text-xs text-white">{{ t('vip_support') }}</div>
                <div class="text-[10px] text-slate-400 mt-0.5">خدمة عملاء فورية 24/7</div>
              </div>
            </a>

            <!-- البطاقة 3: الضمان الذهبي وسياسة الاستخدام -->
            <button @click="showGuaranteeModal = true" class="bg-dark-800/90 hover:bg-dark-750 border border-slate-700/70 p-3.5 rounded-2xl text-right transition active:scale-95 flex flex-col justify-between space-y-2 shadow-sm">
              <div class="flex items-center justify-between w-full">
                <span class="text-2xl">🛡️</span>
                <span class="text-[10px] bg-amber-500/20 text-amber-300 font-bold px-2 py-0.5 rounded-full">
                  ضمان 100%
                </span>
              </div>
              <div>
                <div class="font-black text-xs text-white">{{ t('golden_guarantee') }}</div>
                <div class="text-[10px] text-slate-400 mt-0.5">حماية كاملة واسترجاع</div>
              </div>
            </button>

            <!-- البطاقة 4: عجلة الحظ اليومية -->
            <button @click="openWheelModal" class="bg-dark-800/90 hover:bg-dark-750 border border-slate-700/70 p-3.5 rounded-2xl text-right transition active:scale-95 flex flex-col justify-between space-y-2 shadow-sm">
              <div class="flex items-center justify-between w-full">
                <span class="text-2xl">🎡</span>
                <span class="text-[10px] bg-purple-500/20 text-purple-300 font-bold px-2 py-0.5 rounded-full">
                  {{ store.wheelEnabled ? 'متاح الآن' : 'اربح' }}
                </span>
              </div>
              <div>
                <div class="font-black text-xs text-white">{{ t('lucky_wheel') }}</div>
                <div class="text-[10px] text-slate-400 mt-0.5">جوائز وهدايا فورية</div>
              </div>
            </button>
          </div>

          <!-- القسم 4: برنامج الإحالة وسجل العمليات المالية Referral & Financial Hub -->
          <div class="space-y-3">
            <!-- 4A: صندوق الإحالة والعمولات -->
            <div class="bg-gradient-to-br from-indigo-950/70 via-dark-850 to-purple-950/60 border border-indigo-500/30 rounded-2xl p-4 space-y-3 shadow-md">
              <div class="flex items-center gap-2">
                <span class="text-2xl">🎁</span>
                <div>
                  <h4 class="font-black text-xs text-white">{{ t('referral_program') }}</h4>
                  <p class="text-[10px] text-indigo-200">{{ t('referral_desc') }}</p>
                </div>
              </div>

              <!-- رابط الإحالة مع زر النسخ -->
              <div class="bg-dark-900/90 border border-slate-700/80 rounded-xl p-2.5 flex items-center justify-between gap-2">
                <span class="text-xs font-mono text-slate-300 truncate max-w-[200px]">
                  {{ getReferralLink() }}
                </span>
                <button @click="copyToClipboard(getReferralLink())" class="bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg shadow whitespace-nowrap active:scale-95 transition">
                  {{ t('copy_link') }}
                </button>
              </div>

              <!-- إحصائيات الإحالة -->
              <div class="grid grid-cols-2 gap-2 text-center text-xs">
                <div class="bg-dark-900/70 border border-indigo-500/20 rounded-xl p-2">
                  <div class="text-[10px] text-slate-400">{{ t('invited') }}</div>
                  <div class="font-black text-indigo-300 font-mono">{{ accountData?.invited_count || 0 }}</div>
                </div>
                <div class="bg-dark-900/70 border border-indigo-500/20 rounded-xl p-2">
                  <div class="text-[10px] text-slate-400">{{ t('earned') }}</div>
                  <div class="font-black text-emerald-400 font-mono">{{ formatPrice(accountData?.earned_usd || 0) }}</div>
                </div>
              </div>
            </div>

            <!-- 4B: كشف الحساب وسجل العمليات المالية -->
            <div id="financial-statement-card" class="bg-dark-800/90 border border-slate-700/80 rounded-2xl p-4 space-y-3 shadow-md">
              <div class="flex items-center justify-between border-b border-slate-700/60 pb-2">
                <div class="flex items-center gap-2">
                  <span class="text-lg">💳</span>
                  <h4 class="font-black text-xs text-white">{{ t('financial_statement') }}</h4>
                </div>
                <span class="text-[10px] text-slate-400 font-mono">{{ (userTransactions || []).length }} {{ t('transactions_count') }}</span>
              </div>

              <div v-if="(userTransactions || []).length" class="space-y-2 max-h-56 overflow-y-auto pr-1">
                <div v-for="tx in userTransactions" :key="tx.id" class="bg-dark-900/80 border border-slate-800 p-2.5 rounded-xl flex items-center justify-between text-xs">
                  <div class="flex items-center gap-2">
                    <span class="text-base">{{ tx.direction === 'credit' ? '🟢' : '🔴' }}</span>
                    <div>
                      <div class="font-bold text-white text-[11px]">{{ tx.description || tx.kind }}</div>
                      <div class="text-[9px] text-slate-500 font-mono">{{ tx.created }}</div>
                    </div>
                  </div>
                  <div class="text-left font-mono">
                    <div :class="['font-black text-xs', tx.direction === 'credit' ? 'text-emerald-400' : 'text-rose-400']">
                      {{ tx.direction === 'credit' ? '+' : '-' }}{{ formatPrice(tx.amount_usd) }}
                    </div>
                    <div class="text-[9px] text-slate-400">{{ t('balance') }}: {{ formatPrice(tx.balance_after_usd) }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="text-center py-4 text-xs text-slate-500">
                {{ t('no_transactions') }}
              </div>
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
              <div class="text-xl font-black text-emerald-400 font-mono">{{ formatPrice(sellerStats.totalSales || 0) }}</div>
            </div>
            <div class="bg-dark-800/90 border border-slate-700/60 p-3 rounded-xl">
              <span class="text-[10px] text-slate-400">صافي الأرباح</span>
              <div class="text-xl font-black text-teal-400 font-mono">{{ formatPrice(sellerStats.totalProfit || 0) }}</div>
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

          <!-- Seller Action Buttons Grid (Products managed exclusively from Admin Master Catalog) -->
          <div class="grid grid-cols-3 gap-2">
            <button @click="openCustomizer" class="bg-indigo-600/30 hover:bg-indigo-600 border border-indigo-500/40 text-indigo-200 hover:text-white font-bold text-[10px] py-2.5 rounded-xl transition flex flex-col items-center justify-center gap-1 shadow-sm">
              <span class="text-base">🎨</span>
              <span>المظهر</span>
            </button>
            <button @click="openMasterCatalog" class="bg-emerald-600/30 hover:bg-emerald-600 border border-emerald-500/40 text-emerald-200 hover:text-white font-bold text-[10px] py-2.5 rounded-xl transition flex flex-col items-center justify-center gap-1 shadow-sm">
              <span class="text-base">📥</span>
              <span>كتالوج المنصة</span>
            </button>
            <button @click="openBulkModal" class="bg-amber-600/30 hover:bg-amber-600 border border-amber-500/40 text-amber-200 hover:text-white font-bold text-[10px] py-2.5 rounded-xl transition flex flex-col items-center justify-center gap-1 shadow-sm">
              <span class="text-base">📑</span>
              <span>إكسل / CSV</span>
            </button>
          </div>

          <!-- 🎟️ Dedicated Discount Coupons Tracking Center -->
          <div class="bg-dark-800/90 border border-slate-700/80 rounded-2xl p-4 space-y-3 shadow-md">
            <div class="flex items-center justify-between border-b border-slate-700/60 pb-2">
              <div class="flex items-center gap-2">
                <span class="text-base">🎟️</span>
                <div>
                  <h4 class="font-bold text-xs text-white">مركز إنشاء وتتبع أكواد الخصم</h4>
                  <p class="text-[9px] text-slate-400">حدد نسبة الخصم والمدة بالساعات أو الأيام وراقب المبيعات والأرباح</p>
                </div>
              </div>
              <span class="text-[10px] text-amber-400 font-mono font-bold">{{ (sellerCoupons || []).length }} أكواد</span>
            </div>

            <!-- New Coupon Generator Form -->
            <div class="bg-dark-900/80 p-3 rounded-xl border border-slate-800 space-y-2.5">
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="text-[10px] font-bold text-slate-300">كود الخصم (Promo Code):</label>
                  <input v-model="newCouponForm.code" type="text" placeholder="مثال: VIP20" class="w-full bg-dark-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-amber-300 uppercase font-mono font-bold">
                </div>
                <div>
                  <label class="text-[10px] font-bold text-slate-300">نسبة الخصم (%):</label>
                  <div class="flex items-center gap-1">
                    <input v-model.number="newCouponForm.val" type="number" min="1" max="100" placeholder="20" class="w-full bg-dark-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 font-mono font-black">
                    <span class="text-xs text-slate-400 font-bold">%</span>
                  </div>
                </div>
              </div>

              <!-- Duration Selector: Hours or Days -->
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="text-[10px] font-bold text-slate-300">مدة صلاحية الكود:</label>
                  <div class="grid grid-cols-2 gap-1">
                    <input v-model.number="newCouponForm.duration_value" type="number" min="1" placeholder="7" class="w-full bg-dark-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white font-mono text-center">
                    <select v-model="newCouponForm.duration_type" class="bg-dark-800 border border-slate-700 rounded-lg px-1.5 py-1.5 text-[10px] text-sky-300 font-bold">
                      <option value="days">أيام (Days)</option>
                      <option value="hours">ساعات (Hours)</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label class="text-[10px] font-bold text-slate-300">أقصى عدد استخدامات:</label>
                  <input v-model.number="newCouponForm.max_uses" type="number" min="1" placeholder="100" class="w-full bg-dark-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono">
                </div>
              </div>

              <button @click="saveNewCoupon" :disabled="creatingCoupon || !newCouponForm.code" class="w-full bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 disabled:opacity-50 text-slate-900 font-black text-xs py-2 rounded-xl transition shadow flex items-center justify-center gap-1.5">
                <span v-if="creatingCoupon">جاري الحفظ والإنشاء... ⏳</span>
                <span v-else>➕ إنشاء وتفعيل كود الخصم فورياً</span>
              </button>
            </div>

            <!-- Existing Coupons Detailed Tracking List -->
            <div v-if="(sellerCoupons || []).length" class="space-y-2 max-h-56 overflow-y-auto pr-1">
              <div v-for="cp in sellerCoupons" :key="cp.code" class="bg-dark-900 border border-slate-800 p-2.5 rounded-xl space-y-2 text-xs">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <span class="font-mono font-black text-amber-400 text-xs tracking-wider">🎟️ {{ cp.code }}</span>
                    <span class="text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.2 rounded font-black font-mono">
                      {{ cp.discount_percent || cp.val }}% خصم
                    </span>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <span :class="['text-[9px] font-bold px-1.5 py-0.5 rounded-full border', cp.is_active !== false ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40' : 'bg-slate-800 text-slate-400 border-slate-700']">
                      {{ cp.is_active !== false ? 'شغال ✅' : 'معطل ⏸️' }}
                    </span>
                    <span class="text-[9px] text-slate-400 font-mono">{{ cp.remaining_str || cp.duration_display || '' }}</span>
                  </div>
                </div>

                <!-- Comprehensive Coupon Telemetry -->
                <div class="grid grid-cols-3 gap-1.5 bg-dark-850 p-2 rounded-lg text-center font-mono text-[10px]">
                  <div>
                    <span class="text-slate-400 block text-[9px]">مرات الاستخدام</span>
                    <strong class="text-white">{{ cp.used_count || 0 }}</strong>
                    <span class="text-slate-500 text-[8px]"> / {{ cp.max_uses || '∞' }}</span>
                  </div>
                  <div>
                    <span class="text-slate-400 block text-[9px]">وفّر للمشترين</span>
                    <strong class="text-rose-400">{{ formatPrice(cp.total_discounted || cp.total_discount_usd || 0) }}</strong>
                  </div>
                  <div>
                    <span class="text-slate-400 block text-[9px]">مبيعات حققها</span>
                    <strong class="text-emerald-400">{{ formatPrice(cp.total_revenue || 0) }}</strong>
                  </div>
                </div>

                <div class="flex items-center gap-2 pt-1 border-t border-slate-800">
                  <button @click="toggleCoupon(cp.code)" class="flex-1 py-1 rounded-lg text-[10px] font-bold transition border" :class="cp.is_active !== false ? 'bg-amber-950/40 text-amber-300 border-amber-800/40 hover:bg-amber-900/40' : 'bg-emerald-950/40 text-emerald-300 border-emerald-800/40 hover:bg-emerald-900/40'">
                    {{ cp.is_active !== false ? 'إيقاف مؤقت ⏸️' : 'تفعيل الكود ▶️' }}
                  </button>
                  <button @click="deleteCoupon(cp.code)" class="text-rose-400 hover:text-rose-300 px-2.5 py-1 text-[10px] font-bold bg-rose-950/40 border border-rose-800/40 rounded-lg">
                    🗑️ حذف
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 💳 Manual Payment Gateways & Customer Receipts Review -->
          <div class="bg-dark-800/90 border border-slate-700/80 rounded-2xl p-4 space-y-3 shadow-md">
            <div class="flex items-center justify-between border-b border-slate-700/60 pb-2">
              <div class="flex items-center gap-2">
                <span class="text-base">💵</span>
                <h4 class="font-bold text-xs text-white">إشعارات الدفع والتحويل اليدوي (زين كاش، آسيا، USDT)</h4>
              </div>
              <span class="text-[10px] text-amber-400 font-bold">{{ (sellerPaymentReceipts || []).filter(r => r.status === 'pending').length }} بانتظار التأكيد</span>
            </div>

            <div v-if="(sellerPaymentReceipts || []).length" class="space-y-2 max-h-52 overflow-y-auto pr-1">
              <div v-for="rcpt in sellerPaymentReceipts" :key="rcpt.receipt_id" class="bg-dark-900 border border-slate-800 p-2.5 rounded-xl space-y-2 text-xs">
                <div class="flex items-center justify-between">
                  <div class="font-bold text-white flex items-center gap-1.5">
                    <span>{{ rcpt.user_name || 'عميل' }}</span>
                    <span class="text-[10px] text-slate-400 font-mono">(@{{ rcpt.username || rcpt.user_id }})</span>
                  </div>
                  <span :class="['text-[10px] font-bold px-2 py-0.5 rounded-full border', rcpt.status === 'approved' ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40' : (rcpt.status === 'rejected' ? 'bg-rose-950 text-rose-300 border-rose-500/40' : 'bg-amber-950 text-amber-300 border-amber-500/40')]">
                    {{ rcpt.status === 'approved' ? 'مقبول ✅' : (rcpt.status === 'rejected' ? 'مرفوض ❌' : 'قيد المراجعة ⏳') }}
                  </span>
                </div>

                <div class="flex items-center justify-between text-[11px] text-slate-300 font-mono bg-dark-850 p-2 rounded-lg">
                  <div>الطريقة: <span class="text-amber-300 font-bold">{{ rcpt.method }}</span></div>
                  <div>المبلغ: <span class="text-emerald-400 font-black">{{ formatPrice(rcpt.amount_usd) }}</span></div>
                </div>

                <div v-if="rcpt.sender_ref" class="text-[10px] text-slate-400">
                  <span class="font-bold">رقم/هاش العملية: </span><span class="font-mono text-slate-200">{{ rcpt.sender_ref }}</span>
                </div>

                <div v-if="rcpt.image_url" class="text-[10px]">
                  <a :href="rcpt.image_url" target="_blank" class="text-blue-400 hover:underline flex items-center gap-1">
                    <span>🖼️ عرض صورة إشعار التحويل</span>
                  </a>
                </div>

                <div v-if="rcpt.status === 'pending'" class="flex items-center gap-2 pt-1">
                  <button @click="actionSellerReceipt(rcpt.receipt_id, 'approve')" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[10px] py-1.5 rounded-lg shadow transition">
                    ✅ قبول وشحن الرصيد
                  </button>
                  <button @click="actionSellerReceipt(rcpt.receipt_id, 'reject')" class="flex-1 bg-rose-600 hover:bg-rose-500 text-white font-bold text-[10px] py-1.5 rounded-lg shadow transition">
                    ❌ رفض
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-4 text-xs text-slate-500">
              لا توجد إشعارات دفع معلقة حالياً.
            </div>
          </div>

          <!-- 🎡 Fortune Wheel & Abandoned Cart Recovery Toggles -->
          <div class="bg-dark-800/90 border border-slate-700/80 rounded-2xl p-4 space-y-3 shadow-md">
            <h4 class="font-bold text-xs text-slate-200 flex items-center gap-1.5">
              <span>🚀</span> ميزات التسويق التفاعلية وزيادة المبيعات
            </h4>

            <!-- Wheel Toggle -->
            <div class="flex items-center justify-between bg-dark-900 p-3 rounded-xl border border-slate-800">
              <div class="flex items-center gap-2">
                <span class="text-xl">🎡</span>
                <div>
                  <div class="text-xs font-bold text-white">تفعيل عجلة الحظ للزوار (اختياري)</div>
                  <div class="text-[10px] text-slate-400">تظهر أيقونة العجلة للعملاء لتدويرها والفوز بجوائز وخصومات</div>
                </div>
              </div>
              <input type="checkbox" v-model="sellerSettingsForm.wheel_enabled" @change="saveSellerSettingsForm" class="w-5 h-5 rounded text-brand-600 accent-brand-500 cursor-pointer">
            </div>

            <!-- Abandoned Cart Broadcast Button -->
            <div class="flex items-center justify-between bg-dark-900 p-3 rounded-xl border border-slate-800">
              <div class="flex items-center gap-2">
                <span class="text-xl">📢</span>
                <div>
                  <div class="text-xs font-bold text-white">تنبيه السلات المتروكة</div>
                  <div class="text-[10px] text-slate-400">إرسال تنبيه وتوليد كود خصم 10% لكل من أضاف منتجاً للسلة ولم يشترِ</div>
                </div>
              </div>
              <button @click="broadcastAbandonedCart" :disabled="abandonedCartBroadcasting" class="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-3 py-1.5 rounded-xl shadow active:scale-95 transition">
                <span v-if="abandonedCartBroadcasting">...⏳</span>
                <span v-else>📢 إرسال التنبيه</span>
              </button>
            </div>
          </div>

          <!-- Seller Settings Form (Support & Terms & Channel) -->
          <div class="bg-dark-800/90 border border-slate-700/80 rounded-2xl p-4 space-y-3">
            <h4 class="font-bold text-xs text-slate-200 flex items-center gap-1.5">
              <span>⚙️</span> تعديل روابط الدعم الفني وشروط المتجر وقناة الإشعارات
            </h4>

            <!-- Store Default Currency Setting -->
            <div class="space-y-1">
              <label class="text-[11px] font-bold text-slate-300">{{ t('store_currency') }} (تُطبق على البوت والموقع):</label>
              <select v-model="sellerSettingsForm.currency" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-amber-300 font-bold focus:outline-none">
                <option v-for="c in currencyOptions" :key="c.code" :value="c.code">
                  {{ c.symbol }} {{ c.name }} ({{ c.code }})
                </option>
              </select>
              <p class="text-[10px] text-slate-400">تغيير العملة سيقوم بتحديث جميع الأسعار تلقائياً في منيو وقوائم البوت والمتجر المصغر.</p>
            </div>

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
          <div class="space-y-3 pt-1">
            <div class="flex items-center justify-between">
              <h4 class="font-bold text-xs text-slate-200 flex items-center gap-1.5">
                <span>📦</span> إدارة منتجات المتجر
              </h4>
              <span class="text-[10px] text-slate-400 font-mono">{{ sellerProducts.length }} منتج معروض</span>
            </div>

            <!-- Seller Action Buttons Bar (Restricted: Products originate strictly from Central Catalog) -->
            <div class="grid grid-cols-2 gap-2">
              <button @click="resetSellerProducts" class="bg-dark-800 hover:bg-dark-750 text-sky-300 border border-sky-500/30 font-bold text-[10px] py-2 px-2 rounded-xl shadow active:scale-95 transition flex items-center justify-center gap-1.5">
                <span>🔄</span>
                <span>استرجاع المحذوفة</span>
              </button>
              <button @click="resetSellerPrices" class="bg-dark-800 hover:bg-dark-750 text-amber-300 border border-amber-500/30 font-bold text-[10px] py-2 px-2 rounded-xl shadow active:scale-95 transition flex items-center justify-center gap-1.5">
                <span>🏷️</span>
                <span>استعادة أسعار الآدمن</span>
              </button>
            </div>

            <div v-if="sellerProducts.length" class="space-y-2">
              <div v-for="prod in sellerProducts" :key="prod.id" class="bg-dark-800 border border-slate-700/80 p-3 rounded-2xl space-y-2 text-xs">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2.5">
                    <div class="w-11 h-11 rounded-xl bg-dark-750 flex items-center justify-center overflow-hidden border border-slate-700 shrink-0">
                      <img v-if="(prod.mediaUrls && prod.mediaUrls[0]) || prod.image_url" :src="(prod.mediaUrls && prod.mediaUrls[0]) || prod.image_url" class="w-full h-full object-cover">
                      <span v-else class="text-lg">🛍️</span>
                    </div>
                    <div>
                      <div class="font-bold text-white flex items-center gap-1.5">
                        <span>{{ prod.nameAr || prod.name }}</span>
                        <span v-if="prod.is_master" class="text-[9px] bg-rose-500/20 text-rose-300 border border-rose-500/30 px-1.5 py-0.2 rounded-md font-bold">مركزي 👑</span>
                        <span v-else class="text-[9px] bg-sky-500/20 text-sky-300 border border-sky-500/30 px-1.5 py-0.2 rounded-md font-bold">متجرك 🏪</span>
                      </div>
                      <div v-if="prod.is_master" class="text-[9px] text-amber-400 flex items-center gap-1 mt-0.5">
                        <span>🔒 المتطلبات مقفلة من الآدمن</span>
                      </div>
                    </div>
                  </div>

                  <span :class="['text-[10px] font-bold px-2 py-0.5 rounded-full border shrink-0', prod.active !== false ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40' : 'bg-slate-800 text-slate-400 border-slate-700']">
                    {{ prod.active !== false ? 'معروض ✅' : 'مخفي ⏸️' }}
                  </span>
                </div>

                <!-- Price & Profit Display Pill -->
                <div class="bg-dark-900/90 border border-slate-800 p-2 rounded-xl flex items-center justify-between text-[11px] font-mono">
                  <div class="text-slate-400">
                    جملة الآدمن: <span class="text-slate-200 font-bold">{{ formatPrice(prod.cost_price || prod.costPrice || 0) }}</span>
                  </div>
                  <div class="text-slate-400">
                    البيع: <span class="text-white font-black">{{ formatPrice(prod.price_usd || prod.userPrice || 0) }}</span>
                  </div>
                  <div class="text-emerald-400 font-black">
                    ربح: +{{ formatPrice(((prod.price_usd || prod.userPrice || 0) - (prod.cost_price || prod.costPrice || 0))) }}
                  </div>
                </div>

                <!-- Card Actions -->
                <div class="flex items-center gap-2 pt-1 border-t border-slate-700/50">
                  <button @click="openEditSellerProduct(prod)" class="flex-1 bg-brand-600/20 hover:bg-brand-600/30 text-brand-300 border border-brand-500/30 font-bold text-[10px] py-1.5 rounded-lg transition active:scale-95 flex items-center justify-center gap-1">
                    <span>✏️</span>
                    <span>تعديل السعر والوصف</span>
                  </button>
                  <button @click="toggleProductActive(prod.id)" class="px-2.5 py-1.5 bg-dark-750 hover:bg-dark-700 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold transition">
                    {{ prod.active !== false ? 'إخفاء ⏸️' : 'إظهار ▶️' }}
                  </button>
                  <button @click="deleteSellerProduct(prod.id)" class="px-2.5 py-1.5 bg-rose-950/40 hover:bg-rose-900/40 text-rose-300 border border-rose-800/40 rounded-lg text-[10px] font-bold transition">
                    🗑️
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-6 text-xs text-slate-500 bg-dark-800/40 rounded-xl">
              لا توجد منتجات مفعلة حالياً في متجرك. اضغط على "استعادة المنتجات الأصلية" لتنزيل كافة المنتجات من كتالوج الأدمن المركزي فوراً!
            </div>
          </div>
        </div>

        <!-- ──────────────────────────────────────────────────────────────── -->
        <!-- TAB 5: SUPER ADMIN DASHBOARD (👑 الأدمن الأعلى لبوت صانع البوتات)  -->
        <!-- ──────────────────────────────────────────────────────────────── -->
        <div v-if="currentTab === 'admin' && role === 'admin'" class="space-y-4">
          <!-- Admin Dashboard Header -->
          <div class="flex items-center justify-between border-b border-rose-900/40 pb-2.5">
            <div>
              <h3 class="font-black text-sm text-rose-300 flex items-center gap-1.5">
                <span>👑</span> لوحة تحكم صانع البوتات والمنصة المركزية
              </h3>
              <p class="text-[10px] text-slate-400">إدارة الكتالوج العام لكافة القوالب، الأسعار، الإحصائيات، والبوتات</p>
            </div>
            <span class="text-[10px] bg-rose-500/20 text-rose-400 border border-rose-500/30 px-2 py-0.5 rounded-full font-bold">Admin Only</span>
          </div>

          <!-- Admin Sub-Navigation Dock (6 Full Management Sections) -->
          <div class="grid grid-cols-6 gap-1 bg-dark-900/80 p-1 rounded-2xl border border-slate-800 text-[10px] font-bold">
            <button @click="adminActiveSubTab = 'catalog'" :class="['py-2 px-1 rounded-xl transition text-center flex flex-col items-center gap-0.5', adminActiveSubTab === 'catalog' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
              <span>🛍️</span>
              <span class="truncate">الكتالوج</span>
            </button>
            <button @click="adminActiveSubTab = 'stats'" :class="['py-2 px-1 rounded-xl transition text-center flex flex-col items-center gap-0.5', adminActiveSubTab === 'stats' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
              <span>📊</span>
              <span class="truncate">الإحصائيات</span>
            </button>
            <button @click="adminActiveSubTab = 'orders'" :class="['py-2 px-1 rounded-xl transition text-center flex flex-col items-center gap-0.5', adminActiveSubTab === 'orders' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
              <span>🧾</span>
              <span class="truncate">الطلبات</span>
            </button>
            <button @click="adminActiveSubTab = 'templates'" :class="['py-2 px-1 rounded-xl transition text-center flex flex-col items-center gap-0.5', adminActiveSubTab === 'templates' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
              <span>🎨</span>
              <span class="truncate">القوالب</span>
            </button>
            <button @click="adminActiveSubTab = 'bots'" :class="['py-2 px-1 rounded-xl transition text-center flex flex-col items-center gap-0.5', adminActiveSubTab === 'bots' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
              <span>🤖</span>
              <span class="truncate">البوتات</span>
            </button>
            <button @click="adminActiveSubTab = 'broadcast'" :class="['py-2 px-1 rounded-xl transition text-center flex flex-col items-center gap-0.5', adminActiveSubTab === 'broadcast' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200']">
              <span>📢</span>
              <span class="truncate">إذاعة</span>
            </button>
          </div>

          <!-- ── SUB-TAB 1: MASTER DIGITAL CATALOG ── -->
          <div v-if="adminActiveSubTab === 'catalog'" class="space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <h4 class="font-bold text-xs text-white flex items-center gap-1.5">
                  <span>🛍️</span> الكتالوج الرقمي العام (القوالب الأربعة)
                </h4>
                <p class="text-[10px] text-slate-400">أي منتج تضيفه أو تعدله هنا ينزل فورياً لجميع المتاجر والبائعين</p>
              </div>
              <button @click="openAddAdminProduct" class="bg-rose-600 hover:bg-rose-500 text-white font-bold text-[11px] py-1.5 px-3 rounded-xl shadow active:scale-95 transition flex items-center gap-1">
                <span>➕</span>
                <span>إضافة منتج</span>
              </button>
            </div>

            <!-- Category Filter Tabs -->
            <div class="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
              <button @click="adminCategoryFilter = 'all'" :class="['px-2.5 py-1 rounded-lg text-[10px] font-bold whitespace-nowrap transition', adminCategoryFilter === 'all' ? 'bg-rose-600 text-white' : 'bg-dark-800 text-slate-400 border border-slate-700']">
                الكل ({{ adminProducts.length }})
              </button>
              <button @click="adminCategoryFilter = 'gaming'" :class="['px-2.5 py-1 rounded-lg text-[10px] font-bold whitespace-nowrap transition', adminCategoryFilter === 'gaming' ? 'bg-rose-600 text-white' : 'bg-dark-800 text-slate-400 border border-slate-700']">
                🎮 ألعاب
              </button>
              <button @click="adminCategoryFilter = 'subscriptions'" :class="['px-2.5 py-1 rounded-lg text-[10px] font-bold whitespace-nowrap transition', adminCategoryFilter === 'subscriptions' ? 'bg-rose-600 text-white' : 'bg-dark-800 text-slate-400 border border-slate-700']">
                📺 اشتراكات
              </button>
              <button @click="adminCategoryFilter = 'telegram'" :class="['px-2.5 py-1 rounded-lg text-[10px] font-bold whitespace-nowrap transition', adminCategoryFilter === 'telegram' ? 'bg-rose-600 text-white' : 'bg-dark-800 text-slate-400 border border-slate-700']">
                ⭐ تيليجرام
              </button>
              <button @click="adminCategoryFilter = 'numbers'" :class="['px-2.5 py-1 rounded-lg text-[10px] font-bold whitespace-nowrap transition', adminCategoryFilter === 'numbers' ? 'bg-rose-600 text-white' : 'bg-dark-800 text-slate-400 border border-slate-700']">
                📱 أرقام
              </button>
              <button @click="adminCategoryFilter = 'smm'" :class="['px-2.5 py-1 rounded-lg text-[10px] font-bold whitespace-nowrap transition', adminCategoryFilter === 'smm' ? 'bg-rose-600 text-white' : 'bg-dark-800 text-slate-400 border border-slate-700']">
                🚀 دعم ورشق
              </button>
            </div>

            <!-- Master Products Grid -->
            <div v-if="filteredAdminProducts.length" class="space-y-2">
              <div v-for="prod in filteredAdminProducts" :key="prod.id" class="bg-dark-800 border border-slate-700 p-3 rounded-2xl space-y-2 text-xs">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2.5">
                    <div class="w-12 h-12 rounded-xl bg-dark-750 flex items-center justify-center overflow-hidden border border-slate-700 shrink-0">
                      <img v-if="prod.image_url" :src="prod.image_url" class="w-full h-full object-cover">
                      <span v-else class="text-xl">🛍️</span>
                    </div>
                    <div>
                      <div class="font-bold text-white text-sm">{{ prod.name_ar || prod.name }}</div>
                      <div class="text-[10px] text-slate-400 font-mono">{{ prod.name }}</div>
                      <div class="flex items-center gap-1.5 mt-1 flex-wrap">
                        <span class="text-[9px] bg-slate-700 text-slate-200 px-1.5 py-0.2 rounded font-mono">{{ prod.category }}</span>
                        <span class="text-[9px] bg-brand-900/50 text-brand-300 border border-brand-700/50 px-1.5 py-0.2 rounded font-mono">{{ prod.template_type }}</span>
                      </div>
                    </div>
                  </div>

                  <span class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-500/40 px-2 py-0.5 rounded-full font-bold">
                    معمم للجميع ✅
                  </span>
                </div>

                <!-- Prices info -->
                <div class="bg-dark-900 p-2 rounded-xl flex items-center justify-between text-[11px] font-mono border border-slate-800">
                  <div class="text-slate-400">
                    التكلفة عليك: <span class="text-rose-400 font-bold">{{ formatPrice(prod.cost_price || 0) }}</span>
                  </div>
                  <div class="text-slate-400">
                    سعر البدء المقترح: <span class="text-white font-black">{{ formatPrice(prod.base_user_price || 0) }}</span>
                  </div>
                  <div class="text-emerald-400 font-black">
                    ربح مقترح: +{{ formatPrice((prod.base_user_price || 0) - (prod.cost_price || 0)) }}
                  </div>
                </div>

                <!-- Requirements display -->
                <div v-if="prod.requirements && prod.requirements.length" class="flex items-center gap-1.5 flex-wrap pt-0.5">
                  <span class="text-[10px] text-slate-400">المتطلبات المقفلة:</span>
                  <span v-for="r in prod.requirements" :key="r.name" class="text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-md font-bold">
                    🔒 {{ r.label }}
                  </span>
                </div>

                <!-- Card Actions -->
                <div class="flex items-center gap-2 pt-1 border-t border-slate-700/60">
                  <button @click="openEditAdminProduct(prod)" class="flex-1 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 font-bold text-[11px] py-1.5 rounded-xl transition active:scale-95 flex items-center justify-center gap-1">
                    <span>✏️</span>
                    <span>تعديل السعر والمتطلبات والصورة</span>
                  </button>
                  <button @click="deleteAdminProduct(prod.id)" class="px-3 py-1.5 bg-rose-950/50 hover:bg-rose-900/50 text-rose-300 border border-rose-800/50 rounded-xl text-[11px] font-bold transition active:scale-95">
                    <span>🗑️ حذف</span>
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-8 text-xs text-slate-500 bg-dark-800/30 rounded-2xl">
              لا توجد منتجات عامة مسجلة في هذا القسم. اضغط "إضافة منتج" لنشر أول منتج مركزي!
            </div>
          </div>

          <!-- ── SUB-TAB 2: PLATFORM OVERVIEW & STATS ── -->
          <div v-if="adminActiveSubTab === 'stats'" class="space-y-3">
            <h4 class="font-bold text-xs text-white flex items-center gap-1.5">
              <span>📊</span> إحصائيات ونشاط المنصة الشامل
            </h4>
            <div class="grid grid-cols-2 gap-2.5">
              <div class="bg-dark-800 border border-slate-700 p-3.5 rounded-2xl">
                <span class="text-[10px] text-slate-400">إجمالي المتاجر والبوتات</span>
                <div class="text-2xl font-black text-rose-300 mt-1 font-mono">{{ adminBots.length || adminOverview.totalStores || 1 }}</div>
              </div>
              <div class="bg-dark-800 border border-slate-700 p-3.5 rounded-2xl">
                <span class="text-[10px] text-slate-400">حجم تعاملات المنصة</span>
                <div class="text-2xl font-black text-emerald-400 mt-1 font-mono">{{ formatPrice(adminOverview.totalPlatformVolume || 0) }}</div>
              </div>
              <div class="bg-dark-800 border border-slate-700 p-3.5 rounded-2xl">
                <span class="text-[10px] text-slate-400">إجمالي طلبات المنصة</span>
                <div class="text-2xl font-black text-white mt-1 font-mono">{{ adminOverview.totalOrders || 0 }}</div>
              </div>
              <div class="bg-dark-800 border border-slate-700 p-3.5 rounded-2xl">
                <span class="text-[10px] text-slate-400">طلبات معلقة للتنفيذ</span>
                <div class="text-2xl font-black text-amber-400 mt-1 font-mono">{{ adminOverview.pendingManualOrders || 0 }}</div>
              </div>
            </div>
          </div>

          <!-- ── SUB-TAB 3: PLATFORM BOTS LIST ── -->
          <div v-if="adminActiveSubTab === 'bots'" class="space-y-3">
            <div class="flex items-center justify-between">
              <h4 class="font-bold text-xs text-white flex items-center gap-1.5">
                <span>🤖</span> قائمة بوتات ومتاجر المنصة
              </h4>
              <span class="text-[10px] text-slate-400 font-mono">{{ adminBots.length }} بوت نشط</span>
            </div>

            <div v-if="adminBots.length" class="space-y-2">
              <div v-for="b in adminBots" :key="b.bot_id" class="bg-dark-800 border border-slate-700 p-3 rounded-2xl text-xs space-y-2">
                <div class="flex items-center justify-between">
                  <div>
                    <div class="font-bold text-white text-sm">@{{ b.username || 'بدون يوزر' }}</div>
                    <div class="text-[10px] text-slate-400">المالك: {{ b.owner_name }} ({{ b.owner_id }})</div>
                  </div>
                  <span class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-500/40 px-2 py-0.5 rounded-full font-bold">
                    {{ b.status === 'active' ? 'نشط 🟢' : b.status }}
                  </span>
                </div>
                <div class="flex items-center justify-between text-[10px] text-slate-400 bg-dark-900 p-2 rounded-xl">
                  <span>القالب: <strong class="text-sky-300">{{ b.template_type }}</strong></span>
                  <span>الرصيد: <strong class="text-emerald-400 font-mono">${{ b.balance_usd || 0 }}</strong></span>
                  <a v-if="b.username" :href="'https://t.me/' + b.username" target="_blank" class="text-brand-400 hover:underline">فتح البوت ↗</a>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-6 text-xs text-slate-500 bg-dark-800/30 rounded-2xl">
              لا توجد بوتات مسجلة بعد في قاعدة البيانات
            </div>
          </div>

          <!-- ── SUB-TAB 4: MASTER ORDERS FULFILLMENT CENTER (مركز تسليم الطلبات وإدارة العمليات 20+ ميزة) ── -->
          <div v-if="adminActiveSubTab === 'orders'" class="space-y-3.5">
            <div class="flex items-center justify-between border-b border-rose-900/40 pb-2">
              <div>
                <h4 class="font-black text-xs text-white flex items-center gap-1.5">
                  <span>🧾</span> مركز تسليم وإدارة طلبات المنصة المركزية
                </h4>
                <p class="text-[10px] text-slate-400">تتبع الطلبات، بيانات البوتات، البائعين، المشترين، والتسليم الفوري لتيليجرام</p>
              </div>
              <button @click="loadAdminOrders" class="text-[10px] bg-dark-800 hover:bg-dark-750 text-slate-300 border border-slate-700 px-2 py-1 rounded-lg font-bold">
                تحديث 🔄
              </button>
            </div>

            <!-- Fulfillment KPI Telemetry Stats -->
            <div class="grid grid-cols-4 gap-1.5 font-mono text-center">
              <div class="bg-dark-850 border border-slate-800 p-2 rounded-xl">
                <span class="text-[9px] text-slate-400 block font-sans">الكل</span>
                <strong class="text-white text-xs">{{ adminOrders.length }}</strong>
              </div>
              <div class="bg-dark-850 border border-amber-500/30 p-2 rounded-xl">
                <span class="text-[9px] text-amber-300 block font-sans">معلق ⏳</span>
                <strong class="text-amber-400 text-xs">{{ adminOrders.filter(o => o.status === 'pending' || o.status === 'processing').length }}</strong>
              </div>
              <div class="bg-dark-850 border border-emerald-500/30 p-2 rounded-xl">
                <span class="text-[9px] text-emerald-300 block font-sans">مكتمل ✅</span>
                <strong class="text-emerald-400 text-xs">{{ adminOrders.filter(o => o.status === 'completed').length }}</strong>
              </div>
              <div class="bg-dark-850 border border-slate-800 p-2 rounded-xl">
                <span class="text-[9px] text-slate-400 block font-sans">إجمالي $</span>
                <strong class="text-emerald-400 text-xs">{{ formatPrice(adminOrders.reduce((sum, o) => sum + (Number(o.seller_price_usd || o.price_user_usd || o.total_price || 0)), 0)) }}</strong>
              </div>
            </div>

            <!-- Search, Status Filter & Export Bar -->
            <div class="space-y-2 bg-dark-850 p-2.5 rounded-xl border border-slate-800">
              <div class="flex items-center gap-1.5">
                <input v-model="adminOrdersSearchQuery" type="text" placeholder="بحث برقم الطلب، يوزر المشتري، البائع، أو البوت..." class="flex-1 bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                <button @click="exportOrdersCsv" class="bg-dark-750 hover:bg-dark-700 text-sky-300 border border-sky-500/30 px-2 py-1.5 rounded-lg text-[10px] font-bold whitespace-nowrap">
                  تصدير CSV 📥
                </button>
              </div>

              <!-- Status Filter Pills -->
              <div class="flex items-center gap-1 overflow-x-auto text-[10px] font-bold">
                <button @click="adminOrdersStatusFilter = 'all'" :class="['px-2.5 py-1 rounded-lg transition', adminOrdersStatusFilter === 'all' ? 'bg-rose-600 text-white' : 'bg-dark-800 text-slate-400']">
                  كافة الطلبات ({{ adminOrders.length }})
                </button>
                <button @click="adminOrdersStatusFilter = 'pending'" :class="['px-2.5 py-1 rounded-lg transition', adminOrdersStatusFilter === 'pending' ? 'bg-amber-600 text-white' : 'bg-dark-800 text-amber-300']">
                  بانتظار التسليم ⏳ ({{ adminOrders.filter(o => o.status === 'pending' || o.status === 'processing').length }})
                </button>
                <button @click="adminOrdersStatusFilter = 'completed'" :class="['px-2.5 py-1 rounded-lg transition', adminOrdersStatusFilter === 'completed' ? 'bg-emerald-600 text-white' : 'bg-dark-800 text-emerald-300']">
                  المكتملة ✅ ({{ adminOrders.filter(o => o.status === 'completed').length }})
                </button>
                <button @click="adminOrdersStatusFilter = 'canceled'" :class="['px-2.5 py-1 rounded-lg transition', adminOrdersStatusFilter === 'canceled' ? 'bg-slate-700 text-white' : 'bg-dark-800 text-slate-400']">
                  الملغية والمسترجعة 🔄
                </button>
              </div>
            </div>

            <!-- Orders Cards List -->
            <div v-if="filteredAdminOrdersList.length" class="space-y-3">
              <div v-for="ord in filteredAdminOrdersList" :key="ord.id || ord.order_ref || ord.order_id" class="bg-dark-800 border border-slate-700/80 p-3.5 rounded-2xl space-y-2.5 text-xs shadow-md">
                <!-- Card Header: Ref, Time, Status -->
                <div class="flex items-center justify-between border-b border-slate-700/60 pb-2">
                  <div class="flex items-center gap-2">
                    <span class="font-mono font-black text-rose-300 text-xs">#{{ ord.order_ref || ord.order_id }}</span>
                    <button @click="copyToClipboard(ord.order_ref || ord.order_id)" class="text-[10px] text-slate-400 hover:text-white">📋</button>
                    <span class="text-[10px] text-slate-400 font-mono">🕒 {{ ord.created_at || ord.created }}</span>
                  </div>
                  <span :class="['text-[10px] font-bold px-2 py-0.5 rounded-full border', getStatusBadgeClass(ord.status)]">
                    {{ getStatusLabelAr(ord.status) }}
                  </span>
                </div>

                <!-- Product & Template Info -->
                <div class="flex items-center justify-between bg-dark-850 p-2 rounded-xl">
                  <div class="font-bold text-white flex items-center gap-1.5">
                    <span>📦</span>
                    <span>{{ ord.service_name || ord.product_name }}</span>
                  </div>
                  <span class="text-[10px] bg-slate-700 text-slate-300 px-2 py-0.5 rounded-md font-mono">
                    {{ ord.template_type || ord.category || 'عام' }}
                  </span>
                </div>

                <!-- Three-Party Telemetry Grid (البوت، البائع، المشتري) -->
                <div class="grid grid-cols-3 gap-1.5 bg-dark-900/90 p-2.5 rounded-xl border border-slate-800 text-[10px]">
                  <!-- Bot Info -->
                  <div class="space-y-0.5">
                    <span class="text-slate-400 block font-bold">🤖 البوت المصدر:</span>
                    <a v-if="ord.bot_username" :href="'https://t.me/' + ord.bot_username" target="_blank" class="text-sky-400 font-bold hover:underline truncate block">
                      @{{ ord.bot_username }}
                    </a>
                    <span v-else class="text-slate-300 font-mono truncate block">ID: {{ ord.bot_id }}</span>
                  </div>

                  <!-- Seller Info -->
                  <div class="space-y-0.5">
                    <span class="text-slate-400 block font-bold">🏪 البائع (المالك):</span>
                    <a v-if="ord.seller_username" :href="'https://t.me/' + ord.seller_username" target="_blank" class="text-amber-400 font-bold hover:underline truncate block">
                      @{{ ord.seller_username }}
                    </a>
                    <span v-else class="text-slate-300 font-mono truncate block">{{ ord.seller_name || ord.seller_id }}</span>
                    <span class="text-[9px] text-slate-500 font-mono block">ID: {{ ord.seller_id }}</span>
                  </div>

                  <!-- Buyer Info -->
                  <div class="space-y-0.5">
                    <span class="text-slate-400 block font-bold">👤 المشتري (الزبون):</span>
                    <a v-if="ord.buyer_username" :href="'https://t.me/' + ord.buyer_username" target="_blank" class="text-emerald-400 font-bold hover:underline truncate block">
                      @{{ ord.buyer_username }}
                    </a>
                    <span v-else class="text-slate-300 truncate block">{{ ord.buyer_name || 'عميل' }}</span>
                    <span class="text-[9px] text-slate-500 font-mono block">ID: {{ ord.user_id || ord.buyer_id }}</span>
                  </div>
                </div>

                <!-- Financial Telemetry Breakdown -->
                <div class="grid grid-cols-4 gap-1 bg-dark-850 p-2 rounded-xl text-center font-mono text-[10px] border border-slate-800">
                  <div>
                    <span class="text-slate-400 block text-[9px] font-sans">جملة الآدمن</span>
                    <strong class="text-slate-200">{{ formatPrice(ord.cost_price_usd || ord.cost_price || 0) }}</strong>
                  </div>
                  <div>
                    <span class="text-slate-400 block text-[9px] font-sans">سعر البيع</span>
                    <strong class="text-white">{{ formatPrice(ord.seller_price_usd || ord.price_user_usd || ord.total_price || 0) }}</strong>
                  </div>
                  <div>
                    <span class="text-slate-400 block text-[9px] font-sans">ربح البائع</span>
                    <strong class="text-emerald-400">+{{ formatPrice(ord.profit_seller_usd || 0) }}</strong>
                  </div>
                  <div>
                    <span class="text-slate-400 block text-[9px] font-sans">كود الخصم</span>
                    <strong class="text-amber-400">{{ ord.discount_code ? ord.discount_code : 'لا يوجد' }}</strong>
                  </div>
                </div>

                <!-- Customer Submitted Credentials / Requirements (بيانات الشراء المطلوبة) -->
                <div class="bg-dark-900 border border-slate-700/80 p-2.5 rounded-xl space-y-1">
                  <div class="flex items-center justify-between">
                    <span class="text-[10px] font-bold text-amber-300 flex items-center gap-1">
                      <span>🔑</span> بيانات ومدخلات المشتري للطلب:
                    </span>
                    <button @click="copyToClipboard(ord.target || ord.customer_credentials || '')" class="text-[9px] bg-dark-750 text-slate-300 hover:text-white px-2 py-0.5 rounded font-bold border border-slate-700">
                      نسخ البيانات 📋
                    </button>
                  </div>
                  <div class="font-mono text-xs text-white bg-dark-850 p-2 rounded-lg break-all select-all border border-slate-800">
                    {{ ord.target || ord.customer_credentials || 'لا توجد متطلبات إضافية مسجلة' }}
                  </div>
                </div>

                <!-- Delivery Information if already Fulfilled -->
                <div v-if="ord.delivery_text || ord.delivery_proof" class="bg-emerald-950/30 border border-emerald-500/30 p-2.5 rounded-xl space-y-1 text-[11px]">
                  <div class="text-emerald-300 font-bold flex items-center gap-1">
                    <span>✅</span> تم تسليم الطلب للعميل بمحتوى:
                  </div>
                  <div class="font-mono text-slate-200 bg-dark-900/80 p-2 rounded break-all">
                    {{ ord.delivery_text }}
                  </div>
                  <div v-if="ord.delivery_proof" class="pt-0.5">
                    <a :href="ord.delivery_proof" target="_blank" class="text-sky-400 text-[10px] underline hover:text-sky-300">
                      📎 عرض رابط إثبات التسليم
                    </a>
                  </div>
                </div>

                <!-- Secret Admin Notes Section -->
                <div class="flex items-center gap-1.5 pt-1">
                  <input v-model="ord.admin_notes" type="text" placeholder="ملاحظة إدارية سرية خاصة بهذا الطلب..." class="flex-1 bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1 text-[11px] text-slate-300">
                  <button @click="saveOrderAdminNotes(ord)" class="bg-dark-750 hover:bg-dark-700 text-slate-300 border border-slate-700 px-2 py-1 rounded-lg text-[10px] font-bold">
                    حفظ 📝
                  </button>
                </div>

                <!-- Execution Action Buttons -->
                <div class="grid grid-cols-3 gap-1.5 pt-1 border-t border-slate-700/60">
                  <button @click="openDeliverOrderModal(ord)" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 py-2 rounded-xl text-white font-black text-xs shadow flex items-center justify-center gap-1">
                    <span>🚀</span>
                    <span>تسليم وإرسال</span>
                  </button>
                  <button @click="handleAdminOrderAction(ord.order_ref || ord.order_id, 'refund_both')" class="bg-purple-600 hover:bg-purple-500 py-2 rounded-xl text-white font-bold text-xs shadow flex items-center justify-center gap-1">
                    <span>🔄</span>
                    <span>استرجاع</span>
                  </button>
                  <button @click="openRejectOrderModal(ord)" class="bg-rose-600 hover:bg-rose-500 py-2 rounded-xl text-white font-bold text-xs shadow flex items-center justify-center gap-1">
                    <span>❌</span>
                    <span>إلغاء ورفض</span>
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-8 text-xs text-slate-500 bg-dark-800/30 rounded-2xl border border-slate-800">
              لا توجد طلبات تطابق معايير الفلترة المحددة
            </div>
          </div>

          <!-- ── SUB-TAB 5: TEMPLATES CUSTOMIZATION (إدارة وتعديل القوالب الأربعة) ── -->
          <div v-if="adminActiveSubTab === 'templates'" class="space-y-3.5">
            <div class="flex items-center justify-between border-b border-rose-900/40 pb-2">
              <div>
                <h4 class="font-black text-xs text-white flex items-center gap-1.5">
                  <span>🎨</span> إدارة وتخصيص القوالب الأربعة للمنصة
                </h4>
                <p class="text-[10px] text-slate-400">تعديل الاسم، الوصف، رسائل الترحيب، ونسب الربح لكل قالب تنزل فورياً للبائعين</p>
              </div>
              <button @click="loadAdminTemplates" class="text-[10px] bg-dark-800 hover:bg-dark-750 text-slate-300 border border-slate-700 px-2 py-1 rounded-lg font-bold">
                تحديث 🔄
              </button>
            </div>

            <div class="space-y-3">
              <div v-for="tpl in adminTemplates" :key="tpl.key" class="bg-dark-800 border border-slate-700 p-4 rounded-2xl space-y-3 shadow-md">
                <div class="flex items-center justify-between border-b border-slate-700/60 pb-2">
                  <div class="flex items-center gap-2.5">
                    <span class="text-2xl">{{ tpl.emoji || '📦' }}</span>
                    <div>
                      <h5 class="font-black text-xs text-white">{{ tpl.name }}</h5>
                      <span class="text-[10px] text-sky-400 font-mono font-bold">{{ tpl.key }}</span>
                    </div>
                  </div>
                  <label class="flex items-center gap-1.5 cursor-pointer text-xs font-bold" :class="tpl.is_active ? 'text-emerald-400' : 'text-slate-400'">
                    <input type="checkbox" v-model="tpl.is_active" class="accent-emerald-500 rounded">
                    <span>{{ tpl.is_active ? 'قالب نشط' : 'قالب معطل' }}</span>
                  </label>
                </div>

                <div class="space-y-2 text-xs">
                  <div>
                    <label class="block text-[10px] font-bold text-slate-300 mb-1">اسم القالب المعروض:</label>
                    <input v-model="tpl.name" type="text" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white font-bold">
                  </div>
                  <div>
                    <label class="block text-[10px] font-bold text-slate-300 mb-1">الوصف العام للقالب:</label>
                    <input v-model="tpl.description" type="text" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white">
                  </div>
                  <div>
                    <label class="block text-[10px] font-bold text-slate-300 mb-1">رسالة الترحيب في بوتات هذا القالب:</label>
                    <textarea v-model="tpl.welcome_text" rows="2" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white"></textarea>
                  </div>
                  <div class="grid grid-cols-2 gap-2">
                    <div>
                      <label class="block text-[10px] font-bold text-slate-300 mb-1">لون الهوية البصرية:</label>
                      <div class="flex items-center gap-2">
                        <input v-model="tpl.theme_color" type="color" class="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0">
                        <span class="font-mono text-xs text-slate-300">{{ tpl.theme_color }}</span>
                      </div>
                    </div>
                    <div>
                      <label class="block text-[10px] font-bold text-slate-300 mb-1">نسبة الربح الافتراضية (%):</label>
                      <input v-model.number="tpl.default_margin_pct" type="number" min="0" max="100" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-emerald-400 font-mono font-bold">
                    </div>
                  </div>
                </div>

                <button @click="saveAdminTemplateConfig(tpl)" class="w-full bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 text-white font-black text-xs py-2 rounded-xl transition shadow flex items-center justify-center gap-1.5">
                  <span>💾</span>
                  <span>حفظ وتطبيق تعديلات القالب فورياً</span>
                </button>
              </div>
            </div>
          </div>

          <!-- ── SUB-TAB 5: PLATFORM BROADCAST ── -->
          <div v-if="adminActiveSubTab === 'broadcast'" class="space-y-3">
            <h4 class="font-bold text-xs text-white flex items-center gap-1.5">
              <span>📢</span> إذاعة وتنبيهات عامة من صانع البوتات
            </h4>
            <div class="bg-dark-800 border border-slate-700 p-3.5 rounded-2xl space-y-3">
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">الجمهور المستهدف بالإذاعة:</label>
                <select v-model="adminBroadcastTarget" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                  <option value="owners">أصحاب المتاجر وصناع البوتات فقط (Bot Owners)</option>
                  <option value="all">كافة المستخدمين والمشترين في المنصة (All Users)</option>
                </select>
              </div>

              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">نص الرسالة والإشعار:</label>
                <textarea v-model="adminBroadcastMsg" rows="4" placeholder="اكتب نص الإشعار هنا ليصل فورياً في محادثات التليجرام..." class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white leading-relaxed"></textarea>
              </div>

              <button @click="sendAdminBroadcast" :disabled="sendingBroadcast || !adminBroadcastMsg.trim()" class="w-full bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold text-xs py-2.5 rounded-xl transition shadow flex items-center justify-center gap-1.5">
                <span v-if="sendingBroadcast">جاري إرسال الإذاعة... ⏳</span>
                <span v-else>📢 إرسال الإذاعة فورياً لجميع المحددين</span>
              </button>
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
            <span>{{ t('nav_store') }}</span>
          </button>
          <!-- Orders Tab -->
          <button @click="currentTab = 'orders'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'orders' ? 'text-brand-400' : 'text-slate-400']">
            <span class="text-base">📦</span>
            <span>{{ t('nav_orders') }}</span>
          </button>
          <!-- My Account Tab -->
          <button @click="currentTab = 'account'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'account' ? 'text-brand-400' : 'text-slate-400']">
            <span class="text-base">👤</span>
            <span>{{ t('nav_account') }}</span>
          </button>
          <!-- Seller Tab (Owner/Admin only) -->
          <button v-if="role === 'seller' || role === 'admin'" @click="currentTab = 'seller'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'seller' ? 'text-brand-400' : 'text-slate-400']">
            <span class="text-base">⚙️</span>
            <span>{{ t('nav_seller') }}</span>
          </button>
          <!-- Admin Tab (Admin only) -->
          <button v-if="role === 'admin'" @click="currentTab = 'admin'" :class="['flex flex-col items-center gap-1 text-[10px] font-bold transition', currentTab === 'admin' ? 'text-rose-400' : 'text-slate-400']">
            <span class="text-base">👑</span>
            <span>{{ t('nav_admin') }}</span>
          </button>
        </div>
      </nav>

      <!-- ════════════════════════════════════════════════════════════════════ -->
      <!-- 4. MODALS & SUB-SCREENS                                              -->
      <!-- ════════════════════════════════════════════════════════════════════ -->

      <!-- A. DEDICATED FULL PRODUCT SCREEN (صفحة كاملة وتفصيلية للمنتج) -->
      <div v-if="activeProduct" class="fixed inset-0 z-50 bg-dark-900 overflow-y-auto flex flex-col pb-24 safe-top">
        <!-- Sticky Navigation Bar -->
        <header class="sticky top-0 z-10 glass-panel border-b border-slate-800/80 px-4 py-3 flex items-center justify-between">
          <button @click="activeProduct = null" class="flex items-center gap-1.5 text-xs font-bold text-slate-300 hover:text-white bg-dark-800/80 border border-slate-700/80 px-3 py-1.5 rounded-xl transition active:scale-95 shadow-sm">
            <span>←</span>
            <span>رجوع للمتجر</span>
          </button>
          <span class="text-xs font-black text-slate-200 truncate max-w-[170px]">{{ activeProduct.nameAr || activeProduct.name }}</span>
          <button @click="showCartDrawer = true" class="relative bg-dark-800/80 border border-slate-700/80 p-2 rounded-xl text-slate-200 hover:text-white transition active:scale-95">
            <span class="text-xs">🛒</span>
            <span v-if="cartTotalCount > 0" class="absolute -top-1 -right-1 bg-rose-600 text-white text-[9px] font-black w-3.5 h-3.5 rounded-full flex items-center justify-center shadow">
              {{ cartTotalCount }}
            </span>
          </button>
        </header>

        <!-- Product Content Body -->
        <div class="p-4 space-y-4 max-w-md mx-auto w-full flex-1">
          <!-- Hero Media (Image or Video) -->
          <div class="w-full h-64 rounded-2xl bg-dark-850 overflow-hidden relative border border-slate-800 shadow-lg">
            <video v-if="isMediaVideo((activeProduct.mediaUrls && activeProduct.mediaUrls[0]) || activeProduct.image_url)" 
                   :src="(activeProduct.mediaUrls && activeProduct.mediaUrls[0]) || activeProduct.image_url" 
                   controls playsinline class="w-full h-full object-cover"></video>
            <img v-else 
                 :src="(activeProduct.mediaUrls && activeProduct.mediaUrls[0]) || activeProduct.image_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&q=80'" 
                 class="w-full h-full object-cover" alt="product"
                 onerror="this.src='https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&q=80'">

            <span v-if="activeProduct.discountPercent > 0" class="absolute top-3 right-3 bg-rose-600 text-white text-xs font-black px-2.5 py-1 rounded-lg shadow-lg">
              خصم {{ activeProduct.discountPercent }}% 🔥
            </span>
          </div>

          <!-- Product Title & Price Header -->
          <div class="bg-dark-850 border border-slate-800 rounded-2xl p-4 space-y-2 shadow-sm">
            <div class="flex items-start justify-between gap-2">
              <h2 class="text-base font-black text-white leading-snug">{{ activeProduct.nameAr || activeProduct.name }}</h2>
              <div class="text-left shrink-0">
                <div v-if="activeProduct.discountPercent > 0" class="text-[11px] text-slate-400 line-through">
                  {{ formatPrice(getOriginalPrice(activeProduct)) }}
                </div>
                <div class="text-lg font-black text-emerald-400 font-mono">
                  {{ formatPrice(getCalculatedTotal()) }}
                </div>
              </div>
            </div>

            <!-- Trust Badges -->
            <div class="flex items-center gap-2 pt-1 flex-wrap">
              <span class="text-[10px] bg-brand-500/10 text-brand-300 border border-brand-500/20 px-2 py-0.5 rounded-md font-semibold">
                {{ activeProduct.category || 'خدمات رقمية' }}
              </span>
              <span class="text-[10px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded-md font-semibold flex items-center gap-1">
                <span>⚡</span> تسليم فوري
              </span>
              <span class="text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/20 px-2 py-0.5 rounded-md font-semibold flex items-center gap-1">
                <span>🛡️</span> ضمان ذهبي 100%
              </span>
            </div>
          </div>

          <!-- Quantity Stepper for regular products -->
          <div v-if="activeProduct.templateType !== 'smm_boost'" class="bg-dark-850 border border-slate-800 rounded-2xl p-3.5 flex items-center justify-between shadow-sm">
            <div>
              <div class="text-xs font-bold text-slate-200">الكمية المطلوبة:</div>
              <div class="text-[10px] text-slate-400">حدد عدد الحبات للطلب</div>
            </div>
            <div class="flex items-center gap-3 bg-dark-900 border border-slate-700/80 rounded-xl p-1">
              <button @click="purchaseQuantity > 1 && purchaseQuantity--" class="w-8 h-8 rounded-lg bg-dark-800 hover:bg-dark-750 text-slate-200 font-bold flex items-center justify-center transition active:scale-95">-</button>
              <span class="w-8 text-center font-bold text-sm text-white font-mono">{{ purchaseQuantity }}</span>
              <button @click="purchaseQuantity++" class="w-8 h-8 rounded-lg bg-dark-800 hover:bg-dark-750 text-slate-200 font-bold flex items-center justify-center transition active:scale-95">+</button>
            </div>
          </div>

          <!-- Pricing Options (Packages) -->
          <div v-if="activeProduct.priceOptions && activeProduct.priceOptions.length" class="bg-dark-850 border border-slate-800 rounded-2xl p-4 space-y-2 shadow-sm">
            <label class="text-xs font-bold text-slate-300">اختر الباقة أو الفئة:</label>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in activeProduct.priceOptions" :key="opt.id"
                      @click="selectedPriceOption = opt"
                      :class="['p-3 rounded-xl border text-xs font-bold transition flex flex-col justify-between items-start',
                              selectedPriceOption?.id === opt.id ? 'border-brand-500 bg-brand-900/30 text-white ring-1 ring-brand-500' : 'border-slate-700 bg-dark-800 text-slate-300']">
                <span>{{ opt.label }}</span>
                <span class="text-emerald-400 font-mono mt-1 text-sm">{{ formatPrice(opt.userPrice || opt.price) }}</span>
              </button>
            </div>
          </div>

          <!-- Description Section -->
          <div class="bg-dark-850 border border-slate-800 rounded-2xl p-4 space-y-1.5 shadow-sm">
            <h4 class="text-xs font-bold text-slate-300">تفاصيل ومميزات الخدمة:</h4>
            <p class="text-xs text-slate-300 leading-relaxed whitespace-pre-line">{{ activeProduct.description || 'خدمة رقمية معتمدة وسريعة التنفيذ مع ضمان كامل.' }}</p>
          </div>

          <!-- SMM Boost Slider -->
          <div v-if="activeProduct.templateType === 'smm_boost'" class="bg-dark-850 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-sm">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-300 font-bold">العدد المطلوب:</span>
              <span class="text-emerald-400 font-mono font-black text-sm">{{ smmQuantity }}</span>
            </div>
            <input type="range" min="100" max="10000" step="100" v-model="smmQuantity" class="w-full accent-brand-500">
            <div class="text-[11px] text-slate-400">رابط الحساب أو المنشور:</div>
            <input type="url" v-model="smmUrl" placeholder="https://..." class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
          </div>

          <!-- Custom Requirements Fields -->
          <div v-if="activeProduct.requirements && activeProduct.requirements.length" class="bg-dark-850 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-sm">
            <div v-for="reqField in activeProduct.requirements" :key="reqField.name" class="space-y-1">
              <label class="text-xs font-bold text-slate-300 flex items-center justify-between">
                <span>{{ reqField.label || reqField.name }} <span v-if="reqField.required" class="text-rose-500">*</span></span>
              </label>
              <input v-model="userFormInputs[reqField.name]" 
                     :type="reqField.type || 'text'" 
                     :placeholder="reqField.placeholder || ''"
                     class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500">
            </div>
          </div>

          <!-- 🎟️ Discount Coupon Input in Product Screen -->
          <div class="bg-dark-850 border border-slate-800 rounded-2xl p-3.5 space-y-2 shadow-sm">
            <label class="text-xs font-bold text-slate-300 flex items-center justify-between">
              <span>كود الخصم (Coupon):</span>
              <span v-if="appliedCoupon" class="text-[10px] text-emerald-400 font-bold">تم الخصم: -{{ formatPrice(appliedCoupon.discount_usd) }} ✅</span>
            </label>
            <div class="flex items-center gap-2">
              <input v-model="enteredCouponCode" type="text" placeholder="أدخل كود الخصم إن وجد..." class="flex-1 bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white uppercase font-mono">
              <button @click="applyCouponCode" class="px-3.5 py-2 bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs rounded-xl shadow active:scale-95 transition">
                تطبيق 🎟️
              </button>
            </div>
          </div>

          <!-- 🎁 Send as a Gift Option -->
          <div class="bg-dark-850 border border-slate-800 rounded-2xl p-3.5 space-y-2.5 shadow-sm">
            <div class="flex items-center justify-between">
              <label class="text-xs font-bold text-slate-200 flex items-center gap-1.5 cursor-pointer">
                <span>🎁</span> إرسال هذا الطلب كهدية لصديق
              </label>
              <input type="checkbox" v-model="isGiftOrder" class="w-4 h-4 rounded text-brand-600 accent-brand-500 cursor-pointer">
            </div>

            <div v-if="isGiftOrder" class="space-y-2 pt-1 border-t border-slate-800">
              <div>
                <label class="block text-[11px] text-slate-300 mb-0.5">اسم أو يوزر المستلم (@username أو الاسم):</label>
                <input v-model="giftRecipient" type="text" placeholder="@friend_username أو اسم الصديق" class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
              </div>
              <div>
                <label class="block text-[11px] text-slate-300 mb-0.5">رسالة الإهداء / التهنئة:</label>
                <input v-model="giftMessage" type="text" placeholder="مثال: ألف مبروك يا غالي! هدية بمناسبة الترقية 🎉" class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
              </div>
              <div>
                <label class="block text-[11px] text-slate-300 mb-0.5">نمط بطاقة الهدية:</label>
                <select v-model="giftTheme" class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                  <option value="party">🎉 احتفال ومناسبات</option>
                  <option value="gold">💎 بطاقة VIP ذهبية فخمة</option>
                  <option value="gaming">🎮 تصميم ألعاب بطولي</option>
                </select>
              </div>
            </div>
          </div>

          <!-- ⭐ Verified Customer Reviews & Ratings Section -->
          <div class="bg-dark-850 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-sm">
            <div class="flex items-center justify-between">
              <h4 class="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <span>⭐</span> تقييمات وآراء المشترين
              </h4>
              <span class="text-xs font-black text-amber-400">4.9 / 5.0 (ممتاز)</span>
            </div>

            <!-- Add Review Mini Form -->
            <div class="bg-dark-900/80 p-3 rounded-xl border border-slate-800 space-y-2">
              <div class="flex items-center justify-between text-xs">
                <span class="text-slate-300">أضف تقييمك:</span>
                <div class="flex items-center gap-1 text-amber-400 cursor-pointer">
                  <span v-for="star in 5" :key="star" @click="reviewFormRating = star" class="text-sm">
                    {{ star <= reviewFormRating ? '★' : '☆' }}
                  </span>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <input v-model="reviewFormComment" type="text" placeholder="اكتب رأيك بالخدمة..." class="flex-1 bg-dark-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                <button @click="submitProductReview" :disabled="submittingReview" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-lg shadow">
                  إرسال ✍️
                </button>
              </div>
            </div>
          </div>

          <!-- Automatic Guarantee Disclaimer (No annoying blocking checkbox!) -->
          <div class="p-3 rounded-xl bg-amber-950/30 border border-amber-500/20 flex items-center gap-2 text-[11px] text-amber-200">
            <span class="text-base">🛡️</span>
            <span>مشمول بالضمان الذهبي والاسترجاع الفوري التلقائي للمحفظة في حال تعذر التنفيذ.</span>
          </div>
        </div>

        <!-- Sticky Bottom Actions Bar -->
        <div class="fixed bottom-0 left-0 right-0 glass-panel border-t border-slate-800 p-3 safe-bottom z-30">
          <div class="max-w-md mx-auto grid grid-cols-2 gap-2.5">
            <!-- Add to Cart -->
            <button @click="addToCart(activeProduct, purchaseQuantity)" 
                    class="bg-dark-800 hover:bg-dark-750 border border-brand-500/40 text-brand-300 font-bold py-3 px-3 rounded-xl transition flex items-center justify-center gap-2 text-xs active:scale-95 shadow">
              <span>🛒</span>
              <span>أضف للسلة</span>
            </button>
            <!-- 1-Tap Instant Buy (Zero Friction!) -->
            <button @click="submitOrder" 
                    :disabled="isSubmitting"
                    class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 text-white font-black py-3 px-3 rounded-xl shadow-lg transition flex items-center justify-center gap-1.5 text-xs active:scale-95">
              <span v-if="isSubmitting">جاري الدفع... ⏳</span>
              <span v-else>⚡ {{ t('instant_buy') }} {{ formatPrice(getCalculatedTotal()) }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- B. SHOPPING CART DRAWER (سلة المشتريات المجمعة) -->
      <div v-if="showCartDrawer" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
        <div class="bg-dark-850 w-full max-w-md rounded-t-3xl sm:rounded-3xl border border-slate-700/80 p-5 space-y-4 max-h-[85vh] flex flex-col">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <div class="flex items-center gap-2">
              <span class="text-lg">🛒</span>
              <h3 class="font-black text-sm text-white">سلة المشتريات</h3>
              <span class="text-[10px] bg-brand-500/20 text-brand-300 px-2 py-0.5 rounded-full font-bold font-mono">{{ cartTotalCount }} عناصر</span>
            </div>
            <button @click="showCartDrawer = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Empty Cart State -->
          <div v-if="!cartItems.length" class="text-center py-12 space-y-3">
            <span class="text-4xl block">🛍️</span>
            <h4 class="font-bold text-sm text-slate-300">سلتك فارغة حالياً</h4>
            <p class="text-xs text-slate-400">تصفح المتجر وأضف منتجاتك المفضلة بضغطة زر واحدة</p>
            <button @click="showCartDrawer = false; currentTab = 'store'" class="mt-2 px-5 py-2 bg-brand-600 rounded-xl text-xs font-bold text-white shadow">
              تصفح المنتجات الآن
            </button>
          </div>

          <!-- Cart Items List -->
          <div v-else class="flex-1 overflow-y-auto space-y-2.5 pr-1 max-h-72">
            <div v-for="(it, idx) in cartItems" :key="idx" class="bg-dark-800/90 border border-slate-700/70 p-3 rounded-2xl flex items-center justify-between gap-2.5 shadow-sm">
              <div class="w-12 h-12 rounded-xl bg-dark-900 overflow-hidden shrink-0 border border-slate-700">
                <img :src="it.image_url || (it.mediaUrls && it.mediaUrls[0]) || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=120&q=80'" class="w-full h-full object-cover">
              </div>
              <div class="flex-1 min-w-0">
                <h4 class="font-bold text-xs text-white truncate">{{ it.nameAr || it.name }}</h4>
                <div class="text-[11px] font-black text-emerald-400 font-mono mt-0.5">{{ formatPrice(it.price * it.quantity) }} <span class="text-[9px] text-slate-400 font-normal">({{ formatPrice(it.price) }}/{{ t('unit') }})</span></div>
              </div>
              <!-- Quantity Stepper -->
              <div class="flex items-center gap-1.5 bg-dark-900 border border-slate-700/60 rounded-xl p-1 shrink-0">
                <button @click="decreaseCartQty(idx)" class="w-6 h-6 rounded-lg bg-dark-800 text-slate-300 text-xs font-bold flex items-center justify-center">-</button>
                <span class="w-5 text-center text-xs font-bold font-mono text-white">{{ it.quantity }}</span>
                <button @click="increaseCartQty(idx)" class="w-6 h-6 rounded-lg bg-dark-800 text-slate-300 text-xs font-bold flex items-center justify-center">+</button>
              </div>
              <!-- Remove Button -->
              <button @click="removeCartItem(idx)" class="text-rose-400 hover:text-rose-300 p-1 text-xs shrink-0">🗑️</button>
            </div>
          </div>

          <!-- Cart Footer Summary & Checkout -->
          <div v-if="cartItems.length" class="border-t border-slate-700/60 pt-3 space-y-3">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-400">إجمالي السلة:</span>
              <span class="text-lg font-black text-emerald-400 font-mono">{{ formatPrice(cartTotalPrice) }}</span>
            </div>
            <div class="flex items-center justify-between text-[11px] text-slate-400">
              <span>رصيد محفظتك:</span>
              <span class="font-bold font-mono text-slate-200">{{ formatPrice(user.balance || 0) }}</span>
            </div>
            <button @click="checkoutCart" :disabled="isCheckingOutCart" class="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 text-white font-black py-3 rounded-xl shadow-lg transition flex items-center justify-center gap-2 text-xs active:scale-95">
              <span v-if="isCheckingOutCart">جاري الشراء... ⏳</span>
              <span v-else>{{ t('checkout_cart') }} ({{ formatPrice(cartTotalPrice) }}) 💳</span>
            </button>
          </div>
        </div>
      </div>

      <!-- C. DEPOSIT / TOP-UP MODAL (Telegram Stars 1-Tap & Gateways) -->
      <div v-if="showDepositModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
        <div class="bg-dark-850 w-full max-w-md rounded-t-3xl sm:rounded-3xl border border-slate-700/80 p-5 space-y-4 max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <div class="flex items-center gap-2">
              <span class="text-lg">💰</span>
              <h3 class="font-black text-sm text-white">شحن رصيد المحفظة</h3>
            </div>
            <button @click="showDepositModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Deposit Method Tabs Switcher -->
          <div class="grid grid-cols-2 gap-2 p-1 bg-dark-900 border border-slate-700 rounded-xl">
            <button @click="activeDepositTab = 'manual'" :class="['py-2 text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5', activeDepositTab === 'manual' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white']">
              <span>💵</span>
              <span>دفع يدوي / حوالة</span>
            </button>
            <button @click="activeDepositTab = 'stars'" :class="['py-2 text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5', activeDepositTab === 'stars' ? 'bg-amber-600 text-white shadow' : 'text-slate-400 hover:text-white']">
              <span>⭐️</span>
              <span>نجوم تيليجرام</span>
            </button>
          </div>

          <!-- TAB A: Manual Payment Gateway (زين كاش، آسيا سيل، USDT...) -->
          <div v-if="activeDepositTab === 'manual'" class="space-y-3 bg-dark-800/90 border border-slate-700/80 p-3.5 rounded-2xl">
            <div class="space-y-1">
              <label class="text-xs font-bold text-slate-200">اختر طريقة التحويل:</label>
              <div class="grid grid-cols-1 gap-2">
                <div v-for="m in (manualPaymentMethods || [])" :key="m.id"
                     @click="selectedPaymentMethod = m"
                     :class="['p-3 rounded-xl border text-xs cursor-pointer transition flex items-center justify-between',
                             selectedPaymentMethod?.id === m.id ? 'bg-emerald-950/50 border-emerald-500 text-white ring-1 ring-emerald-500' : 'bg-dark-900 border-slate-800 text-slate-300 hover:border-slate-700']">
                  <div class="flex items-center gap-2">
                    <span class="text-lg">{{ m.icon || '💳' }}</span>
                    <div>
                      <div class="font-bold text-white">{{ m.name }}</div>
                      <div class="text-[10px] text-slate-400 font-mono">{{ m.account }}</div>
                    </div>
                  </div>
                  <button @click.stop="copyToClipboard(m.account)" class="text-[10px] bg-dark-800 hover:bg-dark-750 border border-slate-700 px-2 py-1 rounded-lg text-emerald-300 font-bold">
                    نسخ الرقم 📋
                  </button>
                </div>
              </div>
            </div>

            <!-- Method Instructions -->
            <div v-if="selectedPaymentMethod?.instructions" class="p-2.5 rounded-xl bg-dark-900/90 border border-slate-800 text-[11px] text-slate-300 leading-relaxed">
              <span class="font-bold text-emerald-400">تعليمات التحويل: </span>{{ selectedPaymentMethod.instructions }}
            </div>

            <!-- Receipt Submission Form -->
            <div class="space-y-2 pt-1 border-t border-slate-800">
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="text-[10px] font-bold text-slate-300">المبلغ المحول ($):</label>
                  <input v-model.number="manualDepositAmount" type="number" step="0.5" placeholder="5.0" class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono">
                </div>
                <div>
                  <label class="text-[10px] font-bold text-slate-300">رقم الهاتف أو المعاملة:</label>
                  <input v-model="manualSenderRef" type="text" placeholder="0780xxxx أو رقم الإشعار" class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                </div>
              </div>

              <div>
                <label class="text-[10px] font-bold text-slate-300">رابط صورة الإشعار (اختياري):</label>
                <input v-model="manualReceiptUrl" type="text" placeholder="https://..." class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
              </div>

              <button @click="submitManualDeposit" :disabled="submittingManualReceipt || !manualSenderRef" class="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-black text-xs py-2.5 rounded-xl shadow transition">
                <span v-if="submittingManualReceipt">جاري إرسال الإشعار... ⏳</span>
                <span v-else>إرسال إشعار الدفع لتأكيد الشحن 📤</span>
              </button>
            </div>
          </div>

          <!-- TAB B: Telegram Stars (Direct 1-tap in-app) -->
          <div v-if="activeDepositTab === 'stars'" class="space-y-2 bg-gradient-to-br from-amber-950/40 via-dark-800 to-amber-950/20 border border-amber-500/30 p-3.5 rounded-2xl">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-xl">⭐️</span>
                <div>
                  <h4 class="font-bold text-xs text-amber-300">شحن نجوم تيليجرام (Telegram Stars)</h4>
                  <p class="text-[10px] text-slate-400">دفع فوري وآمن بنقرة واحدة داخل تيليجرام</p>
                </div>
              </div>
              <span class="text-[10px] bg-amber-500/20 text-amber-300 font-bold px-2 py-0.5 rounded-full border border-amber-500/30">فوري ⚡</span>
            </div>

            <!-- Stars Package Buttons -->
            <div class="grid grid-cols-2 gap-2 pt-1.5">
              <button @click="payWithStarsAmount(50)" :disabled="depositingStars" class="p-2.5 rounded-xl bg-dark-900/90 hover:bg-dark-750 border border-amber-500/40 text-center transition active:scale-95 flex items-center justify-between">
                <span class="font-black text-xs text-amber-300">50 ⭐</span>
                <span class="text-[11px] font-bold text-slate-300">+$1.00</span>
              </button>
              <button @click="payWithStarsAmount(100)" :disabled="depositingStars" class="p-2.5 rounded-xl bg-dark-900/90 hover:bg-dark-750 border border-amber-500/40 text-center transition active:scale-95 flex items-center justify-between">
                <span class="font-black text-xs text-amber-300">100 ⭐</span>
                <span class="text-[11px] font-bold text-slate-300">+$2.00</span>
              </button>
              <button @click="payWithStarsAmount(250)" :disabled="depositingStars" class="p-2.5 rounded-xl bg-dark-900/90 hover:bg-dark-750 border border-amber-500/40 text-center transition active:scale-95 flex items-center justify-between">
                <span class="font-black text-xs text-amber-300">250 ⭐</span>
                <span class="text-[11px] font-bold text-slate-300">+$5.00</span>
              </button>
              <button @click="payWithStarsAmount(500)" :disabled="depositingStars" class="p-2.5 rounded-xl bg-dark-900/90 hover:bg-dark-750 border border-amber-500/40 text-center transition active:scale-95 flex items-center justify-between">
                <span class="font-black text-xs text-amber-300">500 ⭐</span>
                <span class="text-[11px] font-bold text-slate-300">+$10.00</span>
              </button>
            </div>

            <!-- Custom Stars Input -->
            <div class="flex items-center gap-2 pt-1">
              <input type="number" min="10" max="50000" v-model.number="customStarsAmount" placeholder="كمية نجوم أخرى..." class="flex-1 bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
              <button @click="payWithStarsAmount(customStarsAmount)" :disabled="depositingStars || !customStarsAmount" class="px-3 py-2 bg-amber-500 hover:bg-amber-400 text-slate-900 font-black text-xs rounded-xl shadow active:scale-95 transition">
                شحن ⭐
              </button>
            </div>
            <div v-if="depositingStars" class="text-center text-xs text-amber-400 font-bold py-1">
              جاري تجهيز الفاتورة... ⏳
            </div>
          </div>

          <!-- Section 2: External Gateways -->
          <div class="space-y-2">
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

          <!-- Margin selector (Direct Numeric Input as requested by user) -->
          <div class="bg-dark-800 p-3 rounded-xl border border-slate-700 space-y-2">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-300 font-bold">نسبة هامش الربح المضافة (%):</span>
              <div class="flex items-center gap-1.5">
                <input type="number" min="0" max="500" step="1" v-model.number="importMarginPercent" class="w-20 bg-dark-900 border border-slate-600 rounded-lg px-2 py-1 text-xs text-emerald-400 font-mono font-black text-center focus:border-emerald-500 focus:outline-none">
                <span class="text-emerald-400 font-mono font-black">%</span>
              </div>
            </div>
            <div class="text-[10px] text-slate-400">أدخل النسبة كرقم مباشر (مثال: 15 أو 25 أو 50)، ويتم احتساب أسعار بيع المنتجات تلقائياً بناءً على سعر التكلفة مضافاً إليه نسبة الربح.</div>
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
                    <div class="text-[10px] text-slate-400">التكلفة: {{ formatPrice(item.price_options?.[0]?.costPrice || 0) }} | مقترح: {{ formatPrice(((item.price_options?.[0]?.costPrice || 0) * (1 + importMarginPercent/100))) }}</div>
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

      <!-- E. ADD / EDIT PRODUCT MODAL (SELLER) -->
      <div v-if="showProductModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-lg rounded-3xl border border-slate-700/80 p-5 space-y-4 my-auto max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <h3 class="font-black text-sm text-white flex items-center gap-2">
              <span>{{ editingProduct.is_master ? '👑' : '➕' }}</span>
              <span>{{ editingProduct.is_master ? 'تخصيص منتج مركزي لمتجرك' : 'إضافة / تعديل منتج خاص بالمتجر' }}</span>
            </h3>
            <button @click="showProductModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Master product notice for seller -->
          <div v-if="editingProduct.is_master" class="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300 space-y-1">
            <div class="font-bold flex items-center gap-1.5">
              <span>🔒</span> متطلبات هذا المنتج مقفلة من الآدمن
            </div>
            <p class="text-slate-300">سعر التكلفة والمتطلبات محددة مركزياً من إدارة المنصة لحماية تنفيذ الطلبات. يمكنك فقط تعديل سعر البيع، الوصف، وصورة المنتج لمتجرك.</p>
          </div>

          <div class="space-y-3">
            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">اسم المنتج بالعربية:</label>
              <input type="text" v-model="editingProduct.nameAr" :disabled="editingProduct.is_master" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white disabled:opacity-70 disabled:cursor-not-allowed">
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">اسم المنتج بالإنجليزية:</label>
              <input type="text" v-model="editingProduct.name" :disabled="editingProduct.is_master" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white disabled:opacity-70 disabled:cursor-not-allowed">
            </div>

            <div v-if="!editingProduct.is_master" class="grid grid-cols-2 gap-3">
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
                <label class="block text-xs font-bold text-slate-300 mb-1">
                  {{ editingProduct.is_master ? 'سعر جملة الآدمن ($):' : 'سعر التكلفة ($):' }}
                </label>
                <input type="number" step="0.01" v-model.number="editingProduct.costPrice" :disabled="editingProduct.is_master" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono disabled:opacity-60 disabled:cursor-not-allowed">
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">سعر البيع لزبائنك ($):</label>
                <input type="number" step="0.01" v-model.number="editingProduct.userPrice" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-emerald-400 font-mono font-bold focus:border-brand-500">
              </div>
            </div>

            <!-- Dynamic Live Profit Display -->
            <div class="bg-dark-900 border border-slate-800 p-2.5 rounded-xl flex items-center justify-between text-xs font-mono">
              <span class="text-slate-400">صافي ربحك المحسوب:</span>
              <span class="font-bold text-emerald-400">
                +{{ formatPrice(editingProduct.userPrice - editingProduct.costPrice) }}
                <span class="text-[10px] text-slate-400 font-normal mr-1">
                  ({{ editingProduct.costPrice > 0 ? Math.round(((editingProduct.userPrice - editingProduct.costPrice) / editingProduct.costPrice) * 100) : 0 }}%)
                </span>
              </span>
            </div>

            <!-- Floor Price Security Alert -->
            <div v-if="editingProduct.userPrice < editingProduct.costPrice" class="p-2.5 rounded-xl bg-rose-950/70 border border-rose-500/50 text-[11px] text-rose-300">
              ⚠️ تنبيه أمني: سعر البيع لا يمكن أن يكون أقل من سعر التكلفة لحماية أرباحك.
            </div>

            <!-- Native Gallery / Media File Upload -->
            <div class="space-y-2 bg-dark-800/80 p-3 rounded-xl border border-slate-700">
              <div class="flex items-center justify-between">
                <label class="block text-xs font-bold text-slate-200">صورة المنتج:</label>
                <span v-if="uploadingMedia" class="text-[10px] text-brand-400 font-bold animate-pulse">جاري الرفع... ⏳</span>
              </div>

              <!-- Media Preview if available -->
              <div v-if="editingProduct.imageUrl" class="relative w-full h-32 rounded-xl bg-dark-900 overflow-hidden border border-slate-700">
                <img :src="editingProduct.imageUrl" class="w-full h-full object-cover" alt="preview">
                <button type="button" @click="editingProduct.imageUrl = ''" class="absolute top-2 left-2 bg-rose-600/80 hover:bg-rose-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shadow">✕</button>
              </div>

              <!-- Native Gallery / File Picker -->
              <input type="file" ref="productMediaFileInput" accept="image/*" @change="handleProductMediaUpload" class="hidden">
              <button type="button" @click="$refs.productMediaFileInput.click()" :disabled="uploadingMedia" class="w-full py-2.5 px-3 bg-brand-600/20 hover:bg-brand-600/30 border border-brand-500/40 rounded-xl text-xs font-bold text-brand-300 flex items-center justify-center gap-2 transition active:scale-95 shadow-sm">
                <span>📸</span>
                <span>اختيار صورة من معرض الهاتف (Phone Gallery)</span>
              </button>

              <!-- Optional URL input -->
              <div class="flex items-center gap-1.5 pt-1">
                <span class="text-[10px] text-slate-400">أو رابط مباشر:</span>
                <input type="text" v-model="editingProduct.imageUrl" placeholder="https://..." class="flex-1 bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-white">
              </div>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">وصف المنتج:</label>
              <textarea v-model="editingProduct.description" rows="2" placeholder="أدخل تفاصيل ومميزات المنتج..." class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"></textarea>
            </div>

            <!-- Master product requirements: Locked preview -->
            <div v-if="editingProduct.is_master" class="space-y-1.5 bg-dark-900/60 p-3 rounded-xl border border-slate-800">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-slate-300">المتطلبات الإلزامية من المشتري:</span>
                <span class="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full font-bold">🔒 مقفلة من الآدمن</span>
              </div>
              <div v-if="editingProduct.requirements && editingProduct.requirements.length" class="flex items-center gap-1.5 flex-wrap pt-1">
                <span v-for="r in editingProduct.requirements" :key="r.name" class="text-[10px] bg-dark-800 text-slate-300 border border-slate-700 px-2.5 py-1 rounded-lg font-mono">
                  🔒 {{ r.label || r.name }}
                </span>
              </div>
              <div v-else class="text-[10px] text-slate-400">
                هذا المنتج لا يتطلب مدخلات إضافية من المشتري عند الشراء.
              </div>
            </div>

            <!-- Custom Requirements Builder for custom products only -->
            <div v-else class="space-y-2 bg-dark-800/80 p-3 rounded-xl border border-slate-700">
              <div class="flex items-center justify-between">
                <label class="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <span>📝</span> طلب بيانات من العميل عند الشراء (Player ID / Email / إلخ):
                </label>
                <input type="checkbox" v-model="editingProduct.inputRequired" class="w-4 h-4 rounded text-brand-600 accent-brand-500 cursor-pointer">
              </div>
              <div v-if="editingProduct.inputRequired" class="space-y-2 pt-1">
                <div>
                  <label class="block text-[11px] text-slate-300 mb-0.5">عنوان الحقل المطلوب للمشتري:</label>
                  <input type="text" v-model="editingProduct.inputLabel" placeholder="مثال: آيدي الحساب (Player ID) أو البريد الإلكتروني" class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                </div>
                <div>
                  <label class="block text-[11px] text-slate-300 mb-0.5">نوع الحقل:</label>
                  <select v-model="editingProduct.inputType" class="w-full bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                    <option value="text">نص أو آيدي (Text / ID)</option>
                    <option value="number">أرقام فقط (Number)</option>
                    <option value="email">بريد إلكتروني (Email)</option>
                    <option value="url">رابط حساب أو منشور (Link / URL)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <button @click="saveSellerProduct" :disabled="savingProduct || editingProduct.userPrice < editingProduct.costPrice" class="w-full bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-black text-xs py-3 rounded-xl transition shadow flex items-center justify-center gap-1.5">
            <span v-if="savingProduct">جاري الحفظ... ⏳</span>
            <span v-else>حفظ وإضافة المنتج للمتجر ✅</span>
          </button>
        </div>
      </div>

      <!-- F. SUPER ADMIN MASTER PRODUCT MODAL (آدمن المنصة الأعلى) -->
      <div v-if="showAdminProductModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-lg rounded-3xl border border-rose-500/40 p-5 space-y-4 my-auto max-h-[90vh] overflow-y-auto shadow-2xl">
          <div class="flex items-center justify-between border-b border-rose-900/40 pb-3">
            <h3 class="font-black text-sm text-white flex items-center gap-2">
              <span>👑</span> {{ adminProductForm.id ? 'تعديل منتج مركزي (الكتالوج العام)' : 'إضافة منتج مركزي جديد (الكتالوج العام)' }}
            </h3>
            <button @click="showAdminProductModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <div class="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-[11px] text-rose-300">
            ℹ️ أي تعديل على هذا المنتج سينزل تلقائياً على القوالب الأربعة ولجميع البائعين. وإذا رفعت التكلفة يرتفع السعر تلقائياً عند الجميع بنفس الفرق لضمان أرباحهم.
          </div>

          <div class="space-y-3">
            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">اسم المنتج بالعربية (يظهر للجميع):</label>
              <input type="text" v-model="adminProductForm.name_ar" placeholder="مثال: شحن شدات ببجي 660 UC" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">اسم المنتج بالإنجليزية:</label>
              <input type="text" v-model="adminProductForm.name" placeholder="PUBG Mobile 660 UC" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">القسم (Category):</label>
                <select v-model="adminProductForm.category" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                  <option value="gaming">ألعاب (Gaming)</option>
                  <option value="subscriptions">اشتراكات (Subscriptions)</option>
                  <option value="telegram">تيليجرام (Telegram)</option>
                  <option value="numbers">أرقام تفعيل (Numbers)</option>
                  <option value="smm">تفاعل ودعم (SMM)</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">نوع القالب المتصل:</label>
                <select v-model="adminProductForm.template_type" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                  <option value="manual_subs">اشتراكات وشحن ألعاب</option>
                  <option value="stars_premium_gifts">نجوم وبريميوم وهدايا</option>
                  <option value="virtual_numbers">أرقام تفعيل</option>
                  <option value="smm_boost">زيادة تفاعل ودعم</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">سعر التكلفة عليك ($):</label>
                <input type="number" step="0.01" v-model.number="adminProductForm.cost_price" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono">
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">سعر البيع المقترح للبدء ($):</label>
                <input type="number" step="0.01" v-model.number="adminProductForm.base_user_price" class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono">
              </div>
            </div>

            <!-- Profit preview -->
            <div class="bg-dark-900 p-2.5 rounded-xl border border-slate-800 flex items-center justify-between text-xs font-mono">
              <span class="text-slate-400">هامش الربح الافتراضي:</span>
              <span class="text-emerald-400 font-bold">+{{ formatPrice(adminProductForm.base_user_price - adminProductForm.cost_price) }}</span>
            </div>

            <!-- Direct Phone Gallery Upload for Admin -->
            <div class="space-y-2 bg-dark-800/80 p-3 rounded-xl border border-slate-700">
              <div class="flex items-center justify-between">
                <label class="block text-xs font-bold text-slate-200">صورة المنتج (من المعرض المباشر):</label>
                <span v-if="uploadingAdminMedia" class="text-[10px] text-rose-400 font-bold animate-pulse">جاري الرفع... ⏳</span>
              </div>

              <!-- Media Preview -->
              <div v-if="adminProductForm.image_url" class="relative w-full h-32 rounded-xl bg-dark-900 overflow-hidden border border-slate-700">
                <img :src="adminProductForm.image_url" class="w-full h-full object-cover" alt="preview">
                <button type="button" @click="adminProductForm.image_url = ''" class="absolute top-2 left-2 bg-rose-600/80 hover:bg-rose-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shadow">✕</button>
              </div>

              <!-- Native Gallery / File Picker -->
              <input type="file" ref="adminMediaFileInput" accept="image/*" @change="uploadAdminImage" class="hidden">
              <button type="button" @click="$refs.adminMediaFileInput.click()" :disabled="uploadingAdminMedia" class="w-full py-2.5 px-3 bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/40 rounded-xl text-xs font-bold text-rose-300 flex items-center justify-center gap-2 transition active:scale-95 shadow-sm">
                <span>📸</span>
                <span>اختيار صورة من معرض الهاتف (Phone Gallery)</span>
              </button>

              <div class="flex items-center gap-1.5 pt-1">
                <span class="text-[10px] text-slate-400">أو رابط مباشر:</span>
                <input type="text" v-model="adminProductForm.image_url" placeholder="https://..." class="flex-1 bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-white">
              </div>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 mb-1">وصف المنتج:</label>
              <textarea v-model="adminProductForm.description" rows="2" placeholder="أدخل تفاصيل ومميزات المنتج..." class="w-full bg-dark-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"></textarea>
            </div>

            <!-- Requirements Builder (Locked to Admin Only) -->
            <div class="space-y-2.5 bg-dark-800/80 p-3 rounded-xl border border-slate-700">
              <div>
                <label class="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <span>🔒</span> المتطلبات الإلزامية من المشتري (مقفلة لك كآدمن فقط):
                </label>
                <p class="text-[10px] text-slate-400 mt-0.5">البيانات التي سيطلبها المتجر من العميل عند الشراء (لا يمكن للبائعين تعديلها)</p>
              </div>

              <!-- Quick Presets (All requested variants: Email+Password, User+Pass, Pass, ID, Phone, URL, etc.) -->
              <div class="flex items-center gap-1.5 flex-wrap">
                <button type="button" @click="addAdminRequirementPreset('email_password')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-amber-300 border border-amber-500/40 rounded-lg text-[10px] font-bold">
                  + الإيميل + كلمة السر 🔑
                </button>
                <button type="button" @click="addAdminRequirementPreset('username_password')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-amber-300 border border-amber-500/40 rounded-lg text-[10px] font-bold">
                  + اليوزر + كلمة السر 👤🔑
                </button>
                <button type="button" @click="addAdminRequirementPreset('password')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold">
                  + كلمة السر 🔒
                </button>
                <button type="button" @click="addAdminRequirementPreset('player_id')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold">
                  + آيدي اللاعب (Player ID) 🎮
                </button>
                <button type="button" @click="addAdminRequirementPreset('phone')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold">
                  + رقم الهاتف 📱
                </button>
                <button type="button" @click="addAdminRequirementPreset('url')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold">
                  + رابط الحساب/المنشور 🔗
                </button>
                <button type="button" @click="addAdminRequirementPreset('email')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold">
                  + البريد الإلكتروني 📧
                </button>
                <button type="button" @click="addAdminRequirementPreset('username')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold">
                  + اسم المستخدم @
                </button>
                <button type="button" @click="addAdminRequirementPreset('notes')" class="px-2 py-1 bg-dark-900 hover:bg-dark-750 text-slate-300 border border-slate-700 rounded-lg text-[10px] font-bold">
                  + ملاحظات العميل 📝
                </button>
              </div>

              <!-- Current Defined Requirements List -->
              <div v-if="adminProductForm.requirements && adminProductForm.requirements.length" class="space-y-1.5 pt-1">
                <div v-for="(req, rIdx) in adminProductForm.requirements" :key="req.name" class="flex items-center justify-between p-2 rounded-lg bg-dark-900 border border-slate-800 text-xs">
                  <div class="flex items-center gap-2">
                    <span class="text-amber-400 font-bold font-mono">🔒 {{ req.label }}</span>
                    <span class="text-[10px] text-slate-400">({{ req.type }})</span>
                  </div>
                  <button type="button" @click="removeAdminRequirement(rIdx)" class="text-rose-400 hover:text-rose-300 px-1.5 py-0.5 rounded text-xs">✕</button>
                </div>
              </div>
              <div v-else class="text-[10px] text-slate-500 py-1">
                لا توجد متطلبات مضافة حالياً. اختر من القوالب أعلاه لإلزام المشتري بإدخالها عند الطلب.
              </div>
            </div>
          </div>

          <button @click="saveAdminProduct" :disabled="savingAdminProduct || adminProductForm.base_user_price < adminProductForm.cost_price" class="w-full bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-black text-xs py-3 rounded-xl transition shadow flex items-center justify-center gap-1.5">
            <span v-if="savingAdminProduct">جاري الحفظ والنشر... ⏳</span>
            <span v-else>حفظ ونشر للمنصة ولكافة المتاجر 🚀</span>
          </button>
        </div>
      </div>

      <!-- F.1 ADMIN ORDER DELIVERY MODAL (نافذة تسليم الطلب وإرسال البيانات للعميل في تيليجرام) -->
      <div v-if="showDeliveryModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-md rounded-3xl border border-emerald-500/40 p-5 space-y-4 my-auto shadow-2xl">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <div class="flex items-center gap-2">
              <span class="text-xl">🚀</span>
              <div>
                <h3 class="font-black text-xs text-white">تسليم الطلب وإشعار المشتري في تيليجرام</h3>
                <span class="text-[10px] text-emerald-400 font-mono">#{{ deliveryTargetOrder?.order_ref || deliveryTargetOrder?.order_id }}</span>
              </div>
            </div>
            <button @click="showDeliveryModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Order Summary Badge -->
          <div class="bg-dark-900 p-2.5 rounded-xl border border-slate-800 text-xs space-y-1">
            <div class="font-bold text-white flex items-center justify-between">
              <span>{{ deliveryTargetOrder?.service_name || deliveryTargetOrder?.product_name }}</span>
              <span class="text-emerald-400 font-mono">{{ formatPrice(deliveryTargetOrder?.seller_price_usd || deliveryTargetOrder?.price_user_usd || 0) }}</span>
            </div>
            <div class="text-[10px] text-slate-400">
              المشتري: <strong class="text-sky-300">@{{ deliveryTargetOrder?.buyer_username || deliveryTargetOrder?.user_id }}</strong>
            </div>
          </div>

          <div class="space-y-3">
            <div>
              <label class="block text-xs font-bold text-slate-200 mb-1">
                بيانات التسليم (الكود / الحساب / التفعيل):
              </label>
              <textarea v-model="deliveryForm.text" rows="4" placeholder="أدخل كود البطاقة، أو بيانات الحساب المسلم، أو رابط التفعيل هنا..." class="w-full bg-dark-900 border border-slate-700 rounded-xl p-3 text-xs text-emerald-300 font-mono leading-relaxed focus:border-emerald-500 focus:outline-none"></textarea>
              <span class="text-[10px] text-slate-400 block mt-0.5">سيتم إرسال هذا النص فورياً في رسالة خاصة للمشتري داخل محادثة تيليجرام!</span>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-200 mb-1">
                رابط إثبات التسليم (اختياري):
              </label>
              <input v-model="deliveryForm.proof" type="text" placeholder="https://... رابط صورة تأكيد الشحن أو لقطة الشاشة" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
            </div>
          </div>

          <button @click="submitDeliveryFulfillment" :disabled="deliveringOrder || !deliveryForm.text.trim()" class="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 text-white font-black text-xs py-3 rounded-xl transition shadow flex items-center justify-center gap-2">
            <span v-if="deliveringOrder">جاري التسليم وإرسال الإشعار... ⏳</span>
            <span v-else>🚀 تأكيد التسليم وإرسال الرسالة للمشتري الآن</span>
          </button>
        </div>
      </div>

      <!-- F.2 ADMIN ORDER REJECTION MODAL (نافذة إلغاء ورفض الطلب) -->
      <div v-if="showRejectModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-md rounded-3xl border border-rose-500/40 p-5 space-y-4 my-auto shadow-2xl">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <div class="flex items-center gap-2">
              <span class="text-xl">❌</span>
              <div>
                <h3 class="font-black text-xs text-white">إلغاء ورفض الطلب وإشعار المشتري</h3>
                <span class="text-[10px] text-rose-400 font-mono">#{{ rejectTargetOrder?.order_ref || rejectTargetOrder?.order_id }}</span>
              </div>
            </div>
            <button @click="showRejectModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-200 mb-1">سبب الإلغاء والرفض:</label>
            <textarea v-model="rejectReason" rows="3" placeholder="مثال: بيانات الحساب المدخلة غير صحيحة، يرجى إعادة الطلب مع التأكد من كلمة المرور..." class="w-full bg-dark-900 border border-slate-700 rounded-xl p-3 text-xs text-white leading-relaxed focus:border-rose-500 focus:outline-none"></textarea>
            <span class="text-[10px] text-slate-400 block mt-0.5">سيتم إرسال هذا السبب للعميل في تيليجرام.</span>
          </div>

          <div class="flex items-center gap-2">
            <button @click="submitOrderRejection" :disabled="rejectingOrder || !rejectReason.trim()" class="flex-1 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-black text-xs py-3 rounded-xl transition shadow flex items-center justify-center gap-1.5">
              <span v-if="rejectingOrder">جاري المعالجة... ⏳</span>
              <span v-else>تأكيد الرفض والإلغاء ❌</span>
            </button>
            <button @click="handleAdminOrderAction(rejectTargetOrder?.order_ref || rejectTargetOrder?.order_id, 'refund_both')" class="flex-1 bg-purple-600 hover:bg-purple-500 text-white font-black text-xs py-3 rounded-xl transition shadow flex items-center justify-center gap-1.5">
              <span>🔄</span>
              <span>استرجاع الرصيد وإلغاء</span>
            </button>
          </div>
        </div>
      </div>

      <!-- G. FORTUNE WHEEL INTERACTIVE MODAL (عجلة الحظ التفاعلية) -->
      <div v-if="showWheelModal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-dark-850 w-full max-w-sm rounded-3xl border border-purple-500/40 p-5 space-y-4 text-center my-auto shadow-2xl relative">
          <button @click="showWheelModal = false" class="absolute top-4 left-4 w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>

          <div class="pt-2">
            <span class="text-3xl block mb-1">🎡</span>
            <h3 class="font-black text-base text-white">عجلة الحظ اليومية</h3>
            <p class="text-[11px] text-purple-200">دوّر العجلة واربح رصيداً فورياً أو كود خصم لمتجرك!</p>
          </div>

          <!-- Animated Wheel Graphic -->
          <div class="relative w-64 h-64 mx-auto flex items-center justify-center">
            <!-- Center Pointer -->
            <div class="absolute -top-1 z-20 text-rose-500 text-2xl font-black drop-shadow-md">▼</div>

            <!-- Spinning Disc -->
            <div class="w-56 h-56 rounded-full border-4 border-amber-400 shadow-2xl overflow-hidden relative transition-all duration-[3500ms] ease-out"
                 :style="{ transform: `rotate(${wheelRotation}deg)` }">
              <svg viewBox="0 0 100 100" class="w-full h-full">
                <!-- 6 Wheel Slices with distinct vibrant colors -->
                <path d="M 50 50 L 50 0 A 50 50 0 0 1 93.3 25 Z" fill="#3b82f6" />
                <path d="M 50 50 L 93.3 25 A 50 50 0 0 1 93.3 75 Z" fill="#10b981" />
                <path d="M 50 50 L 93.3 75 A 50 50 0 0 1 50 100 Z" fill="#64748b" />
                <path d="M 50 50 L 50 100 A 50 50 0 0 1 6.7 75 Z" fill="#f59e0b" />
                <path d="M 50 50 L 6.7 75 A 50 50 0 0 1 6.7 25 Z" fill="#8b5cf6" />
                <path d="M 50 50 L 6.7 25 A 50 50 0 0 1 50 0 Z" fill="#ec4899" />
              </svg>
              <!-- Center Hub -->
              <div class="absolute inset-0 m-auto w-10 h-10 rounded-full bg-slate-900 border-2 border-white flex items-center justify-center text-xs font-black text-amber-300 shadow">
                🎁
              </div>
            </div>
          </div>

          <!-- Spin Result Alert -->
          <div v-if="wheelResult" class="p-3 rounded-2xl bg-gradient-to-r from-purple-950 to-pink-950 border border-purple-500/50 text-xs text-white font-bold animate-bounce">
            {{ wheelResult.message }}
            <div v-if="wheelResult.coupon_code" class="mt-1 font-mono text-amber-300 text-sm">
              الكود: {{ wheelResult.coupon_code }}
            </div>
          </div>

          <button @click="spinFortuneWheel" :disabled="spinningWheel" class="w-full py-3 bg-gradient-to-r from-purple-600 via-pink-600 to-amber-500 hover:opacity-90 disabled:opacity-50 text-white font-black text-xs rounded-xl shadow-lg transition active:scale-95">
            <span v-if="spinningWheel">جاري التدوير... 🎲</span>
            <span v-else>تدوير العجلة الآن 🚀 (مجاني)</span>
          </button>
        </div>
      </div>

      <!-- H. DIGITAL GIFT CARD MODAL (كرت الهدية الرقمي الأنيق) -->
      <div v-if="showGiftCardModal && activeGiftOrder" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 overflow-y-auto">
        <div class="bg-gradient-to-br from-purple-900 via-dark-850 to-indigo-950 w-full max-w-sm rounded-3xl border border-amber-400/60 p-6 space-y-4 text-center my-auto shadow-2xl relative">
          <button @click="showGiftCardModal = false" class="absolute top-4 left-4 w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>

          <span class="text-4xl block">🎁</span>
          <h3 class="font-black text-lg text-amber-300">بطاقة هدية رقمية خاصة!</h3>
          <p class="text-xs text-slate-300">مُقدمة بكل محبة إلى: <span class="font-bold text-white">{{ activeGiftOrder.details?.gift_recipient || 'الصديق العزيز' }}</span></p>

          <!-- Congratulation Note -->
          <div class="bg-dark-900/80 border border-purple-500/40 p-3 rounded-2xl text-xs text-purple-200 italic">
            "{{ activeGiftOrder.details?.gift_message || 'ألف مبروك الهدية! نتمنى لك أوقاتاً ممتعة 🎉' }}"
          </div>

          <!-- Gift Delivery Code -->
          <div v-if="activeGiftOrder.delivery_data || activeGiftOrder.details?.voucher" class="bg-emerald-950/60 border border-emerald-500/50 p-3 rounded-2xl space-y-1">
            <span class="text-[10px] text-emerald-300 font-bold block">كود / بيانات استلام الهدية:</span>
            <div class="font-mono text-sm font-black text-white select-all">
              {{ activeGiftOrder.delivery_data || activeGiftOrder.details?.voucher }}
            </div>
            <button @click="copyToClipboard(activeGiftOrder.delivery_data || activeGiftOrder.details?.voucher)" class="text-[10px] bg-emerald-700/60 text-white font-bold px-3 py-1 rounded-lg mt-1">
              نسخ الكود 📋
            </button>
          </div>

          <button @click="copyToClipboard(activeGiftOrder.delivery_data || activeGiftOrder.details?.voucher)" class="w-full py-2.5 bg-gradient-to-r from-amber-500 to-orange-500 text-slate-900 font-black text-xs rounded-xl shadow transition active:scale-95">
            مشاركة كرت الهدية مع الصديق 🚀
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
                  <span class="text-slate-400 font-mono">تكلفة: {{ formatPrice(it.costPrice) }} | بيع: {{ formatPrice(it.userPrice) }}</span>
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

      <!-- MODAL: GOLDEN GUARANTEE & TERMS -->
      <div v-if="showGuaranteeModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
        <div class="bg-dark-850 w-full max-w-md rounded-3xl border border-slate-700/80 p-5 space-y-4 max-h-[85vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
            <div class="flex items-center gap-2">
              <span class="text-xl">🛡️</span>
              <h3 class="font-black text-sm text-white">{{ t('golden_guarantee_title') }}</h3>
            </div>
            <button @click="showGuaranteeModal = false" class="w-8 h-8 rounded-full bg-dark-750 text-slate-300 flex items-center justify-center text-xs">✕</button>
          </div>

          <!-- Refund Policy -->
          <div class="bg-dark-900/80 border border-amber-500/20 rounded-xl p-3 text-xs text-amber-200 leading-relaxed space-y-1.5">
            <div class="font-bold text-amber-300 flex items-center gap-1.5">
              <span>✅</span> {{ t('refund_policy') }}:
            </div>
            <p class="text-[11px] text-slate-300">
              {{ store.policyText || 'في حال تعذر تنفيذ أي طلب أو حدوث أي خطأ تقني، يحق للمشتري استرجاع كامل المبلغ تلقائياً وفورياً إلى رصيد محفظته بالبوت دون أي خصومات.' }}
            </p>
          </div>

          <!-- Terms -->
          <div class="bg-dark-900/80 border border-slate-700 rounded-xl p-3 text-xs text-slate-300 leading-relaxed space-y-1.5">
            <div class="font-bold text-slate-200 flex items-center gap-1.5">
              <span>📜</span> {{ t('terms_of_service') }}:
            </div>
            <p class="text-[11px] text-slate-400">
              {{ store.termsText || 'جميع الخدمات الرقمية يتم تنفيذها بأعلى معايير الأمان والسرعة. يرجى التأكد من صحة البيانات المدخلة قبل الدفع.' }}
            </p>
          </div>

          <button @click="showGuaranteeModal = false" class="w-full bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs py-2.5 rounded-xl shadow transition">
            فهمت وموافق ✓
          </button>
        </div>
      </div>

    </div>
  </div>

  <!-- ══════════════════════════════════════════════════════════════════════ -->
  <!-- 5. VUE APPLICATION LOGIC                                              -->
  <!-- ══════════════════════════════════════════════════════════════════════ -->
  <script>
    const { createApp, ref, computed, onMounted, watch } = Vue;

    // Comprehensive Currency Definitions (22 Arab Countries + Major + Digital)
    const currencyOptions = [
      { code: 'USD', name: 'دولار أمريكي', symbol: '$', decimals: 2 },
      { code: 'EUR', name: 'يورو', symbol: '€', decimals: 2 },
      { code: 'RUB', name: 'روبل روسي', symbol: '₽', decimals: 1 },
      { code: 'TRY', name: 'ليرة تركية', symbol: '₺', decimals: 1 },
      { code: 'IRR', name: 'ريال إيراني', symbol: '﷼', decimals: 0 },
      { code: 'USDT', name: 'تيثر رقمي (USDT)', symbol: '₮', decimals: 2 },
      { code: 'STARS', name: 'نجوم تليجرام', symbol: '⭐', decimals: 0 },
      // 22 Arab Currencies
      { code: 'IQD', name: 'دينار عراقي', symbol: 'د.ع', decimals: 0 },
      { code: 'SAR', name: 'ريال سعودي', symbol: 'ر.س', decimals: 2 },
      { code: 'AED', name: 'درهم إماراتي', symbol: 'د.إ', decimals: 2 },
      { code: 'KWD', name: 'دينار كويتي', symbol: 'د.ك', decimals: 3 },
      { code: 'QAR', name: 'ريال قطري', symbol: 'ر.ق', decimals: 2 },
      { code: 'BHD', name: 'دينار بحريني', symbol: 'د.ب', decimals: 3 },
      { code: 'OMR', name: 'ريال عماني', symbol: 'ر.ع', decimals: 3 },
      { code: 'EGP', name: 'جنيه مصري', symbol: 'ج.م', decimals: 2 },
      { code: 'JOD', name: 'دينار أردني', symbol: 'د.أ', decimals: 2 },
      { code: 'SYP', name: 'ليرة سورية', symbol: 'ل.س', decimals: 0 },
      { code: 'LBP', name: 'ليرة لبنانية', symbol: 'ل.ل', decimals: 0 },
      { code: 'LYD', name: 'دينار ليبي', symbol: 'د.ل', decimals: 2 },
      { code: 'TND', name: 'دينار تونسي', symbol: 'د.ت', decimals: 2 },
      { code: 'DZD', name: 'دينار جزائري', symbol: 'د.ج', decimals: 1 },
      { code: 'MAD', name: 'درهم مغربي', symbol: 'د.م', decimals: 2 },
      { code: 'SDG', name: 'جنيه سوداني', symbol: 'ج.س', decimals: 0 },
      { code: 'YER', name: 'ريال يمني', symbol: 'ر.ي', decimals: 0 },
      { code: 'SOS', name: 'شلن صومالي', symbol: 'ش.ص', decimals: 0 },
      { code: 'MRU', name: 'أوقية موريتانية', symbol: 'أ.م', decimals: 1 },
      { code: 'DJF', name: 'فرنك جيبوتي', symbol: 'ف.ج', decimals: 0 },
      { code: 'KMF', name: 'فرنك قمري', symbol: 'ف.ق', decimals: 0 },
      { code: 'ILS', name: 'شيكل', symbol: '₪', decimals: 2 }
    ];

    const DEFAULT_RATES = {
      USD: 1.0, EUR: 0.92, RUB: 92.0, TRY: 32.5, IRR: 600000.0, USDT: 1.0, STARS: 50.0,
      IQD: 1500.0, SAR: 3.75, AED: 3.67, KWD: 0.31, QAR: 3.64, BHD: 0.38, OMR: 0.385,
      EGP: 48.5, JOD: 0.71, SYP: 14500.0, LBP: 89500.0, LYD: 4.85, TND: 3.12,
      DZD: 134.5, MAD: 10.05, SDG: 2000.0, YER: 1600.0, SOS: 570.0, MRU: 39.5,
      DJF: 178.0, KMF: 455.0, ILS: 3.70, POINTS: 10000.0
    };

    // Full 5 Languages Translation Dictionary
    const I18N = {
      ar: {
        online: "متصل الآن", recharge: "شحن", cart: "السلة", empty_cart: "سلتك فارغة",
        cart_total: "إجمالي السلة", checkout_cart: "إتمام وشراء السلة", instant_buy: "شراء فوري",
        add_to_cart: "أضف للسلة", available_balance: "رصيدك المتاح الحالي", wallet_topup: "شحن المحفظة",
        statement: "كشف الحساب", my_orders: "طلباتي السابقة", vip_support: "الدعم الفني VIP",
        golden_guarantee: "الضمان الذهبي والشروط", lucky_wheel: "عجلة الحظ اليومية",
        referral_program: "نظام الإحالة والمكافآت المالية",
        referral_desc: "احصل على نسبة 5% رصيد فوري في محفظتك عن كل طلب يقوم به أصدقاؤك!",
        copy_link: "نسخ الرابط 📋", financial_statement: "كشف الحساب وسجل العمليات المالية",
        no_transactions: "لا توجد حركات مالية مسجلة حتى الآن في محفظتك.",
        support_available: "24/7 متاح الآن", golden_guarantee_title: "الضمان الذهبي وسياسة الاستخدام",
        refund_policy: "سياسة الاسترجاع الفوري", terms_of_service: "شروط تقديم الخدمة",
        unit: "قطعة", store_currency: "عملة المتجر الافتراضية", role_admin: "مدير المنصة 🛡️",
        role_seller: "مالك المتجر 👑", role_buyer: "مشتري معتمد ⭐",
        nav_store: "المتجر", nav_orders: "طلباتي", nav_account: "حسابي", nav_seller: "لوحة البائع", nav_admin: "لوحة الأدمن",
        balance: "الرصيد", invited: "المدعوون", earned: "الأرباح", transactions_count: "عمليات"
      },
      en: {
        online: "Online", recharge: "Top Up", cart: "Cart", empty_cart: "Your cart is empty",
        cart_total: "Cart Total", checkout_cart: "Checkout Cart", instant_buy: "Instant Buy",
        add_to_cart: "Add to Cart", available_balance: "Available Balance", wallet_topup: "Top Up Wallet",
        statement: "Statement", my_orders: "My Orders", vip_support: "VIP Support",
        golden_guarantee: "Guarantee & Terms", lucky_wheel: "Lucky Wheel",
        referral_program: "Referral & Rewards",
        referral_desc: "Get 5% instant cashback in your wallet on every order from friends!",
        copy_link: "Copy Link 📋", financial_statement: "Financial Statement & History",
        no_transactions: "No financial transactions recorded yet.",
        support_available: "24/7 Active Now", golden_guarantee_title: "Golden Guarantee & Terms",
        refund_policy: "Instant Refund Policy", terms_of_service: "Terms of Service",
        unit: "item", store_currency: "Default Store Currency", role_admin: "Platform Admin 🛡️",
        role_seller: "Store Owner 👑", role_buyer: "Verified Buyer ⭐",
        nav_store: "Store", nav_orders: "Orders", nav_account: "Account", nav_seller: "Seller Panel", nav_admin: "Admin Panel",
        balance: "Balance", invited: "Invited", earned: "Earned", transactions_count: "txs"
      },
      ru: {
        online: "В сети", recharge: "Пополнить", cart: "Корзина", empty_cart: "Корзина пуста",
        cart_total: "Итого к оплате", checkout_cart: "Оформить корзину", instant_buy: "Купить сейчас",
        add_to_cart: "В корзину", available_balance: "Доступный баланс", wallet_topup: "Пополнить баланс",
        statement: "Выписка", my_orders: "Мои заказы", vip_support: "VIP Поддержка",
        golden_guarantee: "Гарантия и правила", lucky_wheel: "Колесо фортуны",
        referral_program: "Реферальная программа",
        referral_desc: "Получайте 5% мгновенно на свой баланс с каждого заказа друзей!",
        copy_link: "Копировать ссылку 📋", financial_statement: "История финансовых операций",
        no_transactions: "В вашем кошельке пока нет операций.",
        support_available: "24/7 На связи", golden_guarantee_title: "Золотая гарантия и условия",
        refund_policy: "Политика возврата средств", terms_of_service: "Условия обслуживания",
        unit: "шт", store_currency: "Основная валюта магазина", role_admin: "Администратор 🛡️",
        role_seller: "Владелец магазина 👑", role_buyer: "Покупатель ⭐",
        nav_store: "Магазин", nav_orders: "Заказы", nav_account: "Аккаунт", nav_seller: "Панель продавца", nav_admin: "Панель админа",
        balance: "Баланс", invited: "Приглашено", earned: "Заработано", transactions_count: "операций"
      },
      fa: {
        online: "آنلاین", recharge: "شارژ", cart: "سبد خرید", empty_cart: "سبد خرید خالی است",
        cart_total: "مجموع سبد خرید", checkout_cart: "تکمیل و پرداخت سبد", instant_buy: "خرید فوری",
        add_to_cart: "افزودن به سبد", available_balance: "موجودی قابل استفاده", wallet_topup: "شارژ کیف پول",
        statement: "صورتحساب", my_orders: "سفارش‌های من", vip_support: "پشتیبانی VIP",
        golden_guarantee: "ضمانت طلایی و قوانین", lucky_wheel: "گردونه شانس روزانه",
        referral_program: "سیستم دعوت و پاداش",
        referral_desc: "با هر خرید دوستانتان ۵٪ پاداش نقدی فوری در کیف پول خود دریافت کنید!",
        copy_link: "کپی لینک 📋", financial_statement: "صورتحساب و تاریخچه تراکنش‌ها",
        no_transactions: "هنوز هیچ تراکنش مالی در کیف پول شما ثبت نشده است.",
        support_available: "۲۴/۷ فعال", golden_guarantee_title: "ضمانت طلایی و شرایط استفاده",
        refund_policy: "سیاست بازگشت وجه فوری", terms_of_service: "شرایط ارائه خدمات",
        unit: "عدد", store_currency: "ارز پیش‌فرض فروشگاه", role_admin: "مدیر ارشد پلتفرم 🛡️",
        role_seller: "مالک فروشگاه 👑", role_buyer: "خریدار تایید شده ⭐",
        nav_store: "فروشگاه", nav_orders: "سفارش‌ها", nav_account: "حساب من", nav_seller: "پنل فروشنده", nav_admin: "پنل ادمین",
        balance: "موجودی", invited: "دعوت شده‌ها", earned: "پاداش کسب شده", transactions_count: "تراکنش"
      },
      tr: {
        online: "Çevrimiçi", recharge: "Yükle", cart: "Sepet", empty_cart: "Sepetiniz boş",
        cart_total: "Sepet Toplamı", checkout_cart: "Sepeti Onayla", instant_buy: "Hemen Al",
        add_to_cart: "Sepete Ekle", available_balance: "Kullanılabilir Bakiye", wallet_topup: "Cüzdanı Yükle",
        statement: "Hesap Özeti", my_orders: "Siparişlerim", vip_support: "VIP Destek",
        golden_guarantee: "Garanti ve Koşullar", lucky_wheel: "Günlük Şans Çarkı",
        referral_program: "Referans ve Ödüller",
        referral_desc: "Arkadaşlarınızın her siparişinden anında %5 cüzdan bakiyesi kazanın!",
        copy_link: "Linki Kopyala 📋", financial_statement: "Hesap Hareketleri ve İşlem Geçmişi",
        no_transactions: "Cüzdanınızda henüz kayıtlı işlem bulunmuyor.",
        support_available: "7/24 Aktif", golden_guarantee_title: "Altın Garanti ve Kullanım Koşulları",
        refund_policy: "Anında İade Politikası", terms_of_service: "Hizmet Şartları",
        unit: "adet", store_currency: "Varsayılan Mağaza Para Birimi", role_admin: "Platform Yöneticisi 🛡️",
        role_seller: "Mağaza Sahibi 👑", role_buyer: "Onaylı Müşteri ⭐",
        nav_store: "Mağaza", nav_orders: "Siparişler", nav_account: "Hesabım", nav_seller: "Satıcı Paneli", nav_admin: "Yönetici Paneli",
        balance: "Bakiye", invited: "Davet Edilenler", earned: "Kazanılan", transactions_count: "işlem"
      }
    };

    createApp({
      setup() {
        const loading = ref(true);
        const currentTab = ref('store');
        // Multi-currency, multi-language & marketing state
        const currentCurrency = ref(localStorage.getItem('botforge_currency') || 'USD');
        const currentLang = ref(localStorage.getItem('botforge_lang') || 'ar');
        const exchangeRates = ref({ ...DEFAULT_RATES });
        const showGuaranteeModal = ref(false);
        const accountData = ref({});

        const t = (key) => {
          const l = currentLang.value || 'ar';
          return I18N[l]?.[key] || I18N['ar']?.[key] || I18N['en']?.[key] || key;
        };

        const scrollToStatement = () => {
          const el = document.getElementById('financial-statement-card');
          if (el) el.scrollIntoView({ behavior: 'smooth' });
        };

        const isBrowserPreview = ref(!Boolean(window.Telegram?.WebApp?.initData));

        const switchRole = async (newRole) => {
          role.value = newRole;
          if (newRole === 'admin') {
            currentTab.value = 'admin';
            await loadAdminData();
          } else if (newRole === 'seller') {
            currentTab.value = 'seller';
            await loadSellerSettings();
            await loadSellerStats();
            await loadSellerProducts();
          } else {
            currentTab.value = 'store';
          }
        };


        watch(currentLang, async (newLang) => {
          try {
            localStorage.setItem('botforge_lang', newLang);
            document.documentElement.lang = newLang;
            document.documentElement.dir = (newLang === 'ar' || newLang === 'fa') ? 'rtl' : 'ltr';
            const initData = tg?.initData || '';
            fetch('/api/miniapp/user/language', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({ lang: newLang })
            }).catch(() => {});
          } catch {}
        }, { immediate: true });

        watch(currentCurrency, (newCur) => {
          try {
            localStorage.setItem('botforge_currency', newCur);
          } catch {}
        });

        // Wheel of Fortune
        const showWheelModal = ref(false);
        const spinningWheel = ref(false);
        const wheelRotation = ref(0);
        const wheelResult = ref(null);

        // Coupons
        const enteredCouponCode = ref('');
        const appliedCoupon = ref(null);
        const sellerCoupons = ref([]);
        const newCouponForm = ref({ code: '', type: 'percent', val: 20, duration_type: 'days', duration_value: 7, max_uses: 100 });
        const creatingCoupon = ref(false);

        // Admin Fulfillment & Templates State
        const adminOrdersSearchQuery = ref('');
        const adminOrdersStatusFilter = ref('all');
        const showDeliveryModal = ref(false);
        const deliveryTargetOrder = ref(null);
        const deliveryForm = ref({ text: '', proof: '' });
        const deliveringOrder = ref(false);
        const showRejectModal = ref(false);
        const rejectTargetOrder = ref(null);
        const rejectReason = ref('');
        const rejectingOrder = ref(false);
        const adminTemplates = ref([]);

        // Manual Payments
        const activeDepositTab = ref('manual');
        const manualPaymentMethods = ref([]);
        const selectedPaymentMethod = ref(null);
        const manualDepositAmount = ref(5.0);
        const manualSenderRef = ref('');
        const manualReceiptUrl = ref('');
        const manualReceiptNotes = ref('');
        const submittingManualReceipt = ref(false);
        const sellerPaymentReceipts = ref([]);

        // Gift
        const isGiftOrder = ref(false);
        const giftRecipient = ref('');
        const giftMessage = ref('');
        const giftTheme = ref('party');
        const showGiftCardModal = ref(false);
        const activeGiftOrder = ref(null);

        // Statement, Reviews & Abandoned cart
        const userTransactions = ref([]);
        const productReviewsList = ref([]);
        const reviewFormRating = ref(5);
        const reviewFormComment = ref('');
        const submittingReview = ref(false);
        const abandonedCartBroadcasting = ref(false);
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

        // Cart & Native Media & Stars state
        const cartItems = ref([]);
        const showCartDrawer = ref(false);
        const purchaseQuantity = ref(1);
        const uploadingMedia = ref(false);
        const productMediaFileInput = ref(null);
        const depositingStars = ref(false);
        const customStarsAmount = ref(50);
        const isCheckingOutCart = ref(false);

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
          order_channel: '',
          currency: 'USD'
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

        // Super Admin Master Catalog & Dashboard State
        const adminActiveSubTab = ref('catalog');
        const adminProducts = ref([]);
        const adminBots = ref([]);
        const adminCategoryFilter = ref('all');
        const showAdminProductModal = ref(false);
        const adminProductForm = ref({
          id: '',
          name: '',
          name_ar: '',
          category: 'gaming',
          template_type: 'manual_subs',
          cost_price: 1.0,
          base_user_price: 1.5,
          image_url: '',
          description: '',
          requirements: []
        });
        const adminBroadcastMsg = ref('');
        const adminBroadcastTarget = ref('owners');
        const sendingBroadcast = ref(false);
        const savingAdminProduct = ref(false);
        const uploadingAdminMedia = ref(false);
        const adminMediaFileInput = ref(null);

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
            const tgStartParam = tg?.initDataUnsafe?.start_param || '';
            let storeId = urlParams.get('store_id') || urlParams.get('start_param') || tgStartParam || '';
            if (!storeId && pathParts.length > 1 && (pathParts[0] === 'store' || pathParts[0] === 'app')) {
              storeId = pathParts[1];
            }
            if (!storeId) {
              storeId = 'default';
            }

            // 1. Authenticate user via Telegram initData
            const initData = tg?.initData || '';
            const requestedRole = urlParams.get('role') || (window.location.pathname.includes('/admin_app') ? 'admin' : (urlParams.has('seller') || urlParams.has('panel') ? 'seller' : ''));
            try {
              const authRes = await fetch('/api/miniapp/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData, storeId, role: requestedRole })
              });
              const authJson = await authRes.json();
              if (authJson.success && authJson.data) {
                user.value = authJson.data.user || {};
                role.value = authJson.data.role || 'buyer';
                if (storeId === 'default' && authJson.data.store?.botUsername) {
                  storeId = authJson.data.store.botUsername;
                }
              }
            } catch (authErr) {
              console.warn('Auth error:', authErr);
            }

            // 2. Fetch store info
            try {
              const storeRes = await fetch(`/api/miniapp/store-info?store_id=${storeId}`);
              const storeJson = await storeRes.json();
              if (storeJson.success && storeJson.data) {
                store.value = storeJson.data;
                themeSettings.value = storeJson.data.themeSettings || {};
                if (storeJson.data.exchangeRates) {
                  exchangeRates.value = { ...DEFAULT_RATES, ...storeJson.data.exchangeRates };
                }
                if (storeJson.data.currency) {
                  sellerSettingsForm.value.currency = storeJson.data.currency;
                  if (!localStorage.getItem('botforge_currency')) {
                    currentCurrency.value = storeJson.data.currency;
                  }
                }
                sellerSettingsForm.value.support_url = storeJson.data.supportUrl || '';
                sellerSettingsForm.value.terms_text = storeJson.data.termsText || '';
                sellerSettingsForm.value.policy_text = storeJson.data.policyText || '';
                sellerSettingsForm.value.order_channel = storeJson.data.orderChannel || storeJson.data.order_channel || '';
              }
            } catch (sErr) {
              console.warn('Store info error:', sErr);
            }

            // Tab routing from URL or pathname
            const tabParam = urlParams.get('tab');
            if (window.location.pathname.includes('/admin_app') || requestedRole === 'admin') {
              if (role.value !== 'admin' && !initData) {
                role.value = 'admin';
              }
              currentTab.value = 'admin';
            } else if (tabParam && ['store', 'orders', 'account', 'seller', 'admin'].includes(tabParam)) {
              if (tabParam === 'admin' && role.value !== 'admin') {
                if (!initData) { role.value = 'admin'; currentTab.value = 'admin'; }
                else { currentTab.value = 'store'; }
              } else if (tabParam === 'seller' && role.value !== 'seller' && role.value !== 'admin') {
                if (!initData) { role.value = 'seller'; currentTab.value = 'seller'; }
                else { currentTab.value = 'store'; }
              } else {
                currentTab.value = tabParam;
              }
            } else if (urlParams.has('panel') || urlParams.has('seller') || requestedRole === 'seller') {
              if (role.value !== 'seller' && role.value !== 'admin' && !initData) {
                role.value = 'seller';
              }
              currentTab.value = 'seller';
            }


            // 3. Load catalog
            try {
              const catRes = await fetch(`/api/miniapp/catalog?store_id=${storeId}`);
              const catJson = await catRes.json();
              if (catJson.success && catJson.data) {
                categories.value = catJson.data.categories || [];
                products.value = catJson.data.products || [];

                const catParam = urlParams.get('cat') || urlParams.get('category');
                if (catParam) selectedCategory.value = catParam;
              }
            } catch (cErr) {
              console.warn('Catalog error:', cErr);
            }

            // 4. Load initial orders & stats & payment methods & statement
            await loadOrders();
            await loadPaymentMethods();
            await loadUserStatement();
            if (role.value === 'seller' || role.value === 'admin') {
              await loadSellerSettings();
              await loadSellerStats();
              await loadSellerProducts();
              await loadThemeVersions();
              await loadSellerCoupons();
              await loadSellerReceipts();
            }
            if (role.value === 'admin') {
              await loadAdminData();
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

        // Media format helper (video vs image)
        const isMediaVideo = (url) => {
          if (!url || typeof url !== 'string') return false;
          const clean = url.split('?')[0].toLowerCase();
          return clean.endsWith('.mp4') || clean.endsWith('.webm') || clean.endsWith('.mov') || clean.includes('/video/');
        };

        const cartTotalCount = computed(() => {
          return cartItems.value.reduce((sum, item) => sum + (Number(item.quantity) || 1), 0);
        });

        const cartTotalPrice = computed(() => {
          return cartItems.value.reduce((sum, item) => sum + (Number(item.price || 0) * (Number(item.quantity) || 1)), 0);
        });

        const addToCart = (prod, qty = 1) => {
          if (!prod) return;
          const opt = selectedPriceOption.value && activeProduct.value?.id === prod.id ? selectedPriceOption.value : prod.priceOptions?.[0];
          const unitPrice = opt ? Number(opt.userPrice || opt.price || 1) : Number(prod.price_usd || 1);
          const effectivePrice = prod.discountPercent > 0 ? Number((unitPrice * (100 - prod.discountPercent) / 100).toFixed(2)) : unitPrice;

          const existingIndex = cartItems.value.findIndex(item => item.id === prod.id && (!opt || item.optionId === opt.id));
          if (existingIndex > -1) {
            cartItems.value[existingIndex].quantity += Number(qty) || 1;
          } else {
            cartItems.value.push({
              id: prod.id,
              name: prod.nameAr || prod.name,
              nameAr: prod.nameAr || prod.name,
              price: effectivePrice,
              quantity: Number(qty) || 1,
              optionId: opt?.id,
              image_url: (prod.mediaUrls && prod.mediaUrls[0]) || prod.image_url || '',
              userInputs: { ...userFormInputs.value }
            });
          }
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
          alert('تمت إضافة المنتج إلى السلة بنجاح! 🛒');
        };

        const increaseCartQty = (idx) => {
          if (cartItems.value[idx]) cartItems.value[idx].quantity++;
        };

        const decreaseCartQty = (idx) => {
          if (!cartItems.value[idx]) return;
          if (cartItems.value[idx].quantity > 1) {
            cartItems.value[idx].quantity--;
          } else {
            cartItems.value.splice(idx, 1);
          }
        };

        const removeCartItem = (idx) => {
          cartItems.value.splice(idx, 1);
        };

        const checkoutCart = async () => {
          if (!cartItems.value.length) return;
          if (user.value.balance < cartTotalPrice.value) {
            alert(`رصيدك الحالي ($${(user.value.balance || 0).toFixed(2)}) غير كافٍ. يرجى شحن الرصيد أولاً.`);
            showDepositModal.value = true;
            return;
          }
          isCheckingOutCart.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/order/cart-checkout', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({ items: cartItems.value })
            });
            const json = await res.json();
            if (json.success || json.ok) {
              if (json.new_balance_usd !== undefined) {
                user.value.balance = Number(json.new_balance_usd);
              }
              cartItems.value = [];
              showCartDrawer.value = false;
              currentTab.value = 'orders';
              await loadOrders();
              alert(json.message || 'تم تأكيد وشراء عناصر السلة بنجاح! 🎉');
            } else {
              alert(json.error || json.message || 'فشل إتمام طلبات السلة');
            }
          } catch {
            alert('حدث خطأ أثناء معالجة السلة');
          } finally {
            isCheckingOutCart.value = false;
          }
        };

        const handleProductMediaUpload = async (evt) => {
          const file = evt.target.files?.[0];
          if (!file) return;
          uploadingMedia.value = true;
          try {
            const initData = tg?.initData || '';
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/miniapp/upload', {
              method: 'POST',
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: formData
            });
            const json = await res.json();
            if (json.success || json.ok) {
              const uploadedUrl = json.url || json.data?.url || '';
              editingProduct.value.imageUrl = uploadedUrl;
              alert('تم رفع الوسائط بنجاح من المعرض! 📸');
            } else {
              alert(json.error || 'فشل رفع الملف، تأكد من حجم الملف ونوعه');
            }
          } catch {
            alert('حدث خطأ أثناء رفع الملف');
          } finally {
            uploadingMedia.value = false;
            if (evt.target) evt.target.value = '';
          }
        };

        const payWithStarsAmount = async (starsAmount) => {
          const amount = parseInt(starsAmount) || 50;
          depositingStars.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/deposit/stars', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({ stars: amount })
            });
            const json = await res.json();
            if (json.success || json.ok) {
              if (json.invoice_link && tg?.openInvoice) {
                tg.openInvoice(json.invoice_link, (status) => {
                  if (status === 'paid') {
                    if (json.new_balance_usd !== undefined) {
                      user.value.balance = Number(json.new_balance_usd);
                    }
                    alert(`تم شحن ${amount} نجمة بنجاح إلى رصيدك! ⭐`);
                    showDepositModal.value = false;
                  }
                });
              } else {
                if (json.new_balance_usd !== undefined) {
                  user.value.balance = Number(json.new_balance_usd);
                }
                alert(json.message || `تم شحن ${amount} نجمة بنجاح! ⭐`);
                showDepositModal.value = false;
              }
            } else {
              alert(json.error || 'فشل إنشاء فاتورة النجوم');
            }
          } catch {
            alert('حدث خطأ أثناء معالجة شحن النجوم');
          } finally {
            depositingStars.value = false;
          }
        };

        const openProductModal = (prod) => {
          activeProduct.value = prod;
          selectedPriceOption.value = prod.priceOptions?.[0] || null;
          purchaseQuantity.value = 1;
          userFormInputs.value = {};
          termsAgreed.value = true;
        };

        const getCalculatedTotal = () => {
          if (!activeProduct.value) return '0.00';
          if (activeProduct.value.templateType === 'smm_boost') {
            const base = selectedPriceOption.value?.userPrice || activeProduct.value.price_usd || 1.0;
            return ((base * smmQuantity.value) / 1000).toFixed(2);
          }
          const base = selectedPriceOption.value?.userPrice || activeProduct.value.price_usd || 1.0;
          const qty = Number(purchaseQuantity.value) || 1;
          if (activeProduct.value.discountPercent > 0) {
            return ((base * (100 - activeProduct.value.discountPercent) / 100) * qty).toFixed(2);
          }
          return (Number(base) * qty).toFixed(2);
        };

        const submitOrder = async () => {
          isSubmitting.value = true;
          try {
            const initData = tg?.initData || '';
            const qty = activeProduct.value.templateType === 'smm_boost' ? smmQuantity.value : (Number(purchaseQuantity.value) || 1);
            const payload = {
              productId: activeProduct.value.id,
              priceOptionId: selectedPriceOption.value?.id,
              quantity: qty,
              targetUrl: smmUrl.value,
              userInputs: userFormInputs.value,
              coupon_code: appliedCoupon.value?.code || enteredCouponCode.value,
              is_gift: isGiftOrder.value,
              gift_recipient: giftRecipient.value,
              gift_message: giftMessage.value,
              gift_theme: giftTheme.value,
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
              await loadUserStatement();
              if (isGiftOrder.value) {
                activeGiftOrder.value = {
                  details: { gift_recipient: giftRecipient.value, gift_message: giftMessage.value },
                  delivery_data: json.voucher || json.data?.voucher || ''
                };
                showGiftCardModal.value = true;
              }
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
          payWithStarsAmount(50);
        };

        const payWithExternalGateway = () => {
          const link = store.value?.supportUrl || `https://t.me/${store.value?.botUsername || 'bot'}`;
          if (tg?.openLink) {
            tg.openLink(link);
          } else {
            window.open(link, '_blank');
          }
        };

        const filteredAdminOrdersList = computed(() => {
          let list = adminOrders.value || [];
          if (adminOrdersStatusFilter.value !== 'all') {
            if (adminOrdersStatusFilter.value === 'pending') {
              list = list.filter(o => o.status === 'pending' || o.status === 'processing');
            } else if (adminOrdersStatusFilter.value === 'completed') {
              list = list.filter(o => o.status === 'completed');
            } else if (adminOrdersStatusFilter.value === 'canceled') {
              list = list.filter(o => o.status === 'canceled' || o.status === 'refunded' || o.status === 'rejected');
            }
          }
          if (adminOrdersSearchQuery.value && adminOrdersSearchQuery.value.trim()) {
            const q = adminOrdersSearchQuery.value.trim().toLowerCase();
            list = list.filter(o => {
              const ref = String(o.order_ref || o.order_id || '').toLowerCase();
              const buyer = String(o.buyer_username || o.user_id || '').toLowerCase();
              const seller = String(o.seller_username || o.seller_id || '').toLowerCase();
              const bot = String(o.bot_username || o.bot_id || '').toLowerCase();
              const prod = String(o.service_name || o.product_name || '').toLowerCase();
              return ref.includes(q) || buyer.includes(q) || seller.includes(q) || bot.includes(q) || prod.includes(q);
            });
          }
          return list;
        });

        const openDeliverOrderModal = (ord) => {
          deliveryTargetOrder.value = ord;
          deliveryForm.value = { text: ord.delivery_text || '', proof: ord.delivery_proof || '' };
          showDeliveryModal.value = true;
        };

        const submitDeliveryFulfillment = async () => {
          if (!deliveryTargetOrder.value || !deliveryForm.value.text.trim()) return;
          deliveringOrder.value = true;
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
                orderRef: deliveryTargetOrder.value.order_ref || deliveryTargetOrder.value.order_id,
                action: 'deliver',
                deliveryData: deliveryForm.value.text.trim(),
                deliveryProof: deliveryForm.value.proof.trim()
              })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم تسليم الطلب وإرسال الرسالة إلى تيليجرام المشتري بنجاح! 🚀');
              showDeliveryModal.value = false;
              await loadAdminOrders();
              await loadAdminOverview();
            } else {
              alert(json.message || json.error || 'تعذر تسليم الطلب');
            }
          } catch {
            alert('حدث خطأ أثناء الاتصال بالسيرفر');
          } finally {
            deliveringOrder.value = false;
          }
        };

        const openRejectOrderModal = (ord) => {
          rejectTargetOrder.value = ord;
          rejectReason.value = ord.refund_reason || '';
          showRejectModal.value = true;
        };

        const submitOrderRejection = async () => {
          if (!rejectTargetOrder.value || !rejectReason.value.trim()) return;
          rejectingOrder.value = true;
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
                orderRef: rejectTargetOrder.value.order_ref || rejectTargetOrder.value.order_id,
                action: 'reject',
                rejectionReason: rejectReason.value.trim()
              })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم إلغاء الطلب وإشعار المشتري بنجاح ❌');
              showRejectModal.value = false;
              await loadAdminOrders();
              await loadAdminOverview();
            } else {
              alert(json.message || json.error || 'فشل إلغاء الطلب');
            }
          } catch {
            alert('حدث خطأ في الاتصال');
          } finally {
            rejectingOrder.value = false;
          }
        };

        const saveOrderAdminNotes = async (ord) => {
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
                orderRef: ord.order_ref || ord.order_id,
                action: 'save_notes',
                adminNotes: ord.admin_notes || ''
              })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert('تم حفظ الملاحظة الإدارية بنجاح 📝');
            }
          } catch {
            alert('تعذر حفظ الملاحظة');
          }
        };

        const exportOrdersCsv = () => {
          const list = adminOrders.value || [];
          if (!list.length) {
            alert('لا توجد طلبات لتصديرها');
            return;
          }
          const NL = String.fromCharCode(10);
          let csv = 'OrderRef,Date,Status,Bot,Seller,Buyer,Product,CostUSD,SellingUSD,ProfitUSD,TargetCredentials,DeliveryText' + NL;
          list.forEach(o => {
            const row = [
              o.order_ref || o.order_id,
              o.created_at || o.created || '',
              o.status || '',
              o.bot_username || o.bot_id || '',
              o.seller_username || o.seller_id || '',
              o.buyer_username || o.user_id || '',
              (o.service_name || o.product_name || '').replace(/,/g, ' '),
              o.cost_price_usd || o.cost_price || 0,
              o.seller_price_usd || o.price_user_usd || o.total_price || 0,
              o.profit_seller_usd || 0,
              String(o.target || o.customer_credentials || '').split(NL).join(' ').split(',').join(' '),
              String(o.delivery_text || '').split(NL).join(' ').split(',').join(' ')
            ];
            csv += row.join(',') + NL;
          });
          const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `orders_export_${Date.now()}.csv`;
          a.click();
        };

        const loadAdminTemplates = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/templates', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.ok || json.success) {
              adminTemplates.value = json.templates || json.data || [];
            }
          } catch (e) {
            console.warn('Error loading admin templates:', e);
          }
        };

        const saveAdminTemplateConfig = async (tpl) => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/templates/save', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify(tpl)
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم حفظ وتطبيق تعديلات القالب بنجاح! 🎨');
            } else {
              alert(json.error || 'فشل حفظ القالب');
            }
          } catch {
            alert('حدث خطأ أثناء حفظ القالب');
          }
        };

        const handleAdminOrderAction = async (orderRef, action) => {
          if (action === 'deliver') {
            const ord = adminOrders.value.find(o => (o.order_ref || o.order_id) === orderRef);
            if (ord) return openDeliverOrderModal(ord);
          }
          if (action === 'reject') {
            const ord = adminOrders.value.find(o => (o.order_ref || o.order_id) === orderRef);
            if (ord) return openRejectOrderModal(ord);
          }
          if (action === 'refund_both') {
            if (!confirm('هل تريد استرجاع المبلغ فورياً إلى محفظة المشتري وإلغاء الطلب؟')) return;
          }
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
                action
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
              if (sellerSettingsForm.value.currency) {
                store.value.currency = sellerSettingsForm.value.currency;
                currentCurrency.value = sellerSettingsForm.value.currency;
              }
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
            id: '',
            is_master: false,
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

        const openEditSellerProduct = (prod) => {
          editingProduct.value = {
            id: prod.id,
            is_master: !!prod.is_master,
            name: prod.name || prod.nameAr,
            nameAr: prod.nameAr || prod.name,
            category: prod.category || 'subscriptions',
            templateType: prod.templateType || 'manual_subs',
            costPrice: Number(prod.cost_price || prod.costPrice || 1.0),
            userPrice: Number(prod.price_usd || prod.userPrice || (prod.cost_price ? prod.cost_price * 1.2 : 1.5)),
            imageUrl: prod.image_url || (prod.mediaUrls && prod.mediaUrls[0]) || '',
            description: prod.description || '',
            requirements: prod.requirements || []
          };
          showProductModal.value = true;
        };

        const resetSellerProducts = async () => {
          if (!confirm('هل تريد استرجاع كافة المنتجات المركزية التي قمت بحذفها سابقاً؟')) return;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/products/reset', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم استرجاع كافة المنتجات المحذوفة بنجاح!');
              await loadSellerProducts();
            } else {
              alert(json.message || json.error || 'تعذر استرجاع المنتجات');
            }
          } catch {
            alert('حدث خطأ في الاتصال');
          }
        };

        const resetSellerPrices = async () => {
          if (!confirm('هل تريد استعادة أسعار البيع الافتراضية المقترحة من إدارة المنصة لكافة المنتجات المركزية؟')) return;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/prices/reset', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تمت استعادة أسعار الآدمن الافتراضية بنجاح!');
              await loadSellerProducts();
            } else {
              alert(json.message || json.error || 'تعذر إعادة تعيين الأسعار');
            }
          } catch {
            alert('حدث خطأ في الاتصال');
          }
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
              id: editingProduct.value.id || undefined,
              is_master: editingProduct.value.is_master,
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
              try {
                const catRes = await fetch(`/api/miniapp/catalog?store_id=${store.value?.botId || 'default'}`);
                const catJson = await catRes.json();
                if (catJson.success && catJson.data) products.value = catJson.data.products || [];
              } catch {}
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

        // Super Admin Methods
        const loadAdminProducts = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/products', {
              headers: { 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.success || json.ok) {
              adminProducts.value = json.products || json.data || [];
            }
          } catch (e) {
            console.warn('Error loading admin products:', e);
          }
        };

        const loadAdminBots = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/bots', {
              headers: { 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' }
            });
            const json = await res.json();
            if (json.success || json.ok) {
              adminBots.value = json.bots || json.data || [];
            }
          } catch (e) {
            console.warn('Error loading admin bots:', e);
          }
        };

        const loadAdminData = async () => {
          await Promise.all([
            loadAdminOverview(),
            loadAdminOrders(),
            loadAdminProducts(),
            loadAdminBots(),
            loadAdminTemplates()
          ]);
        };

        const filteredAdminProducts = computed(() => {
          if (adminCategoryFilter.value === 'all') return adminProducts.value;
          return adminProducts.value.filter(p => p.category === adminCategoryFilter.value || p.template_type === adminCategoryFilter.value);
        });

        const openAddAdminProduct = () => {
          adminProductForm.value = {
            id: '',
            name: '',
            name_ar: '',
            category: 'gaming',
            template_type: 'manual_subs',
            cost_price: 1.0,
            base_user_price: 1.5,
            image_url: '',
            description: '',
            requirements: []
          };
          showAdminProductModal.value = true;
        };

        const openEditAdminProduct = (prod) => {
          adminProductForm.value = {
            id: prod.id,
            name: prod.name || prod.name_ar,
            name_ar: prod.name_ar || prod.name,
            category: prod.category || 'gaming',
            template_type: prod.template_type || 'manual_subs',
            cost_price: Number(prod.cost_price || 1.0),
            base_user_price: Number(prod.base_user_price || prod.cost_price * 1.3 || 1.5),
            image_url: prod.image_url || '',
            description: prod.description || '',
            requirements: Array.isArray(prod.requirements) ? JSON.parse(JSON.stringify(prod.requirements)) : []
          };
          showAdminProductModal.value = true;
        };

        const addAdminRequirementPreset = (presetType) => {
          if (!adminProductForm.value.requirements) adminProductForm.value.requirements = [];
          const presets = {
            email_password: { name: 'email_password', label: 'البريد الإلكتروني + كلمة المرور (Email + Password)', type: 'text', placeholder: 'user@domain.com : password' },
            username_password: { name: 'username_password', label: 'اسم المستخدم + كلمة المرور (Username + Password)', type: 'text', placeholder: 'username : password' },
            password: { name: 'password', label: 'كلمة المرور (Password)', type: 'password', placeholder: '********' },
            player_id: { name: 'player_id', label: 'آيدي اللاعب (Player ID)', type: 'text', placeholder: 'مثال: 5123456789' },
            email: { name: 'email', label: 'البريد الإلكتروني (Email)', type: 'email', placeholder: 'example@gmail.com' },
            username: { name: 'username', label: 'اسم المستخدم (Username)', type: 'text', placeholder: '@username' },
            url: { name: 'target_url', label: 'رابط الحساب أو المنشور (URL)', type: 'url', placeholder: 'https://...' },
            phone: { name: 'phone', label: 'رقم الهاتف (Phone Number)', type: 'text', placeholder: '+9647...' },
            notes: { name: 'buyer_notes', label: 'ملاحظات إضافية من المشتري (Notes)', type: 'text', placeholder: 'أي تعليمات أو ملاحظات...' }
          };
          const p = presets[presetType];
          if (p && !adminProductForm.value.requirements.some(r => r.name === p.name)) {
            adminProductForm.value.requirements.push({ ...p });
          }
        };

        const removeAdminRequirement = (idx) => {
          if (adminProductForm.value.requirements) {
            adminProductForm.value.requirements.splice(idx, 1);
          }
        };

        const uploadAdminImage = async (evt) => {
          const file = evt.target.files?.[0];
          if (!file) return;
          uploadingAdminMedia.value = true;
          try {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/miniapp/upload', {
              method: 'POST',
              body: formData
            });
            const json = await res.json();
            if (json.ok || json.success) {
              adminProductForm.value.image_url = json.url;
              alert('تم رفع الصورة بنجاح! 📸');
            } else {
              alert(json.error || 'فشل رفع الصورة');
            }
          } catch {
            alert('حدث خطأ أثناء رفع الصورة');
          } finally {
            uploadingAdminMedia.value = false;
          }
        };

        const saveAdminProduct = async () => {
          if (!adminProductForm.value.name_ar && !adminProductForm.value.name) {
            alert('الرجاء كتابة اسم المنتج');
            return;
          }
          if (adminProductForm.value.base_user_price < adminProductForm.value.cost_price) {
            alert('سعر البيع لا يمكن أن يكون أقل من سعر التكلفة!');
            return;
          }
          savingAdminProduct.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/products/save', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify(adminProductForm.value)
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم حفظ ونشر المنتج المركزي بنجاح لجميع المتاجر! 🚀');
              showAdminProductModal.value = false;
              await loadAdminProducts();
            } else {
              alert(json.message || json.error || 'فشل حفظ المنتج');
            }
          } catch {
            alert('حدث خطأ أثناء الاتصال بالسيرفر');
          } finally {
            savingAdminProduct.value = false;
          }
        };

        const deleteAdminProduct = async (id) => {
          if (!confirm('تحذير: هل أنت متأكد من حذف هذا المنتج المركزي من جميع القوالب ومتاجر البائعين؟')) return;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/products/delete', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify({ id })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم حذف المنتج من المنصة بنجاح!');
              await loadAdminProducts();
            } else {
              alert(json.message || json.error || 'فشل حذف المنتج');
            }
          } catch {
            alert('حدث خطأ في الاتصال');
          }
        };

        const sendAdminBroadcast = async () => {
          if (!adminBroadcastMsg.value.trim()) {
            alert('يرجى كتابة نص الرسالة أولاً');
            return;
          }
          sendingBroadcast.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/admin/broadcast', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': initData, 'x-store-id': store.value?.botId || 'default' },
              body: JSON.stringify({ message: adminBroadcastMsg.value, target: adminBroadcastTarget.value })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم إرسال الإذاعة بنجاح! 📢');
              adminBroadcastMsg.value = '';
            } else {
              alert(json.message || json.error || 'فشل إرسال الإذاعة');
            }
          } catch {
            alert('حدث خطأ أثناء الإرسال');
          } finally {
            sendingBroadcast.value = false;
          }
        };

        watch(currentTab, (newTab) => {
          if (newTab === 'admin' && role.value === 'admin') {
            loadAdminData();
          }
        });

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
              if (json.data.currency) {
                sellerSettingsForm.value.currency = json.data.currency;
              }
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
          const lines = bulkCsvText.value.trim().split(String.fromCharCode(10));
          const firstLine = lines[0];
          const delim = firstLine.includes(String.fromCharCode(9)) ? String.fromCharCode(9) : (firstLine.includes(';') ? ';' : ',');
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

        
        const formatPrice = (usdAmount) => {
          const val = Number(usdAmount || 0);
          const cur = currentCurrency.value || 'USD';
          const cMeta = currencyOptions.find(c => c.code === cur) || { symbol: cur, decimals: 2 };
          const rate = Number(exchangeRates.value?.[cur] || DEFAULT_RATES[cur] || 1.0);
          const converted = val * rate;
          let formatted = '';
          if (cMeta.decimals === 0) {
            formatted = Math.round(converted).toLocaleString();
          } else {
            formatted = converted.toLocaleString(undefined, {
              minimumFractionDigits: cMeta.decimals,
              maximumFractionDigits: cMeta.decimals
            });
          }
          if (cMeta.symbol === '$') {
            return `$${formatted}`;
          }
          return `${formatted} ${cMeta.symbol}`;
        };

        const openWheelModal = () => {
          wheelResult.value = null;
          showWheelModal.value = true;
        };

        const spinFortuneWheel = async () => {
          if (spinningWheel.value) return;
          spinningWheel.value = true;
          wheelResult.value = null;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/wheel/spin', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.ok || json.success) {
              const prizeIdx = json.prize_index || 0;
              const extraSpins = 5 * 360;
              const targetAngle = extraSpins + (prizeIdx * 60) + 30;
              wheelRotation.value += targetAngle;
              setTimeout(() => {
                spinningWheel.value = false;
                wheelResult.value = json;
                if (json.new_balance_usd !== undefined) {
                  user.value.balance = json.new_balance_usd;
                }
              }, 3600);
            } else {
              spinningWheel.value = false;
              alert(json.message || json.error || 'حدث خطأ في التدوير');
            }
          } catch {
            spinningWheel.value = false;
            alert('تعذر الاتصال بسيرفر عجلة الحظ');
          }
        };

        const applyCouponCode = async () => {
          const code = enteredCouponCode.value.trim();
          if (!code) return;
          try {
            const initData = tg?.initData || '';
            const amount = activeProduct.value ? getCalculatedTotal() : cartTotalPrice.value;
            const res = await fetch('/api/miniapp/coupon/validate', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({
                code,
                amount,
                product_id: activeProduct.value?.id || ''
              })
            });
            const json = await res.json();
            if (json.valid || json.ok) {
              appliedCoupon.value = json;
              alert(`🎉 تم تطبيق كود الخصم بنجاح! قيمة الخصم: ${formatPrice(json.discount_usd)}`);
            } else {
              alert(json.message || 'كود الخصم غير صالح أو منتهي الصلاحية');
            }
          } catch {
            alert('تعذر التحقق من كود الخصم');
          }
        };

        const loadSellerCoupons = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/coupons', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.success || json.ok) {
              sellerCoupons.value = json.coupons || json.data || [];
            }
          } catch (e) {
            console.warn('Error loading coupons:', e);
          }
        };

        const saveNewCoupon = async () => {
          if (!newCouponForm.value.code) return;
          creatingCoupon.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/coupons', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({
                code: newCouponForm.value.code,
                discount_percent: Number(newCouponForm.value.val) || 20,
                duration_type: newCouponForm.value.duration_type || 'days',
                duration_value: Number(newCouponForm.value.duration_value) || 7,
                max_uses: Number(newCouponForm.value.max_uses) || 100
              })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || `تم حفظ وتفعيل كود الخصم (${newCouponForm.value.code}) بنجاح! ✅`);
              newCouponForm.value = { code: '', type: 'percent', val: 20, duration_type: 'days', duration_value: 7, max_uses: 100 };
              await loadSellerCoupons();
            } else {
              alert(json.message || 'فشل حفظ الكود');
            }
          } catch {
            alert('حدث خطأ أثناء حفظ الكود');
          } finally {
            creatingCoupon.value = false;
          }
        };

        const toggleCoupon = async (code) => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/coupons/toggle', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({ code })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              await loadSellerCoupons();
            }
          } catch {}
        };

        const deleteCoupon = async (code) => {
          if (!confirm(`هل أنت متأكد من حذف كود الخصم (${code})؟`)) return;
          try {
            const initData = tg?.initData || '';
            const res = await fetch(`/api/miniapp/seller/coupons/${code}`, {
              method: 'DELETE',
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.ok || json.success) {
              await loadSellerCoupons();
            }
          } catch {
            alert('تعذر حذف الكود');
          }
        };

        const loadPaymentMethods = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/payment-methods', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.methods || json.data) {
              manualPaymentMethods.value = json.methods || json.data || [];
              if (manualPaymentMethods.value.length && !selectedPaymentMethod.value) {
                selectedPaymentMethod.value = manualPaymentMethods.value[0];
              }
            }
          } catch (e) {
            console.warn('Error loading payment methods:', e);
          }
        };

        const submitManualDeposit = async () => {
          if (!manualSenderRef.value.trim()) {
            alert('يرجى إدخال رقم الهاتف أو رقم المعاملة للتحقق من التحويل');
            return;
          }
          submittingManualReceipt.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/payment-receipt/submit', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({
                method: selectedPaymentMethod.value?.name || 'Manual',
                method_id: selectedPaymentMethod.value?.id || 'manual',
                amount_usd: manualDepositAmount.value,
                sender_ref: manualSenderRef.value,
                image_url: manualReceiptUrl.value,
                notes: manualReceiptNotes.value
              })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم إرسال إشعار الدفع بنجاح! سيتم التحقق من التحويل وشحن رصيدك.');
              showDepositModal.value = false;
              manualSenderRef.value = '';
              manualReceiptUrl.value = '';
              await loadUserStatement();
            } else {
              alert(json.message || json.error || 'فشل إرسال الإشعار');
            }
          } catch {
            alert('حدث خطأ في الاتصال، يرجى المحاولة لاحقاً');
          } finally {
            submittingManualReceipt.value = false;
          }
        };

        const loadSellerReceipts = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/payment-receipts', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.receipts || json.data) {
              sellerPaymentReceipts.value = json.receipts || json.data || [];
            }
          } catch (e) {
            console.warn('Error loading seller receipts:', e);
          }
        };

        const actionSellerReceipt = async (receiptId, action) => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/payment-receipts/action', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({ receipt_id: receiptId, action })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تمت العملية بنجاح');
              await loadSellerReceipts();
            } else {
              alert(json.message || json.error || 'فشلت العملية');
            }
          } catch {
            alert('حدث خطأ أثناء معالجة الإيصال');
          }
        };

        const openGiftCard = (order) => {
          activeGiftOrder.value = order;
          showGiftCardModal.value = true;
        };

        const loadUserStatement = async () => {
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/account/statement', {
              headers: {
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.transactions || json.data) {
              userTransactions.value = json.transactions || json.data || [];
            }
          } catch (e) {
            console.warn('Error loading statement:', e);
          }
        };

        const submitProductReview = async () => {
          if (!activeProduct.value) return;
          submittingReview.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/reviews', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              },
              body: JSON.stringify({
                product_id: activeProduct.value.id,
                rating: reviewFormRating.value,
                comment: reviewFormComment.value
              })
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert('شكراً لتقييمك! تم تسجيل رأيك بنجاح ⭐');
              reviewFormComment.value = '';
            } else {
              alert(json.message || 'تم تسجيل تقييمك بنجاح');
            }
          } catch {
            alert('تم إرسال التقييم بنجاح');
          } finally {
            submittingReview.value = false;
          }
        };

        const broadcastAbandonedCart = async () => {
          abandonedCartBroadcasting.value = true;
          try {
            const initData = tg?.initData || '';
            const res = await fetch('/api/miniapp/seller/broadcast-abandoned', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-telegram-init-data': initData,
                'x-store-id': store.value?.botId || 'default'
              }
            });
            const json = await res.json();
            if (json.ok || json.success) {
              alert(json.message || 'تم إطلاق حملة استرجاع السلات المتروكة بنجاح! 📢');
            }
          } catch {
            alert('تم إطلاق حملة السلات المتروكة');
          } finally {
            abandonedCartBroadcasting.value = false;
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
          cartItems,
          showCartDrawer,
          purchaseQuantity,
          uploadingMedia,
          productMediaFileInput,
          depositingStars,
          customStarsAmount,
          isCheckingOutCart,
          isMediaVideo,
          cartTotalCount,
          cartTotalPrice,
          addToCart,
          increaseCartQty,
          decreaseCartQty,
          removeCartItem,
          checkoutCart,
          handleProductMediaUpload,
          payWithStarsAmount,
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
          initApp,
          currentCurrency,
          currentLang,
          exchangeRates,
          formatPrice,
          showWheelModal,
          spinningWheel,
          wheelRotation,
          wheelResult,
          openWheelModal,
          spinFortuneWheel,
          enteredCouponCode,
          appliedCoupon,
          applyCouponCode,
          sellerCoupons,
          newCouponForm,
          creatingCoupon,
          loadSellerCoupons,
          saveNewCoupon,
          toggleCoupon,
          deleteCoupon,
          activeDepositTab,
          manualPaymentMethods,
          selectedPaymentMethod,
          manualDepositAmount,
          manualSenderRef,
          manualReceiptUrl,
          manualReceiptNotes,
          submittingManualReceipt,
          loadPaymentMethods,
          submitManualDeposit,
          sellerPaymentReceipts,
          loadSellerReceipts,
          actionSellerReceipt,
          isGiftOrder,
          giftRecipient,
          giftMessage,
          giftTheme,
          showGiftCardModal,
          activeGiftOrder,
          openGiftCard,
          userTransactions,
          loadUserStatement,
          productReviewsList,
          reviewFormRating,
          reviewFormComment,
          submittingReview,
          submitProductReview,
          abandonedCartBroadcasting,
          broadcastAbandonedCart,
          t,
          currencyOptions,
          showGuaranteeModal,
          scrollToStatement,
          accountData,
          // Seller Edit & Reset Methods
          openEditSellerProduct,
          resetSellerProducts,
          resetSellerPrices,
          // Super Admin State & Methods
          adminActiveSubTab,
          adminProducts,
          adminBots,
          adminCategoryFilter,
          showAdminProductModal,
          adminProductForm,
          adminBroadcastMsg,
          adminBroadcastTarget,
          sendingBroadcast,
          savingAdminProduct,
          uploadingAdminMedia,
          adminMediaFileInput,
          filteredAdminProducts,
          loadAdminProducts,
          loadAdminBots,
          loadAdminData,
          openAddAdminProduct,
          openEditAdminProduct,
          addAdminRequirementPreset,
          removeAdminRequirement,
          uploadAdminImage,
          saveAdminProduct,
          deleteAdminProduct,
          sendAdminBroadcast,
          isBrowserPreview,
          switchRole,
          // Master Orders Fulfillment & Templates Center
          adminOrdersSearchQuery,
          adminOrdersStatusFilter,
          showDeliveryModal,
          deliveryTargetOrder,
          deliveryForm,
          deliveringOrder,
          showRejectModal,
          rejectTargetOrder,
          rejectReason,
          rejectingOrder,
          adminTemplates,
          filteredAdminOrdersList,
          openDeliverOrderModal,
          submitDeliveryFulfillment,
          openRejectOrderModal,
          submitOrderRejection,
          saveOrderAdminNotes,
          exportOrdersCsv,
          loadAdminTemplates,
          saveAdminTemplateConfig

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
            "frame-ancestors *;"
        ),
        "Cache-Control": "no-cache",
    }
    return web.Response(text=HTML_SHELL, headers=headers)

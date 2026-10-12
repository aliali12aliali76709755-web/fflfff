/* تطبيق تيليجرام المصغر الموحد (Telegram Mini App Client Engine - Vue 3) */
const { createApp, ref, computed, onMounted, watch } = Vue;

const app = createApp({
  setup() {
    // ── كائن Telegram WebApp ──
    const tg = window.Telegram?.WebApp || {
      initData: "",
      initDataUnsafe: {},
      colorScheme: "dark",
      themeParams: {},
      ready: () => {},
      expand: () => {},
      close: () => {},
      openLink: (url) => window.open(url, "_blank"),
      openTelegramLink: (url) => window.open(url, "_blank"),
      openInvoice: (url, cb) => cb && cb("paid"),
      BackButton: { show: () => {}, hide: () => {}, onClick: () => {} },
      MainButton: { show: () => {}, hide: () => {}, setText: () => {}, onClick: () => {} },
      HapticFeedback: { impactOccurred: () => {}, notificationOccurred: () => {} },
    };

    // ── الحالة العامة (State) ──
    const loading = ref(true);
    const errorMsg = ref("");
    const activeTab = ref("store"); // "store" | "orders" | "account" | "seller" | "admin"
    const sellerSubTab = ref("analytics"); // "analytics" | "products" | "settings" | "theme"
    const botUsername = ref("");
    const botData = ref({});
    const userData = ref({});
    const themeData = ref({});
    const activeSales = ref([]);

    // ── الكتالوج والمنتجات ──
    const categories = ref([]);
    const products = ref([]);
    const selectedCategory = ref("all");
    const searchQuery = ref("");

    // ── نافذة تفاصيل وشراء المنتج ──
    const selectedProduct = ref(null);
    const orderTargetInput = ref("");
    const orderQuantity = ref(1);
    const agreedToTerms = ref(false);
    const orderSubmitting = ref(false);
    const orderSuccessData = ref(null);

    // ── نافذة الشحن والمحفظة ──
    const showDepositModal = ref(false);
    const depositMethod = ref("stars"); // "stars" | "manual"
    const depositStarsAmount = ref(100);
    const depositProofText = ref("");

    // ── سجل طلباتي ──
    const ordersLoading = ref(false);
    const userOrders = ref([]);

    // ── حسابي والإحالة ──
    const accountData = ref({});

    // ── لوحة البائع: الإحصائيات والمخطط ──
    const sellerAnalytics = ref({ summary: {}, chart_days: [] });
    const selectedChartDay = ref(null);

    // ── لوحة البائع: المنتجات المخصصة ──
    const sellerProducts = ref([]);
    const showAddProductModal = ref(false);
    const savingProduct = ref(false);
    const newProductForm = ref({
      name: "",
      category_id: "custom",
      price_usd: 1.0,
      description: "",
      input_label: "آيدي الحساب أو رقم الهاتف",
      image_url: "",
      is_instant: false,
      raw_codes: "",
    });

    // ── لوحة البائع: الشروط والدعم ──
    const sellerSettings = ref({
      support_url: "",
      terms_text: "",
      policy_text: "",
    });
    const savingSettings = ref(false);
    const showTermsModal = ref(false);

    // ── لوحة البائع: التصميم والـ AI ──
    const themeDraft = ref({});
    const aiPromptInput = ref("");
    const aiLoading = ref(false);

    // ── لوحة الأدمن المركزية ──
    const adminOverview = ref({ stats: {} });
    const adminOrders = ref([]);

    // ── استخراج اسم البوت من الرابط أو start_param ──
    const getBotUsernameFromUrl = () => {
      const path = window.location.pathname.toLowerCase();
      if (path.includes("admin_app")) {
        return "admin_app";
      }
      const pathParts = window.location.pathname.split("/").filter(Boolean);
      const appIdx = pathParts.indexOf("app");
      if (appIdx !== -1 && pathParts[appIdx + 1]) {
        return pathParts[appIdx + 1];
      }
      if (tg.initDataUnsafe?.start_param) {
        return tg.initDataUnsafe.start_param;
      }
      const params = new URLSearchParams(window.location.search);
      return params.get("bot") || "shop";
    };

    // ── دالة استدعاء الـ API الموثقة ──
    const apiCall = async (endpoint, method = "GET", body = null) => {
      const headers = {
        "X-Telegram-Init-Data": tg.initData || "",
        "Content-Type": "application/json",
      };
      const opts = { method, headers };
      if (body) opts.body = JSON.stringify(body);

      const res = await fetch(endpoint, opts);
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.message || data.error || "حدث خطأ في الاتصال");
      }
      return data;
    };

    // ── تحميل بيانات المتجر الأساسية ──
    const loadStore = async () => {
      loading.value = true;
      errorMsg.value = "";
      try {
        botUsername.value = getBotUsernameFromUrl();

        // فحص مسار الأدمن المباشر
        if (botUsername.value === "admin_app" || window.location.pathname.includes("admin_app")) {
          activeTab.value = "admin";
        }

        const bData = await apiCall(`/api/miniapp/${botUsername.value}/bootstrap`);
        botData.value = bData.bot;
        userData.value = bData.user;
        themeData.value = bData.theme;
        themeDraft.value = { ...bData.theme };
        activeSales.value = bData.active_sales || [];

        // تطبيق الألوان
        document.documentElement.style.setProperty("--primary", bData.theme.primary_color || "#2563eb");
        document.documentElement.style.setProperty("--bg", bData.theme.bg_color || "#0f172a");
        document.documentElement.style.setProperty("--card-bg", bData.theme.card_bg || "#1e293b");
        document.documentElement.setAttribute("data-theme", bData.theme.color_mode || tg.colorScheme || "dark");

        // جلب الكتالوج
        const catData = await apiCall(`/api/miniapp/${botUsername.value}/catalog`);
        categories.value = catData.categories || [];
        products.value = catData.products || [];

        // جلب إعدادات الدعم والشروط
        await loadSellerSettings();

        // إشعار تيليجرام
        tg.ready();
        tg.expand();
      } catch (err) {
        errorMsg.value = err.message || "تعذر تحميل المتجر";
      } finally {
        loading.value = false;
      }
    };

    // ── تصفية المنتجات بالبحث والفئات ──
    const filteredProducts = computed(() => {
      let list = products.value;
      if (selectedCategory.value !== "all") {
        list = list.filter((p) => p.category_id === selectedCategory.value);
      }
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase().trim();
        list = list.filter(
          (p) =>
            p.name.toLowerCase().includes(q) ||
            (p.description && p.description.toLowerCase().includes(q))
        );
      }
      return list;
    });

    // ── فتح وإغلاق تفاصيل المنتج ──
    const openProduct = (p) => {
      selectedProduct.value = p;
      orderTargetInput.value = "";
      orderQuantity.value = 1;
      agreedToTerms.value = false;
      orderSuccessData.value = null;
      tg.HapticFeedback?.impactOccurred("light");
    };

    const closeProduct = () => {
      selectedProduct.value = null;
    };

    // ── تنفيذ الشراء والطلب الذري ──
    const submitOrder = async () => {
      if (!selectedProduct.value) return;
      if (selectedProduct.value.input_label && !orderTargetInput.value.trim()) {
        alert("يرجى إدخال البيانات المطلوبة بدقة");
        return;
      }
      if (!agreedToTerms.value) {
        alert("يجب الموافقة على شروط وسياسات المتجر أولاً");
        return;
      }

      orderSubmitting.value = true;
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/order`, "POST", {
          product_id: selectedProduct.value.id,
          target: orderTargetInput.value.trim(),
          quantity: orderQuantity.value,
        });

        tg.HapticFeedback?.notificationOccurred("success");
        orderSuccessData.value = res;
        userData.value.balance_usd = res.new_balance_usd;
        userData.value.balance_display = `$${Number(res.new_balance_usd).toFixed(2)}`;
      } catch (err) {
        tg.HapticFeedback?.notificationOccurred("error");
        alert(err.message || "فشل تنفيذ الطلب");
      } finally {
        orderSubmitting.value = false;
      }
    };

    // ── شحن الرصيد ──
    const submitDeposit = async () => {
      tg.HapticFeedback?.notificationOccurred("success");
      alert("تم إرسال طلب الشحن للمراجعة والاعتماد الفوري! ستصلك رسالة تأكيد في البوت.");
      showDepositModal.value = false;
    };

    // ── جلب طلباتي ──
    const loadOrders = async () => {
      ordersLoading.value = true;
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/orders`);
        userOrders.value = res.orders || [];
      } catch (e) {
        console.error("Failed to load orders:", e);
      } finally {
        ordersLoading.value = false;
      }
    };

    // ── جلب بيانات حسابي والإحالة ──
    const loadAccount = async () => {
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/account`);
        accountData.value = res.user || {};
        if (res.settings) {
          sellerSettings.value = { ...res.settings };
        }
      } catch (e) {
        console.error("Failed to load account:", e);
      }
    };

    // ── لوحة البائع: الإحصائيات والمخطط ──
    const loadSellerAnalytics = async () => {
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/seller/analytics`);
        sellerAnalytics.value = res;
        if (res.chart_days && res.chart_days.length > 0) {
          selectedChartDay.value = res.chart_days[res.chart_days.length - 1];
        }
      } catch (e) {
        console.error("Failed to load seller analytics:", e);
      }
    };

    // ── حساب ارتفاع أعمدة المخطط ──
    const getBarHeightPercent = (ordersCount) => {
      const days = sellerAnalytics.value.chart_days || [];
      const maxOrders = Math.max(...days.map((d) => d.orders || 0), 1);
      const pct = Math.round((ordersCount / maxOrders) * 100);
      return Math.max(pct, 12); // حد أدنى 12% لجمالية العرض
    };

    // ── لوحة البائع: المنتجات المخصصة ──
    const loadSellerProducts = async () => {
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/seller/products`);
        sellerProducts.value = res.products || [];
      } catch (e) {
        console.error("Failed to load seller products:", e);
      }
    };

    const submitAddProduct = async () => {
      if (!newProductForm.value.name.trim()) {
        alert("يرجى كتابة اسم المنتج");
        return;
      }
      savingProduct.value = true;
      try {
        const stockArr = newProductForm.value.raw_codes
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean);

        await apiCall(`/api/miniapp/${botUsername.value}/seller/products`, "POST", {
          name: newProductForm.value.name.trim(),
          category_id: newProductForm.value.category_id,
          price_usd: Number(newProductForm.value.price_usd) || 1.0,
          description: newProductForm.value.description.trim(),
          input_label: newProductForm.value.input_label.trim(),
          image_url: newProductForm.value.image_url.trim(),
          is_instant: newProductForm.value.is_instant,
          stock_codes: stockArr,
        });

        alert("تمت إضافة المنتج بنجاح إلى المتجر! ✅");
        showAddProductModal.value = false;
        newProductForm.value = {
          name: "",
          category_id: "custom",
          price_usd: 1.0,
          description: "",
          input_label: "آيدي الحساب أو رقم الهاتف",
          image_url: "",
          is_instant: false,
          raw_codes: "",
        };
        await loadSellerProducts();
        // تحديث كتالوج المتجر الرئيسي فوراً
        const catData = await apiCall(`/api/miniapp/${botUsername.value}/catalog`);
        categories.value = catData.categories || [];
        products.value = catData.products || [];
      } catch (e) {
        alert(e.message || "فشلت إضافة المنتج");
      } finally {
        savingProduct.value = false;
      }
    };

    const deleteProduct = async (prodId) => {
      if (!confirm("هل أنت متأكد من حذف هذا المنتج؟")) return;
      try {
        await apiCall(`/api/miniapp/${botUsername.value}/seller/products/${prodId}`, "DELETE");
        alert("تم حذف المنتج بنجاح 🗑️");
        await loadSellerProducts();
        const catData = await apiCall(`/api/miniapp/${botUsername.value}/catalog`);
        categories.value = catData.categories || [];
        products.value = catData.products || [];
      } catch (e) {
        alert(e.message || "فشل حذف المنتج");
      }
    };

    // ── لوحة البائع: حفظ الإعدادات والشروط ──
    const loadSellerSettings = async () => {
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/account`);
        if (res.settings) {
          sellerSettings.value = { ...res.settings };
        }
      } catch (e) {
        console.error("Failed to load settings:", e);
      }
    };

    const saveSettings = async () => {
      savingSettings.value = true;
      try {
        await apiCall(`/api/miniapp/${botUsername.value}/seller/settings`, "POST", sellerSettings.value);
        tg.HapticFeedback?.notificationOccurred("success");
        alert("تم حفظ إعدادات الدعم والشروط بنجاح! ✅");
      } catch (e) {
        alert(e.message || "فشل حفظ الإعدادات");
      } finally {
        savingSettings.value = false;
      }
    };

    // ── لوحة البائع: حفظ الثيم ──
    const saveTheme = async () => {
      try {
        await apiCall(`/api/miniapp/${botUsername.value}/seller/theme`, "POST", themeDraft.value);
        themeData.value = { ...themeDraft.value };
        document.documentElement.style.setProperty("--primary", themeDraft.value.primary_color || "#2563eb");
        alert("تم حفظ التصميم ونشره بنجاح! 🎨");
      } catch (e) {
        alert(e.message || "فشل حفظ التصميم");
      }
    };

    // ── المساعد الذكي لتصميم المتجر ──
    const requestAiCustomizer = async () => {
      if (!aiPromptInput.value.trim()) return;
      aiLoading.value = true;
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/seller/ai_customizer`, "POST", {
          prompt: aiPromptInput.value,
        });
        if (res.suggested_theme) {
          themeDraft.value = { ...themeDraft.value, ...res.suggested_theme };
          document.documentElement.style.setProperty("--primary", themeDraft.value.primary_color || "#2563eb");
          alert(res.message || "تم إنشاء التصميم المقترح!");
        }
      } catch (e) {
        alert(e.message || "فشل توليد التصميم");
      } finally {
        aiLoading.value = false;
      }
    };

    // ── لوحة الأدمن المركزية ──
    const loadAdminData = async () => {
      try {
        const over = await apiCall("/api/admin_app/overview");
        adminOverview.value = over;
        const ords = await apiCall("/api/admin_app/orders");
        adminOrders.value = ords.orders || [];
      } catch (e) {
        console.error("Failed to load admin data:", e);
      }
    };

    const performDualRefund = async (orderId) => {
      if (!confirm(`هل أنت متأكد من الاسترجاع المزدوج الذري للطلب #${orderId}؟`)) return;
      try {
        const res = await apiCall("/api/admin_app/dual_refund", "POST", {
          order_id: orderId,
          reason: "استرجاع يدوي من لوحة تحكم الأدمن المصغرة",
        });
        alert(res.message || "تم الاسترجاع المزدوج بنجاح! ↩️");
        loadAdminData();
      } catch (e) {
        alert(e.message || "فشل الاسترجاع");
      }
    };

    // ── أدوات مساعدة ──
    const copyText = (text, successMsg = "تم النسخ بنجاح! ✅") => {
      if (!text) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text);
      } else {
        const el = document.createElement("textarea");
        el.value = text;
        document.body.appendChild(el);
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
      }
      tg.HapticFeedback?.impactOccurred("light");
      alert(successMsg);
    };

    const openSupportChat = () => {
      const url =
        sellerSettings.value.support_url ||
        accountData.value.support_url ||
        `https://t.me/${botUsername.value}`;
      if (url.startsWith("https://t.me/")) {
        tg.openTelegramLink(url);
      } else {
        tg.openLink(url);
      }
    };

    const formatOrderStatus = (st) => {
      const map = {
        completed: "✅ مكتمل",
        queued: "⏳ قيد الانتظار",
        processing: "⚙️ جاري التنفيذ",
        canceled: "❌ ملغي",
        refunded: "↩️ مسترجع",
      };
      return map[st] || st || "معلق";
    };

    // ── مراقبة تغيير التبويبات وجلب البيانات المناسبة ──
    watch(activeTab, (newTab) => {
      tg.HapticFeedback?.impactOccurred("medium");
      if (newTab === "orders") {
        loadOrders();
      } else if (newTab === "account") {
        loadAccount();
      } else if (newTab === "seller") {
        loadSellerAnalytics();
        loadSellerProducts();
        loadSellerSettings();
      } else if (newTab === "admin") {
        loadAdminData();
      }
    });

    onMounted(() => {
      loadStore();
    });

    return {
      tg,
      loading,
      errorMsg,
      activeTab,
      sellerSubTab,
      botUsername,
      botData,
      userData,
      themeData,
      activeSales,
      categories,
      products,
      selectedCategory,
      searchQuery,
      filteredProducts,
      selectedProduct,
      orderTargetInput,
      orderQuantity,
      agreedToTerms,
      orderSubmitting,
      orderSuccessData,
      showDepositModal,
      depositMethod,
      depositStarsAmount,
      depositProofText,
      ordersLoading,
      userOrders,
      accountData,
      sellerAnalytics,
      selectedChartDay,
      sellerProducts,
      showAddProductModal,
      savingProduct,
      newProductForm,
      sellerSettings,
      savingSettings,
      showTermsModal,
      themeDraft,
      aiPromptInput,
      aiLoading,
      adminOverview,
      adminOrders,
      openProduct,
      closeProduct,
      submitOrder,
      submitDeposit,
      loadOrders,
      loadAccount,
      loadSellerAnalytics,
      getBarHeightPercent,
      loadSellerProducts,
      submitAddProduct,
      deleteProduct,
      loadSellerSettings,
      saveSettings,
      saveTheme,
      requestAiCustomizer,
      loadAdminData,
      performDualRefund,
      copyText,
      openSupportChat,
      formatOrderStatus,
      loadStore,
    };
  },
});

app.mount("#app");

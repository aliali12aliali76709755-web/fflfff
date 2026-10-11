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
    const activeTab = ref("store");     // "store" | "orders" | "ref" | "seller" | "admin"
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
    const activeBannerIndex = ref(0);

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

    // ── سجل الطلبات ──
    const userOrders = ref([]);

    // ── لوحة البائع وإدارة التصميم ──
    const sellerStats = ref(null);
    const themeDraft = ref({});
    const themeVersions = ref([]);
    const aiPromptInput = ref("");
    const aiLoading = ref(false);

    // ── استخراج اسم البوت من الرابط أو start_param ──
    const getBotUsernameFromUrl = () => {
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

    // ── دالة تنفيذ طلبات الـ API الموثقة ──
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

    // ── تحميل بيانات المتجر ──
    const loadStore = async () => {
      loading.value = true;
      errorMsg.value = "";
      try {
        botUsername.value = getBotUsernameFromUrl();
        const bData = await apiCall(`/api/miniapp/${botUsername.value}/bootstrap`);
        botData.value = bData.bot;
        userData.value = bData.user;
        themeData.value = bData.theme;
        themeDraft.value = { ...bData.theme };
        activeSales.value = bData.active_sales || [];

        // تطبيق ألوان التصميم
        document.documentElement.style.setProperty("--primary", bData.theme.primary_color || "#2563eb");
        document.documentElement.style.setProperty("--bg", bData.theme.bg_color || "#0f172a");
        document.documentElement.style.setProperty("--card-bg", bData.theme.card_bg || "#1e293b");
        document.documentElement.setAttribute("data-theme", bData.theme.color_mode || tg.colorScheme || "dark");

        // جلب الكتالوج
        const catData = await apiCall(`/api/miniapp/${botUsername.value}/catalog`);
        categories.value = catData.categories || [];
        products.value = catData.products || [];

        // إشعار تيليجرام باكتمال التحميل
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

    // ── فتح تفاصيل المنتج ──
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

    // ── تنفيذ الشراء والطلب ──
    const submitOrder = async () => {
      if (!selectedProduct.value) return;
      if (selectedProduct.value.input_label && !orderTargetInput.value.trim()) {
        alert("يرجى إدخال البيانات المطلوبة بدقة");
        return;
      }
      if (!agreedToTerms.value) {
        alert("يجب الموافقة على الشروط أولاً");
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
      } catch (err) {
        tg.HapticFeedback?.notificationOccurred("error");
        alert(err.message || "فشل تنفيذ الطلب");
      } finally {
        orderSubmitting.value = false;
      }
    };

    // ── شحن الرصيد ──
    const submitDeposit = async () => {
      alert("تم إرسال طلب الشحن للمراجعة الفورية");
      showDepositModal.value = false;
    };

    // ── لوحة البائع: جلب الإحصائيات ──
    const loadSellerData = async () => {
      try {
        const stats = await apiCall(`/api/miniapp/${botUsername.value}/seller/stats`);
        sellerStats.value = stats;
        const vers = await apiCall(`/api/miniapp/${botUsername.value}/seller/theme/versions`);
        themeVersions.value = vers.versions || [];
      } catch (e) {
        console.error(e);
      }
    };

    // ── لوحة البائع: حفظ التصميم ──
    const saveTheme = async () => {
      try {
        const res = await apiCall(`/api/miniapp/${botUsername.value}/seller/theme`, "POST", themeDraft.value);
        themeData.value = { ...themeDraft.value };
        alert("تم حفظ التصميم ونشره بنجاح!");
        loadSellerData();
      } catch (e) {
        alert(e.message);
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
          alert(res.message || "تم إنشاء التصميم المقترح!");
        }
      } catch (e) {
        alert(e.message);
      } finally {
        aiLoading.value = false;
      }
    };

    // ── التنقل ومراقبة التبويبات ──
    watch(activeTab, (newTab) => {
      tg.HapticFeedback?.impactOccurred("medium");
      if (newTab === "seller") {
        loadSellerData();
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
      userOrders,
      sellerStats,
      themeDraft,
      themeVersions,
      aiPromptInput,
      aiLoading,
      openProduct,
      closeProduct,
      submitOrder,
      submitDeposit,
      saveTheme,
      requestAiCustomizer,
      loadStore,
    };
  },
});

app.mount("#app");

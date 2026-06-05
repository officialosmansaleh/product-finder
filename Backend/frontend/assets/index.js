// ---------------- State ----------------
  const UI_BUILD = "2026-05-08-include-accessories-1";
  const selectedFilters = {}; // { key: Set(values as strings) }
  let hasRunSearchOnce = false;
  const $ = (id) => document.getElementById(id);
  let lastProductNameShortFacet = [];
  let productNameShortFacetReqSeq = 0;
  let lastProductNameShortFacetSignature = "";
  const PAGE_SIZE = 20;
  const MIN_SIMILAR_SCORE = 0.6;
  const FACET_VALUE_LIMIT = 200;
  const NAME_FACET_VALUE_LIMIT = 5000;
  const PRODUCT_NAME_FILTER_KEY = "product_name_short";
  const LEGACY_PRODUCT_NAME_FILTER_KEY = "name_prefix";
  const PUBLIC_QUERY_MAX_WORDS = 2;
  const PUBLIC_QUERY_MAX_CHARS = 24;
  const DATASHEET_LANGS = {
    en: { media: "1", prefix: "EN" },
    fr: { media: "2", prefix: "FR" },
    it: { media: "4", prefix: "IT" },
    es: { media: "5", prefix: "ES" },
    ru: { media: "20", prefix: "RU" },
    pl: { media: "22", prefix: "PL" },
    pt: { media: "1006", prefix: "PT" },
    cs: { media: "1002", prefix: "CS" },
    hr: { media: "1004", prefix: "HR" },
    sl: { media: "1003", prefix: "SL" },
  };
  let currentPage = 1;
  let allExactResults = [];
  let allSimilarResults = [];
  let activeResultsTab = "exact";
  let finderSortModes = { exact: "score_desc", similar: "score_desc" };
  let lastUnderstoodFilterChips = [];
  let lastUnderstoodFilterItems = [];
  let lastImportedFilterItems = [];
  let lastInterpretedSearch = null;
  let ignoredAIFilterPairs = [];
  let ignoredAIQuerySignature = "";
  const quoteCart = new Map(); // key: product_code
  const QUOTE_STORAGE_KEY = "productFinderQuoteCartV1";
  const TOOLS_STATE_KEY = "productFinderToolsStateV1";
  const COMPARE_REF_IMAGE_KEY = "productFinderCompareRefImageV1";
  const FINDER_STATE_KEY = "productFinderFinderStateV1";
  const FINDER_STATE_TTL_MS = 30 * 60 * 1000;
  const ONBOARDING_KEY = "productFinderOnboardingV1";
  const WELCOME_GATE_KEY = "productFinderWelcomeGateSeenV1";
  const UI_LANG_KEY = "productFinderUiLangV1";
  const OPTIONAL_SCRIPT_URLS = [
    "/frontend/assets/countries.js?v=2026-03-25-country-list-1",
    "/frontend/assets/quote-utils.js?v=2026-03-25-quote-modal-labels-1",
    "/frontend/assets/consent.js?v=2026-03-31-consent-analytics-1",
  ];
  const LOCAL_MANUFACTURER_LOGOS = {
    disano: "/frontend/logo-disano.webp",
    fosnova: "/frontend/logo-fosnova.webp",
  };
  const FILTER_GROUP_KEYS = {
    families: ["manufacturer", "product_family", PRODUCT_NAME_FILTER_KEY],
    protection: ["ip_rating", "ip_visible", "ip_non_visible", "ik_rating"],
    light: ["cct_k", "cri", "ugr", "power_max_w", "power_min_w", "lumen_output", "efficacy_lm_w", "beam_angle_deg"],
    electrical: ["control_protocol", "interface", "insulation_class", "surge_common_mode", "surge_differential_mode", "emergency_present", "ambient_temp_min_c", "ambient_temp_max_c"],
    mechanical: ["shape", "housing_color", "diameter", "luminaire_length", "luminaire_width", "luminaire_height"],
    quality: ["warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct"],
  };
  let pendingFinderViewState = null;
  let lastSearchCompareSpec = null;
  let optionalUiScriptsPromise = null;
  let optionalUiScriptsScheduled = false;
  let initialFacetsWarmupScheduled = false;
  let facetsHydratedAtLeastOnce = false;
  let initialFacetsLoadPromise = null;
  let welcomeGateActive = false;
  const SUPPORTED_LANGS = [
    { code: "en", label: "English" },
    { code: "it", label: "Italiano" },
    { code: "fr", label: "Français" },
    { code: "es", label: "Español" },
    { code: "pt", label: "Português" },
    { code: "ru", label: "\u0420\u0443\u0441\u0441\u043a\u0438\u0439" },
    { code: "ar", label: "\u0627\u0644\u0639\u0631\u0628\u064a\u0629" },
    { code: "pl", label: "Polski" },
    { code: "cs", label: "Ceština" },
    { code: "hr", label: "Hrvatski" },
    { code: "sl", label: "Slovenšcina" },
  ];
  const I18N = {
    en: { lang_label:"Language", title:"Laiting Workspace", tagline:"search, compare, and quote from one workspace", btn_tools:"Compare", btn_quote:"Quote cart", btn_filters:"Filters", btn_reset:"Reset", btn_search:"Search", btn_searching:"Searching...", btn_import_pdf:"Import PDF", btn_import_image:"Import Image", q_placeholder:"e.g. downlight for office, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Type your query...", sort:"Sort", exact:"Exact", similar:"Similar", prev:"Prev", next:"Next", dismiss:"Dismiss", close:"Close", quick_start:"Quick start", recovery_title:"No exact matches. Try one of these:", no_filters_selected:"No filters selected", parsed_from_query:"Parsed from query text", stats_searching:"Searching...", stats_search_failed:"Search failed", metric_latency:"Latency", metric_exact:"Exact", metric_similar:"Similar", metric_filters:"Filters", page_label:"Page", page_loading:"Page ...", toast_set_min_or_max:"Set min or max", toast_facets_failed:"Filters could not be loaded. Check backend logs.", toast_search_error:"Search failed. Check that the backend is running and reachable.", sort_score_desc:"Recommended", sort_score_asc:"Score asc", sort_name_asc:"Name A-Z", sort_name_desc:"Name Z-A", sort_code_asc:"Code A-Z", sort_code_desc:"Code Z-A", sort_price_asc:"Price low-high", sort_price_desc:"Price high-low", sort_power_asc:"Power low-high", sort_power_desc:"Power high-low", sort_efficacy_desc:"Efficiency high-low", sort_lumen_asc:"Lumens low-high", sort_lumen_desc:"Lumens high-low", filter_family:"Family", filter_manufacturer:"Manufacturer", filter_name_prefix:"Product name", filter_ip_rating:"IP total", filter_ip_visible:"IP v.l.", filter_ip_non_visible:"IP v.a.", filter_power_max_w:"Power W", filter_lumen_output:"Lumen", filter_efficacy_lm_w:"Efficacy", filter_beam_angle_deg:"Beam", filter_shape:"Shape", filter_housing_color:"Color", filter_control_protocol:"Control", filter_interface:"Interface", filter_emergency_present:"Emergency", filter_warranty_years:"Warranty", filter_lifetime_hours:"Lifetime h", filter_led_rated_life_h:"Lifetime h", filter_lumen_maintenance_pct:"Lumen maint.", filter_diameter:"Diameter", filter_luminaire_length:"Length", filter_luminaire_width:"Width", filter_luminaire_height:"Height", filter_ambient_temp_min_c:"Min temp (°C)", filter_ambient_temp_max_c:"Max temp (°C)", ai:"AI", quote_selected:"{n} selected", no_products_selected:"No products selected." },
    it: { lang_label:"Lingua", title:"Workspace Laiting", tagline:"cerca, confronta e prepara offerte in un unico spazio", btn_tools:"Confronta", btn_quote:"Carrello offerta", btn_filters:"Filtri", btn_reset:"Reset", btn_search:"Cerca", btn_searching:"Ricerca...", btn_import_pdf:"Import PDF", btn_import_image:"Importa immagine", q_placeholder:"es. downlight ufficio, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Scrivi la tua richiesta...", sort:"Ordina", exact:"Esatti", similar:"Simili", prev:"Prec", next:"Succ", dismiss:"Chiudi", close:"Chiudi", quick_start:"Avvio rapido", recovery_title:"Nessuna corrispondenza esatta. Prova una di queste:", no_filters_selected:"Nessun filtro selezionato", parsed_from_query:"Estratto dal testo query", stats_searching:"Ricerca...", stats_search_failed:"Ricerca fallita", metric_latency:"Latenza", metric_exact:"Esatti", metric_similar:"Simili", metric_filters:"Filtri", page_label:"Pagina", page_loading:"Pagina ...", toast_set_min_or_max:"Imposta minimo o massimo", toast_facets_failed:"Impossibile caricare i filtri. Controlla i log backend.", toast_search_error:"Ricerca non riuscita. Verifica che il backend sia attivo.", quote_selected:"{n} selezionati", no_products_selected:"Nessun prodotto selezionato." },
    fr: { lang_label:"Langue", title:"Recherche Produits", tagline:"exactement ce que vous cherchez", btn_tools:"Outils", btn_quote:"Devis", btn_filters:"Filtres", btn_reset:"Réinit.", btn_search:"Rechercher", btn_searching:"Recherche...", btn_import_pdf:"Import PDF", btn_import_image:"Importer Image", q_placeholder:"ex. downlight bureau, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Saisissez votre requête...", sort:"Tri", exact:"Exacts", similar:"Similaires", prev:"Préc.", next:"Suiv.", dismiss:"Fermer", close:"Fermer", quick_start:"Démarrage rapide", recovery_title:"Aucun résultat exact. Essayez :", no_filters_selected:"Aucun filtre sélectionné", parsed_from_query:"Analysé depuis la requête", stats_searching:"Recherche...", stats_search_failed:"Recherche échouée", metric_latency:"Latence", metric_exact:"Exacts", metric_similar:"Similaires", metric_filters:"Filtres", page_label:"Page", page_loading:"Page ...", toast_set_min_or_max:"Définissez min ou max", toast_facets_failed:"Échec du chargement des facettes : vérifiez les logs backend", toast_search_error:"Erreur de recherche. Vérifiez le backend et les endpoints.", quote_selected:"{n} sélectionnés", no_products_selected:"Aucun produit sélectionné." },
    es: { lang_label:"Idioma", title:"Buscador de Productos", tagline:"exactamente lo que estás buscando", btn_tools:"Herramientas", btn_quote:"Cotización", btn_filters:"Filtros", btn_reset:"Reset", btn_search:"Buscar", btn_searching:"Buscando...", btn_import_pdf:"Import PDF", btn_import_image:"Importar Imagen", q_placeholder:"p. ej. downlight oficina, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Escribe tu consulta...", sort:"Ordenar", exact:"Exactos", similar:"Similares", prev:"Ant.", next:"Sig.", dismiss:"Cerrar", close:"Cerrar", quick_start:"Inicio rápido", recovery_title:"Sin coincidencias exactas. Prueba una de estas:", no_filters_selected:"No hay filtros seleccionados", parsed_from_query:"Analizado desde la consulta", stats_searching:"Buscando...", stats_search_failed:"Búsqueda fallida", metric_latency:"Latencia", metric_exact:"Exactos", metric_similar:"Similares", metric_filters:"Filtros", page_label:"Página", page_loading:"Página ...", toast_set_min_or_max:"Define mínimo o máximo", toast_facets_failed:"Error al cargar facetas: revisa logs del backend", toast_search_error:"Error de búsqueda. Verifica backend y endpoints.", quote_selected:"{n} seleccionados", no_products_selected:"No hay productos seleccionados." },
    pt: { lang_label:"Idioma", title:"Localizador de Produtos", tagline:"exatamente o que você procura", btn_tools:"Ferramentas", btn_quote:"Cotação", btn_filters:"Filtros", btn_reset:"Reset", btn_search:"Buscar", btn_searching:"Buscando...", btn_import_pdf:"Import PDF", btn_import_image:"Importar Imagem", q_placeholder:"ex.: downlight para escritório, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Digite sua busca...", sort:"Ordenar", exact:"Exatos", similar:"Similares", prev:"Ant.", next:"Próx.", dismiss:"Fechar", close:"Fechar", quick_start:"Início rápido", recovery_title:"Sem resultados exatos. Tente uma opção:", no_filters_selected:"Nenhum filtro selecionado", parsed_from_query:"Interpretado da consulta", stats_searching:"Buscando...", stats_search_failed:"Busca falhou", metric_latency:"Latência", metric_exact:"Exatos", metric_similar:"Similares", metric_filters:"Filtros", page_label:"Página", page_loading:"Página ...", toast_set_min_or_max:"Defina mínimo ou máximo", toast_facets_failed:"Falha ao carregar facetas: verifique logs do backend", toast_search_error:"Erro na busca. Verifique backend e endpoints.", quote_selected:"{n} selecionados", no_products_selected:"Nenhum produto selecionado." },
    ru: { lang_label:"Язык", title:"Поиск продуктов", tagline:"именно то, что вы ищете", btn_tools:"Инструменты", btn_quote:"Смета", btn_filters:"Фильтры", btn_reset:"Сброс", btn_search:"Поиск", btn_searching:"Поиск...", btn_import_pdf:"Import PDF", btn_import_image:"Импорт Фото", q_placeholder:"напр. office downlight, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Введите запрос...", sort:"Сортировка", exact:"Точные", similar:"Похожие", prev:"Назад", next:"Вперед", dismiss:"Закрыть", close:"Закрыть", quick_start:"Быстрый старт", recovery_title:"Точных совпадений нет. Попробуйте:", no_filters_selected:"Фильтры не выбраны", parsed_from_query:"Распознано из текста запроса", stats_searching:"Поиск...", stats_search_failed:"Ошибка поиска", metric_latency:"Задержка", metric_exact:"Точные", metric_similar:"Похожие", metric_filters:"Фильтры", page_label:"Страница", page_loading:"Страница ...", toast_set_min_or_max:"Укажите минимум или максимум", toast_facets_failed:"Не удалось загрузить фасеты: проверьте логи backend", toast_search_error:"Ошибка поиска. Проверьте backend и endpoints.", quote_selected:"Выбрано: {n}", no_products_selected:"Нет выбранных продуктов." },
    ar: { lang_label:"اللغة", title:"الباحث عن المنتجات", tagline:"بالضبط ما تبحث عنه", btn_tools:"الأدوات", btn_quote:"عرض سعر", btn_filters:"الفلاتر", btn_reset:"إعادة ضبط", btn_search:"بحث", btn_searching:"جارٍ البحث...", btn_import_pdf:"Import PDF", btn_import_image:"استيراد صورة", q_placeholder:"مثال: downlight للمكتب UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"اكتب طلبك...", sort:"ترتيب", exact:"مطابق", similar:"مشابه", prev:"السابق", next:"التالي", dismiss:"إغلاق", close:"إغلاق", quick_start:"بدء سريع", recovery_title:"لا توجد نتائج مطابقة. جرّب أحد الخيارات:", no_filters_selected:"لا توجد فلاتر محددة", parsed_from_query:"تم التحليل من نص الطلب", stats_searching:"جارٍ البحث...", stats_search_failed:"فشل البحث", metric_latency:"الزمن", metric_exact:"مطابق", metric_similar:"مشابه", metric_filters:"الفلاتر", page_label:"الصفحة", page_loading:"الصفحة ...", toast_set_min_or_max:"حدد الحد الأدنى أو الأقصى", toast_facets_failed:"فشل تحميل الفئات: تحقق من سجلات الخادم", toast_search_error:"خطأ في البحث. تحقق من الخادم ونقاط النهاية.", quote_selected:"{n} محدد", no_products_selected:"لا توجد منتجات محددة." },
    pl: { lang_label:"Język", title:"Wyszukiwarka Produktów", tagline:"dokładnie to, czego szukasz", btn_tools:"Narzędzia", btn_quote:"Oferta", btn_filters:"Filtry", btn_reset:"Reset", btn_search:"Szukaj", btn_searching:"Szukanie...", btn_import_pdf:"Import PDF", btn_import_image:"Importuj Obraz", q_placeholder:"np. downlight do biura, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Wpisz zapytanie...", sort:"Sortuj", exact:"Dokładne", similar:"Podobne", prev:"Poprz.", next:"Nast.", dismiss:"Zamknij", close:"Zamknij", quick_start:"Szybki start", recovery_title:"Brak dokładnych trafień. Spróbuj:", no_filters_selected:"Brak wybranych filtrów", parsed_from_query:"Rozpoznano z tekstu zapytania", stats_searching:"Szukanie...", stats_search_failed:"Błąd wyszukiwania", metric_latency:"Opóźnienie", metric_exact:"Dokładne", metric_similar:"Podobne", metric_filters:"Filtry", page_label:"Strona", page_loading:"Strona ...", toast_set_min_or_max:"Ustaw minimum lub maksimum", toast_facets_failed:"Nie udało się wczytać facetów: sprawdź logi backendu", toast_search_error:"Błąd wyszukiwania. Sprawdź backend i endpointy.", quote_selected:"Wybrano: {n}", no_products_selected:"Brak wybranych produktów." },
    cs: { lang_label:"Jazyk", title:"Vyhledávač Produktů", tagline:"přesně to, co hledáte", btn_tools:"Nástroje", btn_quote:"Nabídka", btn_filters:"Filtry", btn_reset:"Reset", btn_search:"Hledat", btn_searching:"Vyhledávání...", btn_import_pdf:"Import PDF", btn_import_image:"Importovat Obrázek", q_placeholder:"např. downlight do kanceláře, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Zadejte dotaz...", sort:"Řazení", exact:"Přesné", similar:"Podobné", prev:"Před.", next:"Další", dismiss:"Zavřít", close:"Zavřít", quick_start:"Rychlý start", recovery_title:"Žádné přesné výsledky. Zkuste:", no_filters_selected:"Žádné vybrané filtry", parsed_from_query:"Rozpoznáno z textu dotazu", stats_searching:"Vyhledávání...", stats_search_failed:"Vyhledávání selhalo", metric_latency:"Latence", metric_exact:"Přesné", metric_similar:"Podobné", metric_filters:"Filtry", page_label:"Strana", page_loading:"Strana ...", toast_set_min_or_max:"Nastavte minimum nebo maximum", toast_facets_failed:"Načtení facet selhalo: zkontrolujte backend logy", toast_search_error:"Chyba vyhledávání. Zkontrolujte backend a endpointy.", quote_selected:"Vybráno: {n}", no_products_selected:"Nejsou vybrány žádné produkty." },
    hr: { lang_label:"Jezik", title:"Pretraživač Proizvoda", tagline:"točno ono što tražite", btn_tools:"Alati", btn_quote:"Ponuda", btn_filters:"Filteri", btn_reset:"Reset", btn_search:"Pretraži", btn_searching:"Pretraživanje...", btn_import_pdf:"Import PDF", btn_import_image:"Uvezi Sliku", q_placeholder:"npr. downlight za ured, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Upišite upit...", sort:"Sortiranje", exact:"Točni", similar:"Slični", prev:"Preth.", next:"Slj.", dismiss:"Zatvori", close:"Zatvori", quick_start:"Brzi početak", recovery_title:"Nema točnih rezultata. Pokušajte:", no_filters_selected:"Nema odabranih filtera", parsed_from_query:"Prepoznato iz teksta upita", stats_searching:"Pretraživanje...", stats_search_failed:"Pretraga nije uspjela", metric_latency:"Latencija", metric_exact:"Točni", metric_similar:"Slični", metric_filters:"Filteri", page_label:"Stranica", page_loading:"Stranica ...", toast_set_min_or_max:"Postavite minimum ili maksimum", toast_facets_failed:"Učitavanje facet-a nije uspjelo: provjerite backend logove", toast_search_error:"Greška pretrage. Provjerite backend i endpointe.", quote_selected:"Odabrano: {n}", no_products_selected:"Nema odabranih proizvoda." },
    sl: { lang_label:"Jezik", title:"Iskalnik Izdelkov", tagline:"točno to, kar iščete", btn_tools:"Orodja", btn_quote:"Ponudba", btn_filters:"Filtri", btn_reset:"Ponastavi", btn_search:"Išči", btn_searching:"Iskanje...", btn_import_pdf:"Import PDF", btn_import_image:"Uvozi Sliko", q_placeholder:"npr. downlight za pisarno, UGR<19, 4000K, DALI, IP54", q_mobile_placeholder:"Vnesite poizvedbo...", sort:"Razvrsti", exact:"Točni", similar:"Podobni", prev:"Prej", next:"Naprej", dismiss:"Zapri", close:"Zapri", quick_start:"Hiter začetek", recovery_title:"Ni točnih zadetkov. Poskusite:", no_filters_selected:"Ni izbranih filtrov", parsed_from_query:"Prepoznano iz besedila poizvedbe", stats_searching:"Iskanje...", stats_search_failed:"Iskanje ni uspelo", metric_latency:"Zakasnitev", metric_exact:"Točni", metric_similar:"Podobni", metric_filters:"Filtri", page_label:"Stran", page_loading:"Stran ...", toast_set_min_or_max:"Nastavite minimum ali maksimum", toast_facets_failed:"Nalaganje facetov ni uspelo: preverite backend dnevnike", toast_search_error:"Napaka pri iskanju. Preverite backend in endpoint-e.", quote_selected:"Izbrano: {n}", no_products_selected:"Ni izbranih izdelkov." },
  };
  Object.assign(I18N.en, {
    welcome:"Welcome to Laiting",
    welcome_sub:"Search, compare, and quote from one workspace.",
    next:"Next",
    catalog_search:"Catalog search",
    catalog_hint:"Search by product name, product code, or family. Use the filters below to narrow the catalog.",
    enter_search:"Use Enter to run search.",
    selected_filters:"Selected filters",
    chip_remove_hint:"Use Lock to make a parsed filter mandatory, or x to deactivate a filter. Search auto-runs.",
    product_families:"Product families",
    protection:"Protection",
    photometric:"Photometric",
    electrical:"Electrical / Control",
    mechanical:"Mechanical",
    mechanical_dimensions:"Mechanical dimensions",
    lifetime:"Lifetime",
    all:"All",
    search_select:"Search / select",
    select:"Select",
    from_to:"From / To",
    min:"min",
    max:"max",
    apply:"Apply",
    minimum_equal_better:"Minimum value (equal or better)",
    exact_cri_ph:"Exact CRI (e.g. 9)",
    exact_filter:"Exact",
    lower_bound:"Lower bound",
    upper_bound:"Upper bound",
    analyze_brief:"Analyze brief",
    group_families:"Product families",
    group_protection:"Protection",
    group_light:"Photometric",
    group_electrical:"Electrical",
    group_mechanical:"Mechanical",
    group_quality:"Lifetime",
    group_all:"All",
    filter_cct:"CCT",
    filter_cri:"CRI",
    filter_ugr:"UGR",
    filter_ik_rating:"IK",
    filter_ip_visible_full:"IP v.l. (visible)",
    filter_ip_non_visible_full:"IP v.a. (non visible)",
    filter_lumen_output_full:"Lumen output",
    filter_power_max_full:"Power max (W)",
    filter_efficacy_full:"Lumen efficacy (lm/W)",
    filter_ambient_min_full:"Min ambient temp (°C)",
    filter_ambient_max_full:"Max ambient temp (°C)",
    filter_insulation_class:"Insulation class",
    filter_surge_common_mode:"Surge common mode",
    filter_surge_differential_mode:"Surge differential mode",
    search_manufacturer_ph:"Manufacturer...",
    search_families_ph:"Search families...",
    search_product_name_ph:"Search product name...",
    search_cct_ph:"Search CCT...",
    search_cri_ph:"Search CRI...",
    search_ugr_ph:"Search UGR...",
    search_beam_ph:"Search beam angle...",
    search_color_ph:"Search color...",
    search_shape_ph:"Search shape...",
    search_ip_total_ph:"Search IP total...",
    search_ik_ph:"Search IK...",
    search_ip_visible_ph:"Search IP v.l....",
    search_ip_non_visible_ph:"Search IP v.a....",
    search_led_life_ph:"Search LED life...",
    search_warranty_ph:"Search warranty...",
    search_lumen_maintenance_ph:"Search lumen maintenance...",
    search_protocol_ph:"Search protocol...",
    search_interface_ph:"Search interface...",
    search_insulation_class_ph:"Search insulation class...",
    search_surge_ph:"Search surge...",
    search_surge_differential_ph:"Search differential surge...",
    add_to_quote:"Add to quote",
    add:"Add",
    cancel:"Cancel",
    optional_note:"Optional note",
    project_ref:"Project ref",
    remove:"Remove",
    th_code:"Code",
    th_name:"Name",
    th_qty:"Qty",
    th_notes:"Notes",
    th_project_ref:"Project Ref",
    quote_empty:"Quote cart is empty",
    need_quote_meta:"Set company and project name before export",
    quote_export:"Quote Export",
    quote_request:"Quote Request",
    company:"Company",
    project:"Project",
    exported_at:"Exported at",
    total_items:"Total items",
    popup_blocked:"Popup blocked. Enable popups for PDF export.",
    datasheet:"Datasheet",
    website:"Website",
    compare:"Compare",
    alternatives:"Alternatives",
    top_match:"Top match",
    why_it_appears:"Why it appears",
    what_differs:"What differs",
    not_available:"Not available",
    vision_guess:"Vision Guess",
    confidence:"Confidence",
    model:"Model",
    notes:"Notes",
    compare_label:"Compare",
    removed_from_comparison:"Removed {code} from comparison",
    results_summary:"Results: {exact} exact, {close} close, {broader} broader",
    open_compare_workspace:"Open compare workspace",
    clear_filters_keep_query:"Clear filters and keep the query",
    public_search_placeholder:"Search name, code, or family...",
    include_accessories:"Include accessories in search",
    save_learning:"Save learning",
    query:"Query",
    query_hint_private:"Tip: you can search by application or specs. Filters below refine results.",
    query_help_private:"Use Enter to run search. Use Ctrl+Enter (or Cmd+Enter) for a new line.",
    expand:"Expand",
    collapse:"Collapse",
    has_active_filters:"Has active filters",
    active_filter_count:"{n} active filter",
    active_filter_count_plural:"{n} active filters",
    toast_enter_search:"Please enter a search term or select at least one filter.",
    toast_save_learning_need_context:"Run a search or set filters before saving learning",
    toast_learning_saved:"Learning saved",
    toast_login_learning:"Log in to save learning",
    toast_learning_not_enabled:"Learning is not enabled for your user",
    toast_learning_failed:"Could not save learning",
    toast_select_file_first:"Select PDF and/or image first",
    select_pdf:"Select PDF",
    select_image:"Select image",
    no_file_selected:"No file selected",
    analyzing:"Analyzing...",
    saving:"Saving...",
    analyze_files:"Analyze files",
    matches_search_on:"Matches your search on {fields}.",
    close_search_on:"Close to your search on {fields}.",
    related_search_on:"Related to your search on {fields}.",
    onboarding_step_1:"1. Type a natural query like: <b>office downlight UGR&lt;19 4000K DALI</b>.",
    onboarding_step_2:"2. Add filters from the left panel to narrow exact matches.",
    onboarding_step_3:"3. Add products to <b>Quote</b> and export from the Quote page.",
  });
  Object.assign(I18N.it, {
    sort_score_desc:"Consigliati",
    sort_score_asc:"Score crescente",
    sort_name_asc:"Nome A-Z",
    sort_name_desc:"Nome Z-A",
    sort_code_asc:"Codice A-Z",
    sort_code_desc:"Codice Z-A",
    sort_price_asc:"Prezzo basso-alto",
    sort_price_desc:"Prezzo alto-basso",
    sort_power_asc:"Potenza basso-alto",
    sort_power_desc:"Potenza alto-basso",
    sort_efficacy_desc:"Efficienza alto-basso",
    sort_lumen_asc:"Lumen basso-alto",
    sort_lumen_desc:"Lumen alto-basso",
    filter_family:"Famiglia",
    filter_manufacturer:"Produttore",
    filter_name_prefix:"Nome prodotto",
    filter_ip_rating:"IP totale",
    filter_ip_visible:"IP v.l.",
    filter_ip_non_visible:"IP v.a.",
    filter_power_max_w:"Potenza W",
    filter_lumen_output:"Lumen",
    filter_efficacy_lm_w:"Efficienza",
    filter_beam_angle_deg:"Fascio",
    filter_shape:"Forma",
    filter_housing_color:"Colore",
    filter_control_protocol:"Controllo",
    filter_interface:"Interfaccia",
    filter_insulation_class:"Classe isolamento",
    filter_surge_common_mode:"Surge modo comune",
    filter_surge_differential_mode:"Surge modo differenziale",
    filter_emergency_present:"Emergenza",
    filter_warranty_years:"Garanzia",
    filter_lifetime_hours:"Vita utile h",
    filter_led_rated_life_h:"Vita LED h",
    filter_lumen_maintenance_pct:"Mantenimento lumen",
    filter_diameter:"Diametro",
    filter_luminaire_length:"Lunghezza",
    filter_luminaire_width:"Larghezza",
    filter_luminaire_height:"Altezza",
    filter_ambient_temp_min_c:"Temp min (°C)",
    filter_ambient_temp_max_c:"Temp max (°C)",
    welcome:"Benvenuto in Laiting",
    welcome_sub:"Cerca, confronta e prepara offerte da un unico workspace.",
    next:"Avanti",
    catalog_search:"Ricerca catalogo",
    catalog_hint:"Cerca per nome prodotto, codice o famiglia. Usa i filtri sotto per restringere il catalogo.",
    enter_search:"Premi Invio per cercare.",
    selected_filters:"Filtri selezionati",
    chip_remove_hint:"Usa Lock per rendere obbligatorio un filtro interpretato, oppure x per disattivarlo. La ricerca si aggiorna automaticamente.",
    product_families:"Famiglie prodotto",
    protection:"Protezione",
    photometric:"Fotometria",
    electrical:"Elettrico / Controllo",
    mechanical:"Meccanica",
    mechanical_dimensions:"Dimensioni meccaniche",
    lifetime:"Vita utile",
    all:"Tutto",
    search_select:"Cerca / seleziona",
    select:"Seleziona",
    from_to:"Da / A",
    min:"min",
    max:"max",
    apply:"Applica",
    minimum_equal_better:"Valore minimo (uguale o migliore)",
    exact_cri_ph:"CRI esatto (es. 9)",
    exact_filter:"Esatto",
    lower_bound:"Limite inferiore",
    upper_bound:"Limite superiore",
    analyze_brief:"Analizza brief",
    group_families:"Famiglie prodotto",
    group_protection:"Protezione",
    group_light:"Fotometria",
    group_electrical:"Elettrico",
    group_mechanical:"Meccanica",
    group_quality:"Vita utile",
    group_all:"Tutto",
    filter_cct:"CCT",
    filter_cri:"CRI",
    filter_ugr:"UGR",
    filter_ik_rating:"IK",
    filter_ip_visible_full:"IP v.l. (visibile)",
    filter_ip_non_visible_full:"IP v.a. (non visibile)",
    filter_lumen_output_full:"Flusso luminoso",
    filter_power_max_full:"Potenza max (W)",
    filter_efficacy_full:"Efficienza lumen (lm/W)",
    filter_ambient_min_full:"Temp ambiente min (°C)",
    filter_ambient_max_full:"Temp ambiente max (°C)",
    search_manufacturer_ph:"Produttore...",
    search_families_ph:"Cerca famiglie...",
    search_product_name_ph:"Cerca nome prodotto...",
    search_cct_ph:"Cerca CCT...",
    search_cri_ph:"Cerca CRI...",
    search_ugr_ph:"Cerca UGR...",
    search_beam_ph:"Cerca angolo fascio...",
    search_color_ph:"Cerca colore...",
    search_shape_ph:"Cerca forma...",
    search_ip_total_ph:"Cerca IP totale...",
    search_ik_ph:"Cerca IK...",
    search_ip_visible_ph:"Cerca IP v.l....",
    search_ip_non_visible_ph:"Cerca IP v.a....",
    search_led_life_ph:"Cerca vita LED...",
    search_warranty_ph:"Cerca garanzia...",
    search_lumen_maintenance_ph:"Cerca mantenimento lumen...",
    search_protocol_ph:"Cerca protocollo...",
    search_interface_ph:"Cerca interfaccia...",
    search_insulation_class_ph:"Cerca classe isolamento...",
    search_surge_ph:"Cerca surge...",
    search_surge_differential_ph:"Cerca surge differenziale...",
    add_to_quote:"Aggiungi all'offerta",
    add:"Aggiungi",
    cancel:"Annulla",
    optional_note:"Nota opzionale",
    project_ref:"Rif. progetto",
    remove:"Rimuovi",
    th_code:"Codice",
    th_name:"Nome",
    th_qty:"Qta",
    th_notes:"Note",
    th_project_ref:"Rif. progetto",
    quote_empty:"Il carrello offerta e vuoto",
    need_quote_meta:"Imposta azienda e progetto prima dell'export",
    quote_export:"Export offerta",
    quote_request:"Richiesta offerta",
    company:"Azienda",
    project:"Progetto",
    exported_at:"Esportato il",
    total_items:"Totale articoli",
    popup_blocked:"Popup bloccato. Abilita i popup per esportare il PDF.",
    datasheet:"Scheda tecnica",
    website:"Sito web",
    compare:"Confronta",
    alternatives:"Alternative",
    top_match:"Miglior risultato",
    why_it_appears:"Perche appare",
    what_differs:"Differenze",
    not_available:"Non disponibile",
    include_accessories:"Includi accessori nella ricerca",
    save_learning:"Salva apprendimento",
    query:"Query",
    query_hint_private:"Suggerimento: puoi cercare per applicazione o specifiche. I filtri sotto restringono i risultati.",
    query_help_private:"Usa Invio per cercare. Usa Ctrl+Invio (o Cmd+Invio) per andare a capo.",
    expand:"Espandi",
    collapse:"Riduci",
    has_active_filters:"Ci sono filtri attivi",
    active_filter_count:"{n} filtro attivo",
    active_filter_count_plural:"{n} filtri attivi",
    toast_enter_search:"Inserisci una ricerca o seleziona almeno un filtro.",
    toast_save_learning_need_context:"Esegui una ricerca o imposta filtri prima di salvare l'apprendimento",
    toast_learning_saved:"Apprendimento salvato",
    toast_login_learning:"Accedi per salvare l'apprendimento",
    toast_learning_not_enabled:"Apprendimento non abilitato per il tuo utente",
    toast_learning_failed:"Impossibile salvare l'apprendimento",
    toast_select_file_first:"Seleziona prima PDF e/o immagine",
    select_pdf:"Seleziona PDF",
    select_image:"Seleziona immagine",
    no_file_selected:"Nessun file selezionato",
    analyzing:"Analisi...",
    saving:"Salvataggio...",
    analyze_files:"Analizza file",
    vision_guess:"Analisi immagine",
    confidence:"Confidenza",
    model:"Modello",
    notes:"Note",
    compare_label:"Confronta",
    removed_from_comparison:"Rimosso {code} dal confronto",
    results_summary:"Risultati: {exact} esatti, {close} vicini, {broader} ampliati",
    open_compare_workspace:"Apri workspace confronto",
    clear_filters_keep_query:"Cancella filtri e mantieni la query",
    public_search_placeholder:"Cerca nome, codice o famiglia...",
    matches_search_on:"Corrisponde alla ricerca su {fields}.",
    close_search_on:"Vicino alla ricerca su {fields}.",
    related_search_on:"Collegato alla ricerca su {fields}.",
    onboarding_step_1:"1. Scrivi una query naturale, per esempio: <b>downlight ufficio UGR&lt;19 4000K DALI</b>.",
    onboarding_step_2:"2. Aggiungi filtri dal pannello sinistro per restringere i risultati esatti.",
    onboarding_step_3:"3. Aggiungi prodotti all'<b>offerta</b> ed esporta dalla pagina offerta.",
  });
  Object.assign(I18N.fr, {
    sort_score_desc:"Recommandé",
    sort_score_asc:"Score croissant",
    sort_name_asc:"Nom A-Z",
    sort_name_desc:"Nom Z-A",
    sort_code_asc:"Code A-Z",
    sort_code_desc:"Code Z-A",
    sort_price_asc:"Prix croissant",
    sort_price_desc:"Prix décroissant",
    sort_power_asc:"Puissance croissante",
    sort_power_desc:"Puissance décroissante",
    sort_efficacy_desc:"Efficacité décroissante",
    sort_lumen_asc:"Lumens croissants",
    sort_lumen_desc:"Lumens décroissants",
    filter_family:"Famille",
    filter_manufacturer:"Fabricant",
    filter_name_prefix:"Nom produit",
    filter_ip_rating:"IP total",
    filter_ip_visible:"IP v.l.",
    filter_ip_non_visible:"IP v.a.",
    filter_power_max_w:"Puissance W",
    filter_lumen_output:"Lumen",
    filter_efficacy_lm_w:"Efficacité",
    filter_beam_angle_deg:"Faisceau",
    filter_shape:"Forme",
    filter_housing_color:"Couleur",
    filter_control_protocol:"Contrôle",
    filter_interface:"Interface",
    filter_insulation_class:"Classe d'isolation",
    filter_surge_common_mode:"Surtension mode commun",
    filter_surge_differential_mode:"Surtension mode différentiel",
    filter_emergency_present:"Secours",
    filter_warranty_years:"Garantie",
    filter_lifetime_hours:"Durée de vie h",
    filter_led_rated_life_h:"Durée LED h",
    filter_lumen_maintenance_pct:"Maintien du flux",
    filter_diameter:"Diamètre",
    filter_luminaire_length:"Longueur",
    filter_luminaire_width:"Largeur",
    filter_luminaire_height:"Hauteur",
    filter_ambient_temp_min_c:"Temp min (°C)",
    filter_ambient_temp_max_c:"Temp max (°C)",
    catalog_search:"Recherche catalogue",
    catalog_hint:"Recherchez par nom produit, code ou famille. Utilisez les filtres ci-dessous pour affiner le catalogue.",
    enter_search:"Appuyez sur Entrée pour rechercher.",
    selected_filters:"Filtres sélectionnés",
    chip_remove_hint:"Utilisez Lock pour rendre un filtre interprété obligatoire, ou x pour le désactiver. La recherche se relance automatiquement.",
    product_families:"Familles de produits",
    protection:"Protection",
    photometric:"Photométrie",
    electrical:"Électrique / Contrôle",
    mechanical:"Mécanique",
    mechanical_dimensions:"Dimensions mécaniques",
    lifetime:"Durée de vie",
    all:"Tout",
    search_select:"Rechercher / sélectionner",
    select:"Sélectionner",
    from_to:"De / À",
    min:"min",
    max:"max",
    apply:"Appliquer",
    minimum_equal_better:"Valeur minimale (égale ou meilleure)",
    exact_cri_ph:"CRI exact (ex. 9)",
    exact_filter:"Exact",
    lower_bound:"Limite inférieure",
    upper_bound:"Limite supérieure",
    analyze_brief:"Analyser le brief",
    group_families:"Familles produit",
    group_protection:"Protection",
    group_light:"Photométrie",
    group_electrical:"Électrique",
    group_mechanical:"Mécanique",
    group_quality:"Durée de vie",
    group_all:"Tout",
    filter_cct:"CCT",
    filter_cri:"CRI",
    filter_ugr:"UGR",
    filter_ik_rating:"IK",
    filter_ip_visible_full:"IP v.l. (visible)",
    filter_ip_non_visible_full:"IP v.a. (non visible)",
    filter_lumen_output_full:"Flux lumineux",
    filter_power_max_full:"Puissance max (W)",
    filter_efficacy_full:"Efficacité lumineuse (lm/W)",
    filter_ambient_min_full:"Temp ambiante min (°C)",
    filter_ambient_max_full:"Temp ambiante max (°C)",
    search_manufacturer_ph:"Fabricant...",
    search_families_ph:"Rechercher familles...",
    search_product_name_ph:"Rechercher nom produit...",
    search_cct_ph:"Rechercher CCT...",
    search_cri_ph:"Rechercher CRI...",
    search_ugr_ph:"Rechercher UGR...",
    search_beam_ph:"Rechercher faisceau...",
    search_color_ph:"Rechercher couleur...",
    search_shape_ph:"Rechercher forme...",
    search_ip_total_ph:"Rechercher IP total...",
    search_ik_ph:"Rechercher IK...",
    search_ip_visible_ph:"Rechercher IP v.l....",
    search_ip_non_visible_ph:"Rechercher IP v.a....",
    search_led_life_ph:"Rechercher durée LED...",
    search_warranty_ph:"Rechercher garantie...",
    search_lumen_maintenance_ph:"Rechercher maintien flux...",
    search_protocol_ph:"Rechercher protocole...",
    search_interface_ph:"Rechercher interface...",
    search_insulation_class_ph:"Rechercher classe d'isolation...",
    search_surge_ph:"Rechercher surtension...",
    search_surge_differential_ph:"Rechercher surtension différentielle...",
    include_accessories:"Inclure les accessoires dans la recherche",
    save_learning:"Enregistrer l'apprentissage",
    query:"Requête",
    query_hint_private:"Astuce : vous pouvez rechercher par application ou spécifications. Les filtres ci-dessous affinent les résultats.",
    query_help_private:"Utilisez Entrée pour rechercher. Utilisez Ctrl+Entrée (ou Cmd+Entrée) pour une nouvelle ligne.",
    expand:"Déplier",
    collapse:"Replier",
    has_active_filters:"Des filtres sont actifs",
    active_filter_count:"{n} filtre actif",
    active_filter_count_plural:"{n} filtres actifs",
    public_search_placeholder:"Rechercher nom, code ou famille...",
    onboarding_step_1:"1. Saisissez une requête naturelle, par exemple : <b>downlight bureau UGR&lt;19 4000K DALI</b>.",
    onboarding_step_2:"2. Ajoutez des filtres depuis le panneau gauche pour affiner les correspondances exactes.",
    onboarding_step_3:"3. Ajoutez des produits au <b>devis</b> et exportez depuis la page Devis.",
    select_pdf:"Sélectionner un PDF",
    select_image:"Sélectionner une image",
    no_file_selected:"Aucun fichier sélectionné",
    matches_search_on:"Correspond à votre recherche sur {fields}.",
    close_search_on:"Proche de votre recherche sur {fields}.",
    related_search_on:"Lié à votre recherche sur {fields}.",
  });
  Object.assign(I18N.es, {
    select_pdf:"Seleccionar PDF",
    select_image:"Seleccionar imagen",
    no_file_selected:"Ningún archivo seleccionado",
  });
  Object.assign(I18N.pt, {
    select_pdf:"Selecionar PDF",
    select_image:"Selecionar imagem",
    no_file_selected:"Nenhum arquivo selecionado",
  });
  Object.assign(I18N.ru, {
    select_pdf:"Выбрать PDF",
    select_image:"Выбрать изображение",
    no_file_selected:"Файл не выбран",
  });
  Object.assign(I18N.ar, {
    select_pdf:"اختيار PDF",
    select_image:"اختيار صورة",
    no_file_selected:"لم يتم اختيار ملف",
  });
  Object.assign(I18N.pl, {
    select_pdf:"Wybierz PDF",
    select_image:"Wybierz obraz",
    no_file_selected:"Nie wybrano pliku",
  });
  Object.assign(I18N.cs, {
    select_pdf:"Vybrat PDF",
    select_image:"Vybrat obrázek",
    no_file_selected:"Není vybrán soubor",
  });
  Object.assign(I18N.hr, {
    select_pdf:"Odaberi PDF",
    select_image:"Odaberi sliku",
    no_file_selected:"Nije odabrana datoteka",
  });
  Object.assign(I18N.sl, {
    select_pdf:"Izberi PDF",
    select_image:"Izberi sliko",
    no_file_selected:"Ni izbrane datoteke",
  });
  Object.values(I18N).forEach(dict => {
    for (const [key, value] of Object.entries(I18N.en)) {
      if (dict[key] === undefined) dict[key] = value;
    }
  });
  let currentLang = "en";
  let lastMetricsSnapshot = { ms: NaN, exact: 0, similar: 0, filters: 0 };

  function runWhenBrowserIdle(task, timeout = 1200){
    if (typeof task !== "function") return;
    if ("requestIdleCallback" in window){
      window.requestIdleCallback(()=> task(), { timeout });
      return;
    }
    window.setTimeout(task, Math.min(timeout, 600));
  }

  function runAfterWindowLoad(task){
    if (typeof task !== "function") return;
    if (document.readyState === "complete"){
      task();
      return;
    }
    window.addEventListener("load", task, { once: true });
  }

  function loadScriptOnce(src){
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-optional-src="${src}"]`);
      if (existing){
        if (existing.dataset.loaded === "1") {
          resolve(existing);
          return;
        }
        existing.addEventListener("load", ()=> resolve(existing), { once: true });
        existing.addEventListener("error", ()=> reject(new Error(`Failed to load ${src}`)), { once: true });
        return;
      }
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.dataset.optionalSrc = src;
      script.addEventListener("load", ()=>{
        script.dataset.loaded = "1";
        resolve(script);
      }, { once: true });
      script.addEventListener("error", ()=> reject(new Error(`Failed to load ${src}`)), { once: true });
      document.body.appendChild(script);
    });
  }

  function loadOptionalUiScripts(){
    if (!optionalUiScriptsPromise){
      optionalUiScriptsPromise = OPTIONAL_SCRIPT_URLS
        .reduce(
          (chain, src) => chain.then(()=> loadScriptOnce(src)),
          Promise.resolve()
        )
        .catch((error)=>{
          console.debug("Optional UI scripts failed to load:", error);
        });
    }
    return optionalUiScriptsPromise;
  }

  function scheduleOptionalUiScripts(){
    if (optionalUiScriptsScheduled) return;
    optionalUiScriptsScheduled = true;
    runAfterWindowLoad(()=>{
      runWhenBrowserIdle(()=>{
        loadOptionalUiScripts();
      }, 1400);
    });
  }

  function scheduleInitialFacetsWarmup(){
    if (initialFacetsWarmupScheduled || welcomeGateActive) return;
    initialFacetsWarmupScheduled = true;
    runAfterWindowLoad(()=>{
      runWhenBrowserIdle(()=>{
        if (facetsHydratedAtLeastOnce) return;
        ensureInitialFacetsLoaded({ showErrorToast: false });
      }, 1600);
    });
  }

  function renderFinderAIStatus(interpreted){
    const mount = $("finderAiStatus");
    if (!mount) return;
    const status = String(interpreted?.ai_status || "").trim().toLowerCase();
    const note = String(interpreted?.ai_note || "").trim();
    if (!status || status === "skipped"){
      mount.style.display = "none";
      mount.innerHTML = "";
      return;
    }
    let badgeClass = "finderAiBadge";
    let label = "AI parsing off";
    if (status === "ok"){
      badgeClass += " ok";
      label = "AI parsing active";
    }else if (status === "degraded"){
      badgeClass += " warn";
      label = "AI parsing recovered";
    }else if (status === "disabled"){
      badgeClass += " warn";
      label = "AI parsing unavailable";
    }else{
      badgeClass += " bad";
      label = "AI parsing error";
    }
    mount.innerHTML = `
      <span class="${badgeClass}">${escapeHtml(label)}</span>
      ${note ? `<span class="finderAiNote">${escapeHtml(note)}</span>` : ""}
    `;
    mount.style.display = "flex";
  }

  function t(key, vars){
    const pack = I18N[currentLang] || I18N.en;
    let s = (pack && pack[key]) || I18N.en[key] || key;
    if (vars && typeof s === "string"){
      for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
    }
    return s;
  }

  function detectInitialLang(){
    try{
      const saved = String(localStorage.getItem(UI_LANG_KEY) || "").toLowerCase();
      if (SUPPORTED_LANGS.some(x => x.code === saved)) return saved;
    }catch(_e){}
    const base = String(navigator.language || "en").toLowerCase().split("-")[0];
    return SUPPORTED_LANGS.some(x => x.code === base) ? base : "en";
  }

  function toast(msg){
    const el = $("toast");
    el.textContent = msg;
    el.style.display = "block";
    clearTimeout(window.__toastT);
    window.__toastT = setTimeout(()=> el.style.display="none", 2600);
  }
  function hideVisionInfo(){
    const box = $("visionInfo");
    if (!box) return;
    box.style.display = "none";
    box.innerHTML = "";
  }
  function renderVisionInfoFromImageParse(payload){
    const box = $("visionInfo");
    if (!box) return;
    const vision = (payload && typeof payload === "object") ? (payload.vision || {}) : {};
    const confidence = String(vision.confidence || "").trim();
    const notes = String(vision.notes || "").trim();
    const model = String(vision.model || "").trim();
    const guessed = (payload && typeof payload === "object")
      ? (((payload.local && typeof payload.local === "object") ? payload.local : payload.sql) || {})
      : {};
    const chips = Object.entries(guessed || {}).map(([k, v]) =>
      `<span class="chip" data-vision-k="${escapeHtml(k)}" data-vision-v="${escapeHtml(String(v || ""))}"><b>${escapeHtml(filterDisplayLabel(k))}</b>: ${escapeHtml(String(v || ""))} x</span>`
    ).join(" ");
    if (!chips && !confidence && !notes){
      hideVisionInfo();
      return;
    }
    box.innerHTML = `
      <div class="title">${escapeHtml(t("vision_guess"))}</div>
      <div class="meta">
        ${confidence ? `<span><b>${escapeHtml(t("confidence"))}:</b> ${escapeHtml(confidence)}</span>` : ""}
        ${model ? ` ${confidence ? "|" : ""} <span><b>${escapeHtml(t("model"))}:</b> ${escapeHtml(model)}</span>` : ""}
      </div>
      ${notes ? `<div class="small" style="margin-top:4px"><b>${escapeHtml(t("notes"))}:</b> ${escapeHtml(notes)}</div>` : ""}
      ${chips ? `<div class="chips">${chips}</div>` : ""}
    `;
    box.style.display = "block";
  }
  function normalizeCode(v){
    return String(v || "").trim();
  }
  function upsertCompareCodeInToolsState(code){
    const picked = normalizeCode(code);
    if (!picked) return { ok: false, reason: "empty" };
    try{
      const raw = sessionStorage.getItem(TOOLS_STATE_KEY);
      let state = {};
      if (raw){
        try { state = JSON.parse(raw) || {}; } catch(_e){ state = {}; }
      }
      const fields = (state && typeof state.fields === "object" && state.fields) ? state.fields : {};
      const slots = [
        normalizeCode(fields.cmpA),
        normalizeCode(fields.cmpB),
        normalizeCode(fields.cmpC),
      ];
      const dupIdx = slots.findIndex(x => x.toLowerCase() === picked.toLowerCase());
      if (dupIdx >= 0) return { ok: true, reason: "duplicate", slot: dupIdx };
      const emptyIdx = slots.findIndex(x => !x);
      if (emptyIdx < 0) return { ok: false, reason: "full" };
      slots[emptyIdx] = picked;
      fields.cmpA = slots[0];
      fields.cmpB = slots[1];
      fields.cmpC = slots[2];
      state.fields = fields;
      state.ts = Date.now();
      sessionStorage.setItem(TOOLS_STATE_KEY, JSON.stringify(state));
      return { ok: true, reason: "inserted", slot: emptyIdx };
    }catch(_e){
      return { ok: false, reason: "storage" };
    }
  }
  function setCompareReferenceImageInToolsState(dataUrl){
    const img = String(dataUrl || "").trim();
    if (!img) return;
    try{
      const raw = sessionStorage.getItem(TOOLS_STATE_KEY);
      let state = {};
      if (raw){
        try { state = JSON.parse(raw) || {}; } catch(_e){ state = {}; }
      }
      state.compareReferenceImage = img;
      state.ts = Date.now();
      sessionStorage.setItem(TOOLS_STATE_KEY, JSON.stringify(state));
    }catch(_e){}
  }
  async function imageFileToDataUrlForCompare(fileObj){
    if (!fileObj) return "";
    return await new Promise((resolve) => {
      const img = new Image();
      const fr = new FileReader();
      fr.onload = () => {
        img.onload = () => {
          try{
            const maxDim = 640;
            const w = Number(img.naturalWidth || img.width || 0);
            const h = Number(img.naturalHeight || img.height || 0);
            if (!w || !h){
              resolve(String(fr.result || ""));
              return;
            }
            const scale = Math.min(1, maxDim / Math.max(w, h));
            const tw = Math.max(1, Math.round(w * scale));
            const th = Math.max(1, Math.round(h * scale));
            const canvas = document.createElement("canvas");
            canvas.width = tw;
            canvas.height = th;
            const ctx = canvas.getContext("2d");
            if (!ctx){
              resolve(String(fr.result || ""));
              return;
            }
            ctx.drawImage(img, 0, 0, tw, th);
            resolve(canvas.toDataURL("image/jpeg", 0.82));
          }catch(_e){
            resolve(String(fr.result || ""));
          }
        };
        img.onerror = () => resolve(String(fr.result || ""));
        img.src = String(fr.result || "");
      };
      fr.onerror = () => resolve("");
      fr.readAsDataURL(fileObj);
    });
  }
  function hasPendingToolsCompareState(){
    return getToolsCompareSlots().some(Boolean);
  }
  function getToolsCompareSlots(){
    try{
      const raw = sessionStorage.getItem(TOOLS_STATE_KEY);
      if (!raw) return ["", "", ""];
      const state = JSON.parse(raw) || {};
      const fields = (state && typeof state.fields === "object" && state.fields) ? state.fields : {};
      return [normalizeCode(fields.cmpA), normalizeCode(fields.cmpB), normalizeCode(fields.cmpC)];
    }catch(_e){
      return ["", "", ""];
    }
  }
  function removeCompareSlotFromToolsState(slotIdx){
    const idx = Number(slotIdx);
    if (!Number.isInteger(idx) || idx < 0 || idx > 2) return { ok: false, reason: "slot" };
    try{
      const raw = sessionStorage.getItem(TOOLS_STATE_KEY);
      if (!raw) return { ok: false, reason: "empty" };
      const state = JSON.parse(raw) || {};
      const fields = (state && typeof state.fields === "object" && state.fields) ? state.fields : {};
      const slots = [normalizeCode(fields.cmpA), normalizeCode(fields.cmpB), normalizeCode(fields.cmpC)];
      const removedCode = slots[idx];
      if (!removedCode) return { ok: false, reason: "empty" };
      slots[idx] = "";
      const compact = slots.filter(Boolean);
      while (compact.length < 3) compact.push("");
      fields.cmpA = compact[0];
      fields.cmpB = compact[1];
      fields.cmpC = compact[2];
      state.fields = fields;
      state.ts = Date.now();
      sessionStorage.setItem(TOOLS_STATE_KEY, JSON.stringify(state));
      return { ok: true, code: removedCode };
    }catch(_e){
      return { ok: false, reason: "storage" };
    }
  }
  function renderToolsComparePreview(){
    const el = $("toolsComparePreview");
    if (!el) return;
    const slots = getToolsCompareSlots();
    const codes = slots.filter(Boolean);
    if (!codes.length){
      el.style.display = "none";
      el.innerHTML = "";
      return;
    }
    const tokens = slots.map((c, idx) =>
      c ? `<span class="chip" data-cmp-slot="${idx}" data-cmp-code="${escapeHtml(c)}"><b>${escapeHtml(c)}</b> x</span>` : ""
    ).filter(Boolean).join(" ");
    el.innerHTML = `<span class="small"><b>${escapeHtml(t("compare_label"))}:</b></span> ${tokens}`;
    el.title = `Comparison sheet: ${codes.join(" | ")}`;
    el.style.display = "flex";
    Array.from(el.querySelectorAll(".chip[data-cmp-slot]")).forEach(chip=>{
      chip.addEventListener("click", ()=>{
        const idx = Number(chip.getAttribute("data-cmp-slot"));
        const code = normalizeCode(chip.getAttribute("data-cmp-code"));
        const res = removeCompareSlotFromToolsState(idx);
        if (res.ok){
          renderToolsComparePreview();
          toast(t("removed_from_comparison", { code }));
        }
      });
    });
  }

  function applyStaticTranslations(){
    updateSortOptionsForAccess();
    document.documentElement.lang = currentLang;
    document.documentElement.dir = currentLang === "ar" ? "rtl" : "ltr";
    document.title = t("title");
    const textKeyByEnglish = {
      "Welcome to Laiting":"welcome",
      "Search, compare, and quote from one workspace.":"welcome_sub",
      "Next":"next",
      "Filters":"btn_filters",
      "Catalog search":"catalog_search",
      "Search by product name, product code, or family. Use the filters below to narrow the catalog.":"catalog_hint",
      "Use Enter to run search.":"enter_search",
      "Selected filters":"selected_filters",
      "Use Lock to make a parsed filter mandatory, or x to deactivate a filter. Search auto-runs.":"chip_remove_hint",
      "Include accessories in search":"include_accessories",
      "Save learning":"save_learning",
      "Query":"query",
      "Product families":"product_families",
      "Protection":"protection",
      "Photometric":"photometric",
      "Electrical / Control":"electrical",
      "Mechanical":"mechanical",
      "Mechanical dimensions":"mechanical_dimensions",
      "Lifetime":"lifetime",
      "All":"all",
      "Search / select":"search_select",
      "Select":"select",
      "From / To":"from_to",
      "Minimum value (equal or better)":"minimum_equal_better",
      "Lower bound":"lower_bound",
      "Upper bound":"upper_bound",
      "Lumen output":"filter_lumen_output_full",
      "Power max (W)":"filter_power_max_full",
      "Lumen efficacy (lm/W)":"filter_efficacy_full",
      "CCT":"filter_cct",
      "CRI":"filter_cri",
      "UGR":"filter_ugr",
      "Beam":"filter_beam_angle_deg",
      "Color":"filter_housing_color",
      "Shape":"filter_shape",
      "IP total":"filter_ip_rating",
      "IK":"filter_ik_rating",
      "IP v.l. (visible)":"filter_ip_visible_full",
      "IP v.a. (non visible)":"filter_ip_non_visible_full",
      "Lifetime h":"filter_lifetime_hours",
      "Warranty":"filter_warranty_years",
      "Lumen maint.":"filter_lumen_maintenance_pct",
      "Control":"filter_control_protocol",
      "Interface (CP)":"filter_interface",
      "Insulation class":"filter_insulation_class",
      "Surge common mode":"filter_surge_common_mode",
      "Surge differential mode":"filter_surge_differential_mode",
      "Emergency":"filter_emergency_present",
      "Min ambient temp (°C)":"filter_ambient_min_full",
      "Max ambient temp (°C)":"filter_ambient_max_full",
      "Diameter":"filter_diameter",
      "Height":"filter_luminaire_height",
      "Length":"filter_luminaire_length",
      "Width":"filter_luminaire_width",
      "Apply":"apply",
      "Reset":"btn_reset",
      "Exact":"exact_filter",
      "Expand":"expand",
      "Collapse":"collapse",
    };
    const placeholderKeyByEnglish = {
      "Manufacturer...":"search_manufacturer_ph",
      "Search families...":"search_families_ph",
      "Search product name...":"search_product_name_ph",
      "min":"min",
      "max":"max",
      "e.g. 120":"e.g. 120",
      "Search CCT...":"search_cct_ph",
      "Search CRI...":"search_cri_ph",
      "Exact CRI (e.g. 9)":"exact_cri_ph",
      "Search UGR...":"search_ugr_ph",
      "Search beam angle...":"search_beam_ph",
      "Search color...":"search_color_ph",
      "Search shape...":"search_shape_ph",
      "Search IP total...":"search_ip_total_ph",
      "Search IK...":"search_ik_ph",
      "Search IP v.l....":"search_ip_visible_ph",
      "Search IP v.a....":"search_ip_non_visible_ph",
      "Search LED life...":"search_led_life_ph",
      "Search warranty...":"search_warranty_ph",
      "Search lumen maintenance...":"search_lumen_maintenance_ph",
      "Search protocol...":"search_protocol_ph",
      "Search interface...":"search_interface_ph",
      "Search insulation class...":"search_insulation_class_ph",
      "Search surge...":"search_surge_ph",
      "Search differential surge...":"search_surge_differential_ph",
      "e.g. -20":"e.g. -20",
      "e.g. 45":"e.g. 45",
    };
    Array.from(document.querySelectorAll(".welcomeCopy,.welcomeSub,#btnWelcomeNext,.filterPanelTitle,#finderQueryTitle,#finderQueryHint,#finderQueryHelp,.filterPanel .h,.filterPanel .filterLabel,.filterPanel .filterHint,.filterPanel .filterCardTitle,.filterPanel button,.groupBtn")).forEach(el => {
      const raw = String(el.dataset.i18nKey || "").trim();
      const key = raw || textKeyByEnglish[String(el.textContent || "").trim()];
      if (!key) return;
      el.dataset.i18nKey = key;
      el.textContent = t(key);
    });
    Array.from(document.querySelectorAll(".filterPanel input[placeholder],#q[placeholder],#qMobile[placeholder]")).forEach(el => {
      const raw = String(el.dataset.i18nPlaceholderKey || "").trim();
      const key = raw || placeholderKeyByEnglish[String(el.placeholder || "").trim()];
      if (!key) return;
      el.dataset.i18nPlaceholderKey = key;
      el.placeholder = I18N.en[key] ? t(key) : key;
    });
    const groupKeys = {
      families:"group_families",
      protection:"group_protection",
      light:"group_light",
      electrical:"group_electrical",
      mechanical:"group_mechanical",
      quality:"group_quality",
      all:"group_all",
    };
    Array.from(document.querySelectorAll(".groupBtn")).forEach(btn => {
      const key = groupKeys[String(btn.dataset.group || "")];
      if (key) btn.textContent = t(key);
    });
    const buildEl = $("buildLabel");
    if (buildEl){
      buildEl.textContent = "";
      buildEl.style.display = "none";
    }
    if ($("btnTools")){
      $("btnTools").textContent = t("btn_tools");
      $("btnTools").setAttribute("title", t("open_compare_workspace"));
      $("btnTools").setAttribute("aria-label", t("open_compare_workspace"));
    }
    if ($("btnQuote")) $("btnQuote").textContent = t("btn_quote");
    if ($("btnOpenFilters")) $("btnOpenFilters").textContent = t("btn_filters");
    if ($("btnCloseFilters")) $("btnCloseFilters").textContent = t("close");
    if ($("btnClearAll")) $("btnClearAll").textContent = t("btn_reset");
    if ($("btnFinderFilesParse")) $("btnFinderFilesParse").textContent = t("analyze_brief");
    if ($("btnSelectPdfFile")) $("btnSelectPdfFile").textContent = t("select_pdf");
    if ($("btnSelectImageFile")) $("btnSelectImageFile").textContent = t("select_image");
    if ($("btnSaveLearning")) $("btnSaveLearning").textContent = t("save_learning");
    if ($("q")) $("q").placeholder = t("q_placeholder");
    if ($("qMobile")) $("qMobile").placeholder = t("q_mobile_placeholder");
    if ($("btnPrevPage")) $("btnPrevPage").textContent = t("prev");
    if ($("btnNextPage")) $("btnNextPage").textContent = t("next");
    if ($("btnPrevPageTop")) $("btnPrevPageTop").textContent = t("prev");
    if ($("btnNextPageTop")) $("btnNextPageTop").textContent = t("next");
    if ($("btnCloseOnboarding")) $("btnCloseOnboarding").textContent = t("dismiss");
    if ($("btnImgLightboxClose")) $("btnImgLightboxClose").textContent = t("close");
    const sortLabel = document.querySelector(".resultsTop .small");
    if (sortLabel) sortLabel.textContent = t("sort");
    const recoveryTitle = document.querySelector("#recovery .recoveryTitle");
    if (recoveryTitle) recoveryTitle.textContent = t("recovery_title");
    const onbTitle = document.querySelector("#onboardingBox .onbHead .h");
    if (onbTitle) onbTitle.textContent = t("quick_start");
    const onbLines = Array.from(document.querySelectorAll("#onboardingBox .small"));
    ["onboarding_step_1","onboarding_step_2","onboarding_step_3"].forEach((key, idx) => {
      if (onbLines[idx]) onbLines[idx].innerHTML = t(key);
    });
    const sortSel = $("sortSel");
    if (sortSel){
      const map = { score_desc:"sort_score_desc", score_asc:"sort_score_asc", name_asc:"sort_name_asc", name_desc:"sort_name_desc", code_asc:"sort_code_asc", code_desc:"sort_code_desc", price_asc:"sort_price_asc", price_desc:"sort_price_desc", power_asc:"sort_power_asc", power_desc:"sort_power_desc", efficacy_desc:"sort_efficacy_desc", lumen_asc:"sort_lumen_asc", lumen_desc:"sort_lumen_desc" };
      Array.from(sortSel.options).forEach(opt => {
      const k = map[opt.value];
      if (k && I18N.en[k]) opt.textContent = t(k);
      });
    }
    updateFilePickerLabels();
  }

  function applyLanguage(){
    applyStaticTranslations();
    applyAccessModeUI();
    refreshResultsTabLabels();
    renderSelected();
    renderQuoteCart();
    renderMetrics(lastMetricsSnapshot.ms, lastMetricsSnapshot.exact, lastMetricsSnapshot.similar, lastMetricsSnapshot.filters);
  }

  function setLanguage(code){
    currentLang = SUPPORTED_LANGS.some(x => x.code === code) ? code : "en";
    try { localStorage.setItem(UI_LANG_KEY, currentLang); } catch(_e){}
    document.dispatchEvent(new CustomEvent("productfinder:language-changed", { detail: { language: currentLang } }));
    applyLanguage();
    renderPage();
  }

  function initLanguageUI(){
    currentLang = detectInitialLang();
    const mount = $("uiLangMount") || document.querySelector("header .right");
    if (!mount) return;
    Array.from(document.querySelectorAll("#uiLangWrap")).forEach(el => el.remove());
    Array.from(document.querySelectorAll("#uiLang")).forEach(el => el.remove());
    const wrap = document.createElement("div");
    wrap.id = "uiLangWrap";
    wrap.className = "row";
    wrap.style.gap = "6px";
    wrap.style.alignItems = "center";
    wrap.innerHTML = `<select id="uiLang" class="select" aria-label="Language"></select>`;
    mount.appendChild(wrap);
    const sel = $("uiLang");
    if (sel){
      sel.innerHTML = SUPPORTED_LANGS.map(l => `<option value="${l.code}">${l.label}</option>`).join("");
      sel.value = currentLang;
      sel.addEventListener("change", ()=> setLanguage(sel.value));
    }
    applyLanguage();
  }

  function setBusy(b){
    const btnRun = $("btnRun");
    if (!btnRun) return;
    btnRun.disabled = b;
    btnRun.textContent = b ? t("btn_searching") : t("btn_search");
  }

  function escapeHtml(s){
    return String(s ?? "")
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;")
      .replaceAll("'","&#039;");
  }

  function resetRangeInputs(){
    ["lumMin","lumMax","pwrMin","pwrMax","effMin","diaMin","diaMax","hMin","hMax","lMin","lMax","wMin","wMax","criExact","ambMinVal","ambMaxVal"].forEach(id => $(id).value="");
  }

  function setFiltersFromObject(filtersObj){
    for (const k of Object.keys(selectedFilters)) delete selectedFilters[k];
    for (const [k, v] of Object.entries(filtersObj || {})){
      const vals = Array.isArray(v) ? v : [v];
      selectedFilters[k] = new Set(vals.map(x => String(x)));
    }
    renderSelected();
  }

  function setQueryText(v){
    const value = String(v ?? "");
    if ($("q")) $("q").value = value;
    if ($("qMobile")) $("qMobile").value = value;
  }

  function wireQuerySync(){
    const q = $("q");
    const qMobile = $("qMobile");
    if (!q || !qMobile) return;
    let syncing = false;
    q.addEventListener("input", ()=>{
      if (syncing) return;
      syncing = true;
      qMobile.value = q.value;
      syncing = false;
    });
    qMobile.addEventListener("input", ()=>{
      if (syncing) return;
      syncing = true;
      q.value = qMobile.value;
      syncing = false;
    });
  }

  function getVisibleSimilarResults(){
    return (allSimilarResults || []).filter(h => Number(h?.score ?? 0) >= MIN_SIMILAR_SCORE);
  }

  function setResultsTab(tab, opts = {}){
    const next = (String(tab || "").toLowerCase() === "similar") ? "similar" : "exact";
    activeResultsTab = next;
    if (opts.resetPage !== false) currentPage = 1;
    const exactBtn = $("btnTabExact");
    const similarBtn = $("btnTabSimilar");
    exactBtn?.classList.toggle("active", next === "exact");
    similarBtn?.classList.toggle("active", next === "similar");
    $("exactPane")?.classList.toggle("hidden", next !== "exact");
    $("similarPane")?.classList.toggle("hidden", next !== "similar");
    syncSortSelectToActiveTab();
    if (opts.render !== false) renderPage();
  }

  function refreshResultsTabLabels(){
    const exactCount = (allExactResults || []).length;
    const similarCount = getVisibleSimilarResults().length;
    if ($("btnTabExact")) $("btnTabExact").textContent = `${t("exact")} (${exactCount})`;
    if ($("btnTabSimilar")) $("btnTabSimilar").textContent = `${t("similar")} (${similarCount})`;
  }

  function renderMetrics(ms, exactCount, similarCount, filterCount){
    const box = $("metrics");
    if (!box) return;
    lastMetricsSnapshot = { ms, exact: exactCount ?? 0, similar: similarCount ?? 0, filters: filterCount ?? 0 };
    box.innerHTML = [
      `<span class="metric">${escapeHtml(t("metric_latency"))}: ${Number.isFinite(ms) ? `${ms} ms` : "-"}</span>`,
      `<span class="metric">${escapeHtml(t("metric_exact"))}: ${exactCount ?? 0}</span>`,
      `<span class="metric">${escapeHtml(t("metric_similar"))}: ${similarCount ?? 0}</span>`,
      `<span class="metric">${escapeHtml(t("metric_filters"))}: ${filterCount ?? 0}</span>`
    ].join(" ");
  }

  function pageCountFromTotals(){
    const total = activeResultsTab === "similar"
      ? getVisibleSimilarResults().length
      : (allExactResults.length || 0);
    return Math.max(1, Math.ceil(total / PAGE_SIZE));
  }

  function showOnboardingIfNeeded(){
    const box = $("onboardingBox");
    const closeBtn = $("btnCloseOnboarding");
    if (!box || !closeBtn) return;
    const seen = localStorage.getItem(ONBOARDING_KEY) === "1";
    box.style.display = seen ? "none" : "block";
    closeBtn.addEventListener("click", ()=>{
      localStorage.setItem(ONBOARDING_KEY, "1");
      box.style.display = "none";
    });
  }

  function escapeCsv(v){
    const s = String(v ?? "");
    if (/[",\n]/.test(s)) return `"${s.replaceAll('"','""')}"`;
    return s;
  }

  function saveQuoteCart(){
    try{
      const rows = Array.from(quoteCart.values());
      const storageKey = window.ProductFinderQuoteUtils?.getQuoteCartStorageKey?.(QUOTE_STORAGE_KEY) || QUOTE_STORAGE_KEY;
      sessionStorage.setItem(storageKey, JSON.stringify(rows));
    }catch(_e){
      // ignore storage failures
    }
    updateQuoteButtonCount();
  }

  function loadQuoteCart(){
    try{
      const storageKey = window.ProductFinderQuoteUtils?.getQuoteCartStorageKey?.(QUOTE_STORAGE_KEY) || QUOTE_STORAGE_KEY;
      const raw = sessionStorage.getItem(storageKey);
      if (!raw) return;
      const rows = JSON.parse(raw);
      if (!Array.isArray(rows)) return;
      quoteCart.clear();
      for (const r of rows){
        const code = String(r?.product_code || "").trim();
        if (!code) continue;
        quoteCart.set(code, {
          product_code: code,
          product_name: String(r?.product_name || ""),
          manufacturer: String(r?.manufacturer || ""),
          qty: Math.max(1, Math.round(Number(r?.qty) || 1)),
          notes: String(r?.notes || ""),
          project_reference: String(r?.project_reference || ""),
          source: String(r?.source || ""),
          sort_order: Number.isFinite(Number(r?.sort_order)) ? Number(r.sort_order) : quoteCart.size,
          compare_sheet: (r?.compare_sheet && typeof r.compare_sheet === "object") ? r.compare_sheet : null,
        });
      }
    }catch(_e){
      // ignore storage failures
    }
    updateQuoteButtonCount();
  }

  function nextQuoteSortOrder(){
    let maxOrder = -1;
    for (const row of quoteCart.values()){
      const n = Number(row?.sort_order);
      if (Number.isFinite(n) && n > maxOrder) maxOrder = n;
    }
    return maxOrder + 1;
  }

  function getQuoteRowsInDisplayOrder(){
    return Array.from(quoteCart.values()).sort((a, b) => {
      const aOrder = Number(a?.sort_order);
      const bOrder = Number(b?.sort_order);
      if (Number.isFinite(aOrder) || Number.isFinite(bOrder)){
        return (Number.isFinite(aOrder) ? aOrder : 0) - (Number.isFinite(bOrder) ? bOrder : 0);
      }
      return String(a?.product_code || "").localeCompare(String(b?.product_code || ""));
    });
  }

  function buildComparisonSheetContext(source, hit){
    const spec = (lastSearchCompareSpec && typeof lastSearchCompareSpec === "object")
      ? JSON.parse(JSON.stringify(lastSearchCompareSpec))
      : null;
    if (!spec || !Object.keys(spec).length) return null;
    return {
      ideal_spec: spec,
      source: String(source || ""),
      query_text: getCurrentQueryText(),
      product_code: String(hit?.product_code || ""),
      product_name: String(hit?.product_name || ""),
      created_at: new Date().toISOString(),
    };
  }

  async function promptQuoteEntryData(existingRow){
    return await window.ProductFinderQuoteUtils?.promptQuoteEntry?.(existingRow, {
      title: t("add_to_quote"),
      confirmLabel: t("add"),
      cancelLabel: t("cancel"),
      projectReferencePlaceholder: "L1",
    }) || null;
  }

  function updateQuoteButtonCount(){
    const btn = $("btnQuote");
    if (!btn) return;
    const n = quoteCart.size;
    btn.textContent = n > 0 ? `${t("btn_quote")} (${n})` : t("btn_quote");
  }

  function renderQuoteCart(){
    const wrap = $("quoteTableWrap");
    const stats = $("quoteStats");
    updateQuoteButtonCount();
    if (!wrap || !stats) return;
    const rows = getQuoteRowsInDisplayOrder();
    stats.textContent = t("quote_selected", { n: rows.length });
    if (!rows.length){
      wrap.innerHTML = `<span class="small">${escapeHtml(t("no_products_selected"))}</span>`;
      return;
    }

    const disanoRows = rows.filter(r => !/fosnova/i.test(String(r.manufacturer || "")));
    const fosnovaRows = rows.filter(r => /fosnova/i.test(String(r.manufacturer || "")));

    const buildGroupTable = (title, groupRows) => {
      if (!groupRows.length) return "";
      return `
      <div style="margin-top:10px">
        <div class="h" style="margin:0 0 6px 0;font-size:13px">${escapeHtml(title)} (${groupRows.length})</div>
        <table class="quoteTable">
          <colgroup>
            <col style="width:16%">
            <col style="width:26%">
            <col style="width:10%">
            <col style="width:22%">
            <col style="width:18%">
            <col style="width:8%">
          </colgroup>
          <thead>
            <tr>
              <th>${escapeHtml(t("th_code"))}</th>
              <th>${escapeHtml(t("th_name"))}</th>
              <th>${escapeHtml(t("th_qty"))}</th>
              <th>${escapeHtml(t("th_notes"))}</th>
              <th>${escapeHtml(t("th_project_ref"))}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${groupRows.map(r => `
              <tr>
                <td>${escapeHtml(r.product_code)}</td>
                <td>${escapeHtml(r.product_name || "")}</td>
                <td><input class="qty" type="number" min="1" step="1" data-quote-code="${escapeHtml(r.product_code)}" data-field="qty" value="${escapeHtml(r.qty)}" /></td>
                <td><input type="text" data-quote-code="${escapeHtml(r.product_code)}" data-field="notes" value="${escapeHtml(r.notes || "")}" placeholder="${escapeHtml(t("optional_note"))}" /></td>
                <td><input type="text" data-quote-code="${escapeHtml(r.product_code)}" data-field="project_reference" value="${escapeHtml(r.project_reference || "")}" placeholder="${escapeHtml(t("project_ref"))}" /></td>
                <td><button class="btn secondary" style="padding:6px 8px" data-quote-remove="${escapeHtml(r.product_code)}">${escapeHtml(t("remove"))}</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>`;
    };

    wrap.innerHTML = `
      ${buildGroupTable("Disano", disanoRows)}
      ${buildGroupTable("Fosnova", fosnovaRows)}
    `;
    Array.from(wrap.querySelectorAll("input[data-quote-code]")).forEach(el => {
      el.addEventListener("input", ()=>{
        const code = el.dataset.quoteCode;
        const field = el.dataset.field;
        const row = quoteCart.get(code);
        if (!row) return;
        if (field === "qty"){
          const q = Math.max(1, Math.round(Number(el.value) || 1));
          row.qty = q;
        } else if (field === "notes"){
          row.notes = String(el.value || "");
        } else if (field === "project_reference"){
          row.project_reference = String(el.value || "");
        }
        saveQuoteCart();
      });
    });
    Array.from(wrap.querySelectorAll("button[data-quote-remove]")).forEach(btn => {
      btn.addEventListener("click", ()=>{
        const code = btn.dataset.quoteRemove;
        quoteCart.delete(code);
        saveQuoteCart();
        renderQuoteCart();
        renderPage();
      });
    });
  }

  async function toggleQuoteItem(hit, kind){
    const code = String(hit?.product_code || "").trim();
    if (!code) return;
    if (quoteCart.has(code)){
      quoteCart.delete(code);
    } else {
      const entry = await promptQuoteEntryData(null);
      if (!entry) return;
      const manufacturer = String(hit?.preview?.manufacturer || "").trim();
      quoteCart.set(code, {
        product_code: code,
        product_name: String(hit?.product_name || ""),
        manufacturer,
        qty: entry.qty,
        notes: entry.notes,
        project_reference: entry.project_reference,
        source: kind || "",
        sort_order: nextQuoteSortOrder(),
        compare_sheet: buildComparisonSheetContext(kind, hit),
      });
    }
    saveQuoteCart();
    renderQuoteCart();
    renderPage();
  }

  function exportQuoteCsv(){
    const rows = Array.from(quoteCart.values());
    if (!rows.length){ toast(t("quote_empty")); return; }
    const company = String(($("quoteCompany")?.value || "")).trim();
    const project = String(($("quoteProject")?.value || "")).trim();
    if (!company || !project){
      toast(t("need_quote_meta"));
      return;
    }
    const header = ["product_code","product_name","qty","notes","project_reference","source"];
    const lines = [
      `company,${escapeCsv(company)}`,
      `project,${escapeCsv(project)}`,
      `exported_at,${escapeCsv(new Date().toISOString())}`,
      "",
      header.join(",")
    ];
    for (const r of rows){
      lines.push([
        escapeCsv(r.product_code),
        escapeCsv(r.product_name),
        escapeCsv(r.qty),
        escapeCsv(r.notes || ""),
        escapeCsv(r.project_reference || ""),
        escapeCsv(r.source || ""),
      ].join(","));
    }
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quote_${new Date().toISOString().slice(0,19).replace(/[:T]/g,"-")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function exportQuotePdf(){
    const rows = Array.from(quoteCart.values()).sort((a,b)=> String(a.product_code).localeCompare(String(b.product_code)));
    if (!rows.length){ toast(t("quote_empty")); return; }
    const company = String(($("quoteCompany")?.value || "")).trim();
    const project = String(($("quoteProject")?.value || "")).trim();
    if (!company || !project){
      toast(t("need_quote_meta"));
      return;
    }

    const disanoRows = rows.filter(r => !/fosnova/i.test(String(r.manufacturer || "")));
    const fosnovaRows = rows.filter(r => /fosnova/i.test(String(r.manufacturer || "")));
    const exportedAt = new Date().toLocaleString();

    const buildGroup = (title, groupRows) => {
      if (!groupRows.length) return "";
      return `
        <h3>${escapeHtml(title)} (${groupRows.length})</h3>
        <table>
          <thead>
            <tr>
              <th>${escapeHtml(t("th_code"))}</th>
              <th>${escapeHtml(t("th_name"))}</th>
              <th>${escapeHtml(t("th_qty"))}</th>
              <th>${escapeHtml(t("th_notes"))}</th>
              <th>${escapeHtml(t("th_project_ref"))}</th>
            </tr>
          </thead>
          <tbody>
            ${groupRows.map(r => `
              <tr>
                <td>${escapeHtml(r.product_code)}</td>
                <td>${escapeHtml(r.product_name || "")}</td>
                <td>${escapeHtml(r.qty)}</td>
                <td>${escapeHtml(r.notes || "")}</td>
                <td>${escapeHtml(r.project_reference || "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    };

    const html = `
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(t("quote_export"))}</title>
  <style>
    body{font-family:Segoe UI,Arial,sans-serif;padding:20px;color:#111}
    h1{font-size:20px;margin:0 0 8px}
    h2{font-size:14px;margin:2px 0}
    h3{font-size:13px;margin:18px 0 6px}
    .meta{font-size:12px;color:#444;margin-bottom:12px}
    table{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px}
    th,td{border:1px solid #d1d5db;padding:6px;vertical-align:top;text-align:left}
    th{background:#f3f4f6}
    @media print{ body{padding:8px} }
  </style>
</head>
<body>
  <h1>${escapeHtml(t("quote_request"))}</h1>
  <h2>${escapeHtml(t("company"))}: ${escapeHtml(company)}</h2>
  <h2>${escapeHtml(t("project"))}: ${escapeHtml(project)}</h2>
  <div class="meta">${escapeHtml(t("exported_at"))}: ${escapeHtml(exportedAt)} | ${escapeHtml(t("total_items"))}: ${rows.length}</div>
  ${buildGroup("Disano", disanoRows)}
  ${buildGroup("Fosnova", fosnovaRows)}
</body>
</html>`;

    const win = window.open("", "_blank");
    if (!win){ toast(t("popup_blocked")); return; }
    win.document.open();
    win.document.write(html);
    win.document.close();
    setTimeout(() => {
      win.focus();
      win.print();
    }, 250);
  }

  function getCurrentPageSlice(){
    const sortedExact = sortHits(allExactResults);
    const sortedSimilar = sortHits(allSimilarResults).filter(h => Number(h?.score ?? 0) >= MIN_SIMILAR_SCORE);
    const start = (currentPage - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    return {
      exact: activeResultsTab === "exact" ? sortedExact.slice(start, end) : [],
      similar: activeResultsTab === "similar" ? sortedSimilar.slice(start, end) : []
    };
  }

  function renderPage(){
    const pages = pageCountFromTotals();
    if (currentPage > pages) currentPage = pages;
    if (currentPage < 1) currentPage = 1;
    const { exact, similar } = getCurrentPageSlice();
    refreshResultsTabLabels();
    renderHits("exact", exact, "exact");
    renderHits("similar", similar, "similar");
    $("pagerInfo").textContent = `${t("page_label")} ${currentPage}/${pages}`;
    if ($("pagerInfoTop")) $("pagerInfoTop").textContent = `${t("page_label")} ${currentPage}/${pages}`;
    $("btnPrevPage").disabled = currentPage <= 1;
    $("btnNextPage").disabled = currentPage >= pages;
    if ($("btnPrevPageTop")) $("btnPrevPageTop").disabled = currentPage <= 1;
    if ($("btnNextPageTop")) $("btnNextPageTop").disabled = currentPage >= pages;
  }

  function showRecovery(actions){
    const wrap = $("recovery");
    const box = $("recoveryActions");
    const title = wrap ? wrap.querySelector(".recoveryTitle") : null;
    if (!wrap || !box) return;
    if (!actions || !actions.length){
      wrap.style.display = "none";
      box.innerHTML = "";
      if (title) title.textContent = t("recovery_title");
      return;
    }
    const guidance = buildRecoveryGuidance(lastInterpretedSearch);
    box.innerHTML = `
      ${guidance ? `<div class="recoveryGuide">${guidance}</div>` : ""}
      <div class="recoveryButtonRow">
        ${actions.map(a => `<button class="recoveryBtn" data-action="${escapeHtml(a.id)}">${escapeHtml(a.label)}</button>`).join("")}
      </div>
    `;
    wrap.style.display = "block";
    Array.from(box.querySelectorAll("button")).forEach(btn => {
      btn.addEventListener("click", () => applyRecoveryAction(btn.dataset.action));
    });
  }

  function buildRecoveryGuidance(interpreted){
    const data = (interpreted && typeof interpreted === "object") ? interpreted : {};
    const understood = Array.isArray(data.understood_filter_items) ? data.understood_filter_items : [];
    const labels = understood
      .map(item => {
        const label = String(item?.label || item?.key || "").trim();
        const value = String(item?.value || "").trim();
        if (!label || !value) return "";
        return `${label}: ${value}`;
      })
      .filter(Boolean)
      .slice(0, 3);
    const tiers = data.result_tiers && typeof data.result_tiers === "object" ? data.result_tiers : {};
    const closeCount = Number(tiers.close || 0);
    const broaderCount = Number(tiers.broader || 0);
    const lines = [];
    if (labels.length){
      lines.push(`We looked for ${humanJoin(labels)}.`);
    }
    if (closeCount > 0 || broaderCount > 0){
      lines.push(`There ${closeCount + broaderCount === 1 ? "is" : "are"} ${closeCount} close and ${broaderCount} broader alternative${closeCount + broaderCount === 1 ? "" : "s"} below.`);
    } else if (data.search_mode_note){
      lines.push(String(data.search_mode_note).trim());
    } else {
      lines.push("Your request looks more specific than the currently available exact matches.");
    }
    const nextBest = Array.isArray(data.recovery_actions) ? data.recovery_actions[0] : null;
    if (nextBest?.label){
      lines.push(`Best next step: ${String(nextBest.label).trim()}.`);
    }
    return lines.map(line => `<div class="small">${escapeHtml(line)}</div>`).join("");
  }

  function currentSingleFilter(key){
    const set = selectedFilters[key];
    if (!set || !set.size) return null;
    return Array.from(set)[0];
  }

  function isFilterValueSelected(key, value){
    const wantedKey = String(key || "").trim();
    const wantedValue = String(value || "").trim();
    if (!wantedKey || !wantedValue) return false;
    const set = selectedFilters[wantedKey];
    if (!set || !set.size) return false;
    return Array.from(set).some(v => String(v || "").trim() === wantedValue);
  }

  function getAiFilterValue(key){
    const wanted = String(key || "").trim();
    if (!wanted) return null;
    const items = [
      ...(Array.isArray(lastImportedFilterItems) ? lastImportedFilterItems : []),
      ...(Array.isArray(lastUnderstoodFilterItems) ? lastUnderstoodFilterItems : []),
    ];
    for (const item of items){
      if (String(item?.key || "").trim() !== wanted) continue;
      const value = String(item?.value || "").trim();
      if (value) return value;
    }
    return null;
  }

  function getRecoveryFilterValue(key){
    return currentSingleFilter(key) || getAiFilterValue(key) || null;
  }

  function ignoreParsedFilters(keys){
    const wanted = new Set((Array.isArray(keys) ? keys : [keys]).map(x => String(x || "").trim()).filter(Boolean));
    if (!wanted.size) return;
    const items = Array.isArray(lastUnderstoodFilterItems) ? lastUnderstoodFilterItems : [];
    for (const item of items){
      const key = String(item?.key || "").trim();
      const value = String(item?.value || "").trim();
      if (!wanted.has(key) || !value) continue;
      const exists = ignoredAIFilterPairs.some(x => String(x.k || "") === key && String(x.v || "") === value);
      if (!exists) ignoredAIFilterPairs.push({ k: key, v: value });
    }
  }

  function toRounded(n){
    return Math.round(Number(n));
  }

  function buildRecoveryActions(){
    const out = [];
    if (getRecoveryFilterValue("ugr")) out.push({ id: "relax_ugr", label: "Allow a higher UGR" });
    if (getRecoveryFilterValue("ip_rating")) out.push({ id: "relax_ip", label: "Lower the IP requirement" });
    if (getRecoveryFilterValue("ik_rating")) out.push({ id: "relax_ik", label: "Lower the IK requirement" });
    if (getRecoveryFilterValue("power_max_w")) out.push({ id: "widen_power", label: "Widen the power range" });
    if (Object.keys(selectedFilters).length || (Array.isArray(lastUnderstoodFilterItems) && lastUnderstoodFilterItems.length)) {
      out.push({ id: "clear_filters", label: t("clear_filters_keep_query") });
    }
    return out.slice(0, 4);
  }

  function applyRecoveryAction(action){
    if (action === "relax_ugr"){
      const v = getRecoveryFilterValue("ugr") || "<=19";
      const m = String(v).match(/(\d+(?:\.\d+)?)/);
      const next = m ? Number(m[1]) + 3 : 22;
      setSingleFilter("ugr", `<=${next}`);
      ignoreParsedFilters("ugr");
      trackUsage("search_recovery_action", { action, query_text: getCurrentQueryText(), filters: buildFiltersPayload() });
      return runSearch();
    }
    if (action === "relax_ip"){
      const v = getRecoveryFilterValue("ip_rating") || ">=IP65";
      const m = String(v).toUpperCase().match(/(\d{2})/);
      if (m){
        const next = Math.max(20, Number(m[1]) - 10);
        setSingleFilter("ip_rating", `>=IP${String(next).padStart(2, "0")}`);
      }
      ignoreParsedFilters("ip_rating");
      trackUsage("search_recovery_action", { action, query_text: getCurrentQueryText(), filters: buildFiltersPayload() });
      return runSearch();
    }
    if (action === "relax_ik"){
      const v = getRecoveryFilterValue("ik_rating") || ">=IK08";
      const m = String(v).toUpperCase().match(/(\d{1,2})/);
      if (m){
        const next = Math.max(0, Number(m[1]) - 2);
        setSingleFilter("ik_rating", `>=IK${String(next).padStart(2, "0")}`);
      }
      ignoreParsedFilters("ik_rating");
      trackUsage("search_recovery_action", { action, query_text: getCurrentQueryText(), filters: buildFiltersPayload() });
      return runSearch();
    }
    if (action === "widen_power"){
      const raw = getRecoveryFilterValue("power_max_w");
      if (!raw) return runSearch();
      const s = String(raw).replace(/\s+/g, "");
      const range = s.match(/^(-?\d+(?:\.\d+)?)\-(-?\d+(?:\.\d+)?)$/);
      if (range){
        let lo = Number(range[1]);
        let hi = Number(range[2]);
        if (lo > hi) [lo, hi] = [hi, lo];
        lo = Math.max(0, lo * 0.8);
        hi = hi * 1.2;
        setSingleFilter("power_max_w", `${toRounded(lo)}-${toRounded(hi)}`);
      } else {
        const cmp = s.match(/^(>=|<=|>|<)(-?\d+(?:\.\d+)?)$/);
        if (cmp){
          const op = cmp[1];
          const num = Number(cmp[2]);
          const next = (op.includes("<")) ? num * 1.2 : num * 0.8;
          setSingleFilter("power_max_w", `${op}${toRounded(Math.max(0, next))}`);
        }
      }
      ignoreParsedFilters("power_max_w");
      trackUsage("search_recovery_action", { action, query_text: getCurrentQueryText(), filters: buildFiltersPayload() });
      return runSearch();
    }
    if (action === "clear_filters"){
      const qText = $("q").value;
      for (const k of Object.keys(selectedFilters)) delete selectedFilters[k];
      ignoredAIFilterPairs = [];
      ignoredAIQuerySignature = String(qText || "");
      ignoreParsedFilters((lastUnderstoodFilterItems || []).map(it => it?.key));
      lastImportedFilterItems = [];
      resetRangeInputs();
      renderSelected();
      $("q").value = qText;
      trackUsage("search_recovery_action", { action, query_text: getCurrentQueryText(), filters: {} });
      return runSearch();
    }
  }

  function skeletonCard(){
    return `
      <div class="hit skeleton">
        <div class="skLine w35"></div>
        <div class="skLine w60"></div>
        <div class="skLine w90"></div>
        <div class="skLine w60"></div>
      </div>
    `;
  }

  function renderLoadingState(){
    if ($("stats")) $("stats").textContent = t("stats_searching");
    if ($("interpretedLine")) $("interpretedLine").textContent = "";
    renderFinderAIStatus(null);
    if ($("understoodLine")) $("understoodLine").textContent = "";
    lastUnderstoodFilterChips = [];
    renderSelected();
    renderMetrics(NaN, 0, 0, Object.keys(buildFiltersPayload()).length);
    $("exact").innerHTML = skeletonCard() + skeletonCard();
    $("similar").innerHTML = skeletonCard() + skeletonCard();
    $("pagerInfo").textContent = t("page_loading");
    if ($("pagerInfoTop")) $("pagerInfoTop").textContent = t("page_loading");
    $("btnPrevPage").disabled = true;
    $("btnNextPage").disabled = true;
    if ($("btnPrevPageTop")) $("btnPrevPageTop").disabled = true;
    if ($("btnNextPageTop")) $("btnNextPageTop").disabled = true;
    showRecovery([]);
  }

  function applyRange(key, minId, maxId){
  const a = $(minId).value.trim();
  const b = $(maxId).value.trim();

  // remove old key values first
  if (selectedFilters[key]) selectedFilters[key].clear();

  if (a && b) addFilter(key, `${a}-${b}`);
  else if (a) addFilter(key, `>=${a}`);
  else if (b) addFilter(key, `<=${b}`);
  else toast(t("toast_set_min_or_max"));
}
  function resetRange(key, minId, maxId){
  $(minId).value = "";
  $(maxId).value = "";
  if (selectedFilters[key]) { selectedFilters[key].clear(); delete selectedFilters[key]; }
}

  function includeAccessoriesEnabled(){
    return !!$("includeAccessories")?.checked;
  }

  function buildFiltersPayload(){
    const out = {};
    for (const [k,set] of Object.entries(selectedFilters)){
      const arr = Array.from(set);
      out[k] = (arr.length===1) ? arr[0] : arr;
    }
    return out;
  }

  function buildFacetsFiltersPayload(){
    const out = buildFiltersPayload();
    // Keep these facet groups broad so users can select multiple values.
    delete out[PRODUCT_NAME_FILTER_KEY];
    delete out[LEGACY_PRODUCT_NAME_FILTER_KEY];
    delete out.cct_k;
    delete out.interface;
    return out;
  }

  function saveFinderState(){
    try{
      const state = {
        ts: Date.now(),
        q: String($("q")?.value || ""),
        filters: buildFiltersPayload(),
        include_accessories: includeAccessoriesEnabled(),
        imported_ai_items: Array.isArray(lastImportedFilterItems)
          ? lastImportedFilterItems.map(it => ({
              key: String(it?.key || ""),
              value: String(it?.value || ""),
              label: String(it?.label || ""),
              source: "import",
            }))
          : [],
        sort: normalizeSortModeForAccess($("sortSel")?.value || finderSortModes[activeResultsTab] || "score_desc"),
        sort_modes: { ...finderSortModes },
        activeTab: String(activeResultsTab || "exact"),
        currentPage: Number(currentPage || 1),
      };
      sessionStorage.setItem(FINDER_STATE_KEY, JSON.stringify(state));
    }catch(_e){}
  }

  function restoreFinderState(){
    try{
      const raw = sessionStorage.getItem(FINDER_STATE_KEY);
      if (!raw) return false;
      const state = JSON.parse(raw);
      const ts = Number(state?.ts || 0);
      if (!ts || (Date.now() - ts) > FINDER_STATE_TTL_MS){
        sessionStorage.removeItem(FINDER_STATE_KEY);
        return false;
      }
      setQueryText(String(state?.q || ""));
      const includeAccessories = $("includeAccessories");
      if (includeAccessories) includeAccessories.checked = !!state?.include_accessories;

      for (const k of Object.keys(selectedFilters)) delete selectedFilters[k];
      const fs = state?.filters && typeof state.filters === "object" ? state.filters : {};
      for (const [k, v] of Object.entries(fs)){
        const kk = (k === LEGACY_PRODUCT_NAME_FILTER_KEY) ? PRODUCT_NAME_FILTER_KEY : k;
        const arr = Array.isArray(v) ? v : [v];
        if (!selectedFilters[kk]) selectedFilters[kk] = new Set();
        arr.map(x => String(x)).forEach(one => selectedFilters[kk].add(one));
      }
      const imported = Array.isArray(state?.imported_ai_items) ? state.imported_ai_items : [];
      lastImportedFilterItems = imported.map(it => ({
        key: String(it?.key || ""),
        value: String(it?.value || ""),
        label: String(it?.label || filterDisplayLabel(String(it?.key || ""))),
        source: "import",
      })).filter(it => it.key && it.value);

      const savedSortModes = state?.sort_modes && typeof state.sort_modes === "object" ? state.sort_modes : null;
      finderSortModes = {
        exact: normalizeSortModeForAccess(savedSortModes?.exact || state?.sort || "score_desc"),
        similar: String(savedSortModes?.similar || "score_desc"),
      };
      syncSortSelectToActiveTab();
      pendingFinderViewState = {
        tab: String(state?.activeTab || "exact"),
        page: Math.max(1, Number(state?.currentPage || 1)),
      };
      renderSelected();
      return true;
    }catch(_e){
      return false;
    }
  }

  function addFilter(key, value){
    const v = String(value);
    if (!selectedFilters[key]) selectedFilters[key] = new Set();
    selectedFilters[key].add(v);
    renderSelected();
  }
  function applyParsedFiltersObject(obj, options = {}){
    const clearFirst = options.clearFirst !== false;
    if (clearFirst){
      for (const k of Object.keys(selectedFilters)) delete selectedFilters[k];
    }
    const src = (obj && typeof obj === "object" && !Array.isArray(obj)) ? obj : {};
    for (const [kRaw, vRaw] of Object.entries(src)){
      const key = String(kRaw || "").trim();
      if (!key) continue;
      const values = Array.isArray(vRaw) ? vRaw : [vRaw];
      const normalized = values.map(v => String(v ?? "").trim()).filter(Boolean);
      if (!normalized.length) continue;
      selectedFilters[key] = new Set(normalized);
    }
    renderSelected();
  }
  function setImportedAiItemsFromParsedFilters(parsed){
    const src = (parsed && typeof parsed === "object" && !Array.isArray(parsed)) ? parsed : {};
    const items = [];
    for (const [k, v] of Object.entries(src)){
      const key = String(k || "").trim();
      if (!key) continue;
      const values = Array.isArray(v) ? v : [v];
      for (const one of values){
        const value = String(one ?? "").trim();
        if (!value) continue;
        items.push({
          key,
          value,
          label: filterDisplayLabel(key),
          source: "import",
        });
      }
    }
    lastImportedFilterItems = items;
  }

  function removeVisionFilterChip(key, value){
    const box = $("visionInfo");
    if (!box) return;
    const k = String(key || "").trim();
    const v = String(value || "").trim();
    Array.from(box.querySelectorAll(".chip[data-vision-k][data-vision-v]")).forEach(chip => {
      if (String(chip.dataset.visionK || "").trim() === k && String(chip.dataset.visionV || "").trim() === v){
        chip.remove();
      }
    });
    if (!box.querySelector(".chip[data-vision-k][data-vision-v]") && !box.querySelector(".meta span") && !box.querySelector(".small")){
      hideVisionInfo();
    }
  }

  async function importFiltersFromPdf(fileObj, options = {}){
    if (!fileObj) return;
    const applyNow = options.applyNow !== false;
    const showToast = options.showToast !== false;
    const manageButton = options.manageButton !== false;
    const fd = new FormData();
    fd.append("file", fileObj, String(fileObj.name || "spec.pdf"));
    const btn = $("btnFinderFilesParse");
    const prev = btn ? btn.textContent : "";
    if (btn && manageButton){
      btn.disabled = true;
      btn.textContent = t("analyzing");
    }
    try{
      const r = await fetch("/parse-pdf", { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      const parsed = (d && (d.sql || d.local)) || {};
      const out = {
        parsed,
        raw: d,
        compareReferenceImage: String(d?.compare_reference_image || "").trim(),
      };
      if (applyNow){
        applyParsedFiltersObject(parsed, { clearFirst: true });
        setImportedAiItemsFromParsedFilters(parsed);
        if (out.compareReferenceImage){
          try { sessionStorage.setItem(COMPARE_REF_IMAGE_KEY, out.compareReferenceImage); } catch(_e){}
          setCompareReferenceImageInToolsState(out.compareReferenceImage);
        }
        hideVisionInfo();
        await runSearch();
        if (showToast) toast("PDF requirements applied to filters");
      }
      return out;
    }catch(e){
      if (showToast) toast(`Could not parse PDF: ${String(e?.message || e)}`);
      throw e;
    }finally{
      if (btn && manageButton){
        btn.disabled = false;
        btn.textContent = prev || t("analyze_files");
      }
    }
  }
  async function importFiltersFromImage(fileObj, options = {}){
    if (!fileObj) return;
    const applyNow = options.applyNow !== false;
    const showToast = options.showToast !== false;
    const manageButton = options.manageButton !== false;
    const dataUrl = await imageFileToDataUrlForCompare(fileObj);
    const fd = new FormData();
    fd.append("file", fileObj, String(fileObj.name || "fixture.jpg"));
    const btn = $("btnFinderFilesParse");
    const prev = btn ? btn.textContent : "";
    if (btn && manageButton){
      btn.disabled = true;
      btn.textContent = t("analyzing");
    }
    try{
      const r = await fetch("/parse-image", { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      const parsed = (d && (d.sql || d.local)) || {};
      const out = { parsed, raw: d, compareReferenceImage: dataUrl };
      if (applyNow){
        applyParsedFiltersObject(parsed, { clearFirst: true });
        setImportedAiItemsFromParsedFilters(parsed);
        if (dataUrl){
          try { sessionStorage.setItem(COMPARE_REF_IMAGE_KEY, dataUrl); } catch(_e){}
          setCompareReferenceImageInToolsState(dataUrl);
        }
        renderVisionInfoFromImageParse(d);
        await runSearch();
        if (showToast) toast("Image requirements applied to filters");
      }
      return out;
    }catch(e){
      if (showToast) toast(`Could not analyze image: ${String(e?.message || e)}`);
      throw e;
    }finally{
      if (btn && manageButton){
        btn.disabled = false;
        btn.textContent = prev || t("analyze_files");
      }
    }
  }
  function removeFilter(key, value){
    if (!selectedFilters[key]) return;
    selectedFilters[key].delete(String(value));
    if (selectedFilters[key].size===0) delete selectedFilters[key];
    renderSelected();
  }
  function removeImportedFilter(key, value){
    const k = String(key || "").trim();
    const v = String(value || "").trim();
    if (!k || !v) return;
    removeFilter(k, v);
    lastImportedFilterItems = (lastImportedFilterItems || []).filter(it => !(String(it?.key || "") === k && String(it?.value || "") === v));
    removeVisionFilterChip(k, v);
  }
  function setSingleFilter(key, expr){
    // for range inputs: single string expression, overwrite
    selectedFilters[key] = new Set([String(expr)]);
    renderSelected();
  }
  function clearFilterKey(key){
    delete selectedFilters[key];
    renderSelected();
  }
  function clearSearchResults(){
    allExactResults = [];
    allSimilarResults = [];
    lastInterpretedSearch = null;
    lastProductNameShortFacet = [];
    pendingFinderViewState = null;
    hasRunSearchOnce = false;
    currentPage = 1;
    setResultsTab("exact", { resetPage: true, render: false });
    renderFinderAIStatus(null);
    showRecovery([]);
    renderMetrics(NaN, 0, 0, 0);
    if ($("stats")) $("stats").textContent = "";
    if ($("interpretedLine")) $("interpretedLine").textContent = "";
    if ($("understoodLine")) $("understoodLine").textContent = "";
    renderPage();
  }
  function clearAll(){
    for (const k of Object.keys(selectedFilters)) delete selectedFilters[k];
    const includeAccessories = $("includeAccessories");
    if (includeAccessories) includeAccessories.checked = false;
    ignoredAIFilterPairs = [];
    ignoredAIQuerySignature = "";
    lastUnderstoodFilterChips = [];
    lastUnderstoodFilterItems = [];
    lastImportedFilterItems = [];
    lastInterpretedSearch = null;
    setQueryText("");
    resetRangeInputs();
    renderSelected();
    hideVisionInfo();
    clearSearchResults();
    loadFacets({ showErrorToast: false });
    saveFinderState();
  }

  function filterDisplayLabel(key){
    const k = String(key || "");
    return ({
      product_family: t("filter_family"),
      manufacturer: t("filter_manufacturer"),
      product_name_short: t("filter_name_prefix"),
      name_prefix: t("filter_name_prefix"),
      ip_rating: t("filter_ip_rating"),
      ip_visible: t("filter_ip_visible"),
      ip_non_visible: t("filter_ip_non_visible"),
      ik_rating: t("filter_ik_rating"),
      cct_k: t("filter_cct"),
      cri: t("filter_cri"),
      ugr: t("filter_ugr"),
      power_max_w: t("filter_power_max_w"),
      lumen_output: t("filter_lumen_output"),
      efficacy_lm_w: t("filter_efficacy_lm_w"),
      beam_angle_deg: t("filter_beam_angle_deg"),
      shape: t("filter_shape"),
      housing_color: t("filter_housing_color"),
      control_protocol: t("filter_control_protocol"),
      interface: t("filter_interface"),
      insulation_class: t("filter_insulation_class"),
      surge_common_mode: t("filter_surge_common_mode"),
      surge_differential_mode: t("filter_surge_differential_mode"),
      emergency_present: t("filter_emergency_present"),
      warranty_years: t("filter_warranty_years"),
      lifetime_hours: t("filter_lifetime_hours"),
      led_rated_life_h: t("filter_led_rated_life_h"),
      lumen_maintenance_pct: t("filter_lumen_maintenance_pct"),
      diameter: t("filter_diameter"),
      luminaire_length: t("filter_luminaire_length"),
      luminaire_width: t("filter_luminaire_width"),
      luminaire_height: t("filter_luminaire_height"),
      ambient_temp_min_c: t("filter_ambient_temp_min_c"),
      ambient_temp_max_c: t("filter_ambient_temp_max_c"),
    })[k] || k;
  }
  function prettyFilterLabel(key){
    const k = String(key || "").trim();
    const base = String(window.ProductFinderMeasurements?.labelForKey?.(k, filterDisplayLabel(k) || k) || filterDisplayLabel(k) || k);
    if (!base) return k;
    return base.charAt(0).toUpperCase() + base.slice(1);
  }
  function formatDeviationText(one){
    const s = String(one || "").trim();
    if (!s) return "";

    if (/^fallback:\s*strict constraints relaxed$/i.test(s)){
      return "No exact match was found, so we are showing the closest available alternatives.";
    }
    if (/^fallback:\s*text mismatch$/i.test(s)){
      return "This is a broader match related to your search.";
    }

    let m = s.match(/^([a-z0-9_]+):\s*(.+)$/i);
    if (m){
      const label = prettyFilterLabel(m[1]);
      const inner = String(m[2] || "").trim();
      const mm = inner.match(/^([a-z0-9_]+)\s+mismatch:\s*wanted='([^']*)'\s+got='([^']*)'$/i);
      if (mm){
        const displayWanted = formatSpecDisplayValue(m[1], mm[2]);
        const displayGot = formatSpecDisplayValue(m[1], mm[3]);
        return `${label}: requested '${displayWanted}', found '${displayGot}'`;
      }
      return `${label}: ${inner}`;
    }

    m = s.match(/^hard missing:\s*([a-z0-9_]+)\s*$/i);
    if (m){
      return `Required ${prettyFilterLabel(m[1])} is missing`;
    }

    m = s.match(/^hard mismatch:\s*(.+)$/i);
    if (m){
      const inner = formatDeviationText(m[1]);
      return inner ? `Required filter not matched: ${inner}` : s;
    }

    m = s.match(/^([a-z0-9_]+)\s+mismatch:\s*wanted='([^']*)'\s+got='([^']*)'$/i);
    if (m){
      return `${prettyFilterLabel(m[1])}: requested '${m[2]}', found '${m[3]}'`;
    }

    m = s.match(/^wanted\s+(\d+)\s*K\s+got\s+(\d+)\s*K$/i);
    if (m){
      return `CCT: requested ${m[1]}K, found ${m[2]}K`;
    }

    if (/wanted\s+.*IP\d{2}.*got\s+IP\d{2}/i.test(s)){
      return `IP rating: ${s}`;
    }
    if (/wanted\s+.*IK\d{2}.*got\s+IK\d{2}/i.test(s)){
      return `IK rating: ${s}`;
    }

    return s;
  }

  function resultTierLabel(hit, kind){
    const dev = Array.isArray(hit?.deviations) ? hit.deviations.map(x => String(x || "").toLowerCase()) : [];
    if (kind === "exact") return "Exact";
    if (dev.some(x => x.includes("fallback: strict constraints relaxed") || x.includes("fallback: text mismatch"))){
      return "Broader";
    }
    return "Close";
  }
  function formatMissingText(one){
    const s = String(one || "").trim();
    if (!s) return "";
    return prettyFilterLabel(s);
  }

  function aiDeviationCountForKey(key){
    const k = String(key || "").trim();
    if (!k) return 0;
    const aliases = {
      product_family: ["product_family", "family"],
      manufacturer: ["manufacturer"],
      product_name_short: ["product_name", "product_name_short", "name_prefix"],
      name_prefix: ["product_name", "product_name_short", "name_prefix"],
      ip_rating: ["ip_rating", "ip "],
      ip_visible: ["ip_visible", "ip v.l", "visible"],
      ip_non_visible: ["ip_non_visible", "ip v.a", "non-visible", "non visible"],
      ik_rating: ["ik_rating", "ik "],
      cct_k: ["cct_k", "cct"],
      cri: ["cri"],
      ugr: ["ugr"],
      power_max_w: ["power_max_w", "power"],
      lumen_output: ["lumen_output", "lumen"],
      efficacy_lm_w: ["efficacy_lm_w", "efficacy", "lm/w"],
      beam_angle_deg: ["beam_angle_deg", "beam"],
      shape: ["shape"],
      housing_color: ["housing_color", "color"],
      control_protocol: ["control_protocol", "control"],
      interface: ["interface"],
      insulation_class: ["insulation_class", "insulation class", "classe isolamento", "classe di isolamento"],
      surge_common_mode: ["surge_common_mode", "surge", "common mode", "sovratensione", "modo comune"],
      surge_differential_mode: ["surge_differential_mode", "differential mode", "modo differenziale"],
      emergency_present: ["emergency_present", "emergency"],
      warranty_years: ["warranty_years", "warranty"],
      lifetime_hours: ["lifetime_hours", "lifetime"],
      led_rated_life_h: ["led_rated_life_h", "lifetime"],
      lumen_maintenance_pct: ["lumen_maintenance_pct", "l maint", "maintenance"],
      diameter: ["diameter"],
      luminaire_length: ["luminaire_length", "length"],
      luminaire_width: ["luminaire_width", "width"],
      luminaire_height: ["luminaire_height", "height"],
      ambient_temp_min_c: ["ambient_temp_min_c", "min temp"],
      ambient_temp_max_c: ["ambient_temp_max_c", "max temp"],
    };
    const needles = aliases[k] || [k];
    const hits = [...(allExactResults || []), ...(allSimilarResults || [])];
    let count = 0;
    for (const h of hits){
      const miss = Array.isArray(h?.missing) ? h.missing.map(x => String(x || "").toLowerCase()) : [];
      if (miss.includes(k.toLowerCase())){
        count += 1;
        continue;
      }
      const dev = Array.isArray(h?.deviations) ? h.deviations.map(x => String(x || "").toLowerCase()) : [];
      if (!dev.length) continue;
      if (dev.some(d => needles.some(n => d.includes(String(n).toLowerCase())))){
        count += 1;
      }
    }
    return count;
  }

  function aiSeverityClass(count, maxCount){
    const c = Number(count || 0);
    const m = Number(maxCount || 0);
    if (c <= 0 || m <= 0) return "";
    const ratio = c / m;
    if (ratio >= 0.66) return "sev-3";
    if (ratio >= 0.33) return "sev-2";
    return "sev-1";
  }

  function renderSelected(){
    const box = $("selected");
    const normChipSig = (key, value) => `${String(key || "").trim().toLowerCase()}::${String(value || "").trim().toLowerCase()}`;
    const importedSig = new Set(
      (Array.isArray(lastImportedFilterItems) ? lastImportedFilterItems : []).map(
        it => normChipSig(it?.key, it?.value)
      )
    );
    const selectedSig = new Set();
    const chips = [];
    for (const [k,set] of Object.entries(selectedFilters)){
      for (const v of set){
        const sig = normChipSig(k, v);
        selectedSig.add(sig);
        if (importedSig.has(sig)) continue; // Show analyze-file filters as AI chips only.
        const displayLabel = window.ProductFinderMeasurements?.labelForKey?.(k, filterDisplayLabel(k)) || filterDisplayLabel(k);
        const displayValue = formatSpecDisplayValue(k, v);
        chips.push(
          `<span class="chip mandatory" data-k="${escapeHtml(k)}" data-v="${escapeHtml(v)}" title="Mandatory filter">
            <span class="chipText"><b>${escapeHtml(displayLabel)}</b>: ${escapeHtml(displayValue)}</span>
            <span class="chipState">Mandatory</span>
            <button class="chipBtn" type="button" data-chip-action="remove" aria-label="Deactivate filter">x</button>
          </span>`
        );
      }
    }
    const importedItems = (Array.isArray(lastImportedFilterItems) ? lastImportedFilterItems : []).filter(it => {
      const key = String(it?.key || "").trim();
      const val = String(it?.value || "").trim();
      return key && val && selectedSig.has(normChipSig(key, val));
    });
    const aiItemsRaw = importedItems.concat(Array.isArray(lastUnderstoodFilterItems) ? lastUnderstoodFilterItems : []);
    const aiSeen = new Set();
    const aiItems = aiItemsRaw.filter(it => {
      const key = String(it?.key || "").trim();
      const val = String(it?.value || "").trim();
      const sig = normChipSig(key, val);
      const isImport = String(it?.source || "").trim().toLowerCase() === "import";
      if (!key || !val || aiSeen.has(sig) || (!isImport && selectedSig.has(sig))) return false;
      aiSeen.add(sig);
      return true;
    });
    const aiCounts = aiItems.map(it => aiDeviationCountForKey(String(it?.key || "")));
    const maxAiCount = aiCounts.length ? Math.max(...aiCounts) : 0;
    const aiChips = aiItems.length
      ? aiItems.map((it, idx) => {
          const cnt = Number(aiCounts[idx] || 0);
          const sev = aiSeverityClass(cnt, maxAiCount);
          const title = `${t("parsed_from_query")} | deviations: ${cnt}`;
          const key = String(it.key || "");
          const displayLabel = window.ProductFinderMeasurements?.labelForKey?.(key, String(it.label || it.key || "")) || String(it.label || it.key || "");
          const displayValue = formatSpecDisplayValue(key, String(it.value || ""));
          return `<span class="chip ai ${sev}" data-ai-k="${escapeHtml(key)}" data-ai-v="${escapeHtml(String(it.value || ""))}" data-ai-src="${escapeHtml(String(it.source || "query"))}" title="${escapeHtml(title)}">
            <span class="chipText"><b>${escapeHtml(t("ai"))}</b>: ${escapeHtml(displayLabel)}: ${escapeHtml(displayValue)} ${cnt > 0 ? `(${cnt})` : ""}</span>
            <button class="chipBtn lock" type="button" data-chip-action="mandatory" aria-label="Make filter mandatory">Lock</button>
            <button class="chipBtn" type="button" data-chip-action="ignore" aria-label="Deactivate filter">x</button>
          </span>`;
        }
        )
      : (lastUnderstoodFilterChips || []).map(chipText =>
          `<span class="chip ai" title="${escapeHtml(t("parsed_from_query"))}"><b>${escapeHtml(t("ai"))}</b>: ${escapeHtml(chipText)}</span>`
        );
    box.innerHTML = chips.concat(aiChips).join(" ") || `<span class="small">${escapeHtml(t("no_filters_selected"))}</span>`;
    refreshGroupButtonsState();
  }

  function setFilterGroup(group){
    const blocks = Array.from(document.querySelectorAll(".filterGroup"));
    const buttons = Array.from(document.querySelectorAll(".groupBtn"));
    const g = String(group || "all").toLowerCase();
    const setCollapsedState = (el, collapsed) => {
      el.classList.toggle("collapsed", !!collapsed);
      const btn = el.querySelector(".groupCollapseBtn");
      if (btn){
        btn.textContent = collapsed ? t("expand") : t("collapse");
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      }
    };
    blocks.forEach(el => {
      const mine = String(el.dataset.group || "").toLowerCase();
      const show = (g === "all" || mine === g);
      el.classList.toggle("hidden", !show);
      if (show && g !== "all"){
        // Clicking a specific tab auto-expands that group.
        // "All" keeps current collapse state.
        setCollapsedState(el, false);
      }
    });
    buttons.forEach(btn => {
      btn.classList.toggle("active", String(btn.dataset.group || "").toLowerCase() === g);
    });
    refreshGroupButtonsState();
  }

  function refreshGroupButtonsState(){
    const activeCountByGroup = {};
    for (const [group, keys] of Object.entries(FILTER_GROUP_KEYS)){
      let count = 0;
      for (const k of keys){
        const s = selectedFilters[k];
        if (s && s.size) count += s.size;
      }
      activeCountByGroup[group] = count;
    }
    const anyActive = Object.values(activeCountByGroup).some(n => Number(n) > 0);
    Array.from(document.querySelectorAll(".groupBtn")).forEach(btn => {
      const g = String(btn.dataset.group || "").toLowerCase();
      const count = g === "all" ? (anyActive ? 1 : 0) : Number(activeCountByGroup[g] || 0);
      btn.classList.toggle("hasFilters", count > 0);
      if (count > 0){
        btn.title = g === "all"
          ? t("has_active_filters")
          : t(count === 1 ? "active_filter_count" : "active_filter_count_plural", { n: count });
      } else {
        btn.removeAttribute("title");
      }
    });
  }

  function wireGroupNav(){
    Array.from(document.querySelectorAll(".groupBtn")).forEach(btn => {
      btn.addEventListener("click", () => {
        setFilterGroup(btn.dataset.group || "all");
      });
    });
    setFilterGroup("all");
  }

  function wireGroupCollapsers(){
    const groups = Array.from(document.querySelectorAll(".filterGroup"));
    groups.forEach(group => {
      if (group.dataset.collapseWired === "1") return;
      const firstHeader = Array.from(group.children).find(el => el.classList?.contains("h"));
      if (!firstHeader) return;

      const head = document.createElement("div");
      head.className = "filterGroupHead";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "groupCollapseBtn";
      btn.textContent = t("expand");
      btn.setAttribute("aria-expanded", "false");

      group.insertBefore(head, firstHeader);
      head.appendChild(firstHeader);
      head.appendChild(btn);

      btn.addEventListener("click", () => {
        const collapsed = group.classList.toggle("collapsed");
        btn.textContent = collapsed ? t("expand") : t("collapse");
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });

      // Default collapsed state.
      group.classList.add("collapsed");

      group.dataset.collapseWired = "1";
    });
  }

  // --------------- Range helpers ----------------
  function buildRangeExpr(minVal, maxVal){
    const a = Number(minVal);
    const b = Number(maxVal);
    const hasA = Number.isFinite(a) && String(minVal).trim() !== "";
    const hasB = Number.isFinite(b) && String(maxVal).trim() !== "";
    if (!hasA && !hasB) return null;
    if (hasA && hasB){
      const lo = Math.min(a,b);
      const hi = Math.max(a,b);
      return `${lo}-${hi}`;
    }
    if (hasA) return `>=${a}`;
    return `<=${b}`;
  }

  function wireRanges(){
    $("lumApply").addEventListener("click", ()=>{
      const expr = buildRangeExpr($("lumMin").value, $("lumMax").value);
      if (!expr){ toast("Set lumen min/max first"); return; }
      setSingleFilter("lumen_output", expr);
      runSearch();
    });
    $("lumReset").addEventListener("click", ()=>{
      $("lumMin").value=""; $("lumMax").value="";
      clearFilterKey("lumen_output");
      runSearch();
    });

    $("pwrApply").addEventListener("click", ()=>{
      const expr = buildRangeExpr($("pwrMin").value, $("pwrMax").value);
      if (!expr){ toast("Set power min/max first"); return; }
      setSingleFilter("power_max_w", expr);
      runSearch();
    });
    $("pwrReset").addEventListener("click", ()=>{
      $("pwrMin").value=""; $("pwrMax").value="";
      clearFilterKey("power_max_w");
      runSearch();
    });
    $("effApply").addEventListener("click", ()=>{
      const raw = $("effMin").value;
      const n = Number(raw);
      if (!Number.isFinite(n) || String(raw).trim()===""){ toast("Set efficacy min first"); return; }
      setSingleFilter("efficacy_lm_w", `>=${n}`);
      runSearch();
    });
    $("effReset").addEventListener("click", ()=>{
      $("effMin").value="";
      clearFilterKey("efficacy_lm_w");
      runSearch();
    });
    $("criExactApply").addEventListener("click", ()=>{
      const raw = $("criExact").value;
      const n = Number(raw);
      if (!Number.isFinite(n) || String(raw).trim()===""){ toast("Set exact CRI first"); return; }
      setSingleFilter("cri", `=${Math.round(n)}`);
      runSearch();
    });
    $("criExactReset").addEventListener("click", ()=>{
      $("criExact").value="";
      clearFilterKey("cri");
      runSearch();
    });
        $("diaApply").addEventListener("click", ()=>{
      const expr = buildRangeExpr($("diaMin").value, $("diaMax").value);
      if (!expr){ toast("Set diameter min/max first"); return; }
      setSingleFilter("diameter", expr);
      runSearch();
    });
    $("diaReset").addEventListener("click", ()=>{
      $("diaMin").value=""; $("diaMax").value="";
      clearFilterKey("diameter");
      runSearch();
    });

    $("hApply").addEventListener("click", ()=>{
      const expr = buildRangeExpr($("hMin").value, $("hMax").value);
      if (!expr){ toast("Set luminaire height min/max first"); return; }
      setSingleFilter("luminaire_height", expr);
      runSearch();
    });
    $("hReset").addEventListener("click", ()=>{
      $("hMin").value=""; $("hMax").value="";
      clearFilterKey("luminaire_height");
      runSearch();
    });
        $("lApply").addEventListener("click", ()=>{
      const expr = buildRangeExpr($("lMin").value, $("lMax").value);
      if (!expr){ toast("Set luminaire length min/max first"); return; }
      setSingleFilter("luminaire_length", expr);
      runSearch();
    });
    $("lReset").addEventListener("click", ()=>{
      $("lMin").value=""; $("lMax").value="";
      clearFilterKey("luminaire_length");
      runSearch();
    });
        $("wApply").addEventListener("click", ()=>{
      const expr = buildRangeExpr($("wMin").value, $("wMax").value);
      if (!expr){ toast("Set luminaire width min/max first"); return; }
      setSingleFilter("luminaire_width", expr);
      runSearch();
    });
    $("wReset").addEventListener("click", ()=>{
      $("wMin").value=""; $("wMax").value="";
      clearFilterKey("luminaire_width");
      runSearch();
    });

    $("ambMinApply").addEventListener("click", ()=>{
      const raw = $("ambMinVal").value;
      const n = Number(raw);
      if (!Number.isFinite(n) || String(raw).trim()===""){ toast("Set minimum ambient temperature first"); return; }
      setSingleFilter("ambient_temp_min_c", `>=${n}`);
      runSearch();
    });
    $("ambMinReset").addEventListener("click", ()=>{
      $("ambMinVal").value="";
      clearFilterKey("ambient_temp_min_c");
      runSearch();
    });

    $("ambMaxApply").addEventListener("click", ()=>{
      const raw = $("ambMaxVal").value;
      const n = Number(raw);
      if (!Number.isFinite(n) || String(raw).trim()===""){ toast("Set maximum ambient temperature first"); return; }
      setSingleFilter("ambient_temp_max_c", `>=${n}`);
      runSearch();
    });
    $("ambMaxReset").addEventListener("click", ()=>{
      $("ambMaxVal").value="";
      clearFilterKey("ambient_temp_max_c");
      runSearch();
    });

  }

  // --------------- Facets UI ----------------
  function compactFacetText(v){
    return String(v ?? "").toLowerCase().replace(/[^0-9a-z]/g, "");
  }

  function isNearFacetToken(query, token){
    const q = compactFacetText(query);
    const t = compactFacetText(token);
    if (q.length < 5 || t.length < 5 || Math.abs(q.length - t.length) > 1) return false;
    if (q === t) return true;

    if (q.length === t.length){
      const mismatches = [];
      for (let i = 0; i < q.length; i += 1){
        if (q[i] !== t[i]) mismatches.push(i);
        if (mismatches.length > 2) return false;
      }
      if (mismatches.length === 1) return true;
      if (mismatches.length === 2){
        const [i, j] = mismatches;
        return j === i + 1 && q[i] === t[j] && q[j] === t[i];
      }
      return false;
    }

    const shorter = q.length < t.length ? q : t;
    const longer = q.length < t.length ? t : q;
    let i = 0;
    let j = 0;
    let edits = 0;
    while (i < shorter.length && j < longer.length){
      if (shorter[i] === longer[j]){
        i += 1;
        j += 1;
        continue;
      }
      edits += 1;
      if (edits > 1) return false;
      j += 1;
    }
    return true;
  }

  function facetFilter(items, needle){
    const n = (needle||"").trim().toLowerCase();
    if (!n) return items;
    return (items||[]).filter(it => {
      const label = String(it.value ?? it.raw ?? "").toLowerCase();
      if (label.includes(n)) return true;
      return isNearFacetToken(n, label);
    });
  }

  function extractFirstNumber(v){
    const m = String(v ?? "").replace(",", ".").match(/-?\d+(?:\.\d+)?/);
    return m ? Number(m[0]) : null;
  }

  function extractUgrFacetNumber(v){
    const src = String(v ?? "").trim();
    if (!src) return null;
    const normalized = src
      .replace(/≤/g, "<=")
      .replace(/≥/g, ">=")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/<\s*lt\s*\/?\s*>/gi, "<")
      .replace(/<\s*gt\s*\/?\s*>/gi, ">")
      .replace(/\s+/g, "");
    const marker = normalized.match(/(?:^|[^a-z0-9])ugr(?:[:;])?(?:<=|>=|<|>|=)?(\d{1,2})(?!\d)/i);
    if (marker) return Number(marker[1]);
    if (/^-?\d+(?:\.\d+)?$/.test(normalized)) return Number(normalized);
    return null;
  }

  function trimZeroDecimals(s){
    const t = String(s ?? "");
    return t
      .replace(/(\d+)\.0+\b/g, "$1")
      .replace(/(\d+\.\d*?[1-9])0+\b/g, "$1");
  }

  const ZERO_HIDDEN_FACET_KEYS = new Set([
    "ugr",
    "cri",
    "cct_k",
    "power_max_w",
    "power_min_w",
    "lumen_output",
    "efficacy_lm_w",
    "beam_angle_deg",
    "warranty_years",
    "lifetime_hours",
    "led_rated_life_h",
    "lumen_maintenance_pct",
    "surge_common_mode",
    "surge_differential_mode",
    "ambient_temp_min_c",
    "ambient_temp_max_c",
  ]);

  function isZeroLike(v){
    const n = extractFirstNumber(v);
    return Number.isFinite(n) && Math.abs(Number(n)) < 1e-9;
  }

  function normalizeFacetItems(key, items){
    const aggregated = new Map();
    const list = Array.isArray(items) ? items : [];

    for (const it of list){
      const src = String(it?.raw ?? it?.value ?? "").trim();
      if (!src) continue;
      if (ZERO_HIDDEN_FACET_KEYS.has(key) && isZeroLike(src)) continue;
      let value = String(it?.value ?? src).trim();
      let raw = src || value;
      let sortNum = null;

      if (key === "ugr"){
        const n = extractUgrFacetNumber(src || value);
        if (Number.isFinite(n)){
          const v = String(Math.round(n));
          value = v;
          raw = v;
          sortNum = Number(v);
        } else {
          continue;
        }
      } else if (key === "ip_rating"){
        const n = extractFirstNumber(src || value);
        if (Number.isFinite(n)){
          const v = String(Math.round(n)).padStart(2, "0");
          value = `IP${v}`;
          raw = `IP${v}`;
          sortNum = Number(v);
        } else {
          continue;
        }
      } else if (key === "ik_rating"){
        const n = extractFirstNumber(src || value);
        if (Number.isFinite(n)){
          const v = String(Math.round(n)).padStart(2, "0");
          value = `IK${v}`;
          raw = `IK${v}`;
          sortNum = Number(v);
        } else {
          continue;
        }
      } else if (key === "cct_k"){
        const n = extractFirstNumber(src || value);
        if (Number.isFinite(n)){
          const v = String(Math.round(n));
          value = `${v}K`;
          raw = v;
          sortNum = Number(v);
        } else {
          continue;
        }
      } else if (["cri", "beam_angle_deg", "warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct", "ambient_temp_min_c", "ambient_temp_max_c"].includes(key)){
        const n = extractFirstNumber(src || value);
        if (Number.isFinite(n)){
          const v = String(Math.round(n));
          value = v;
          raw = v;
          sortNum = Number(v);
        } else if (key === "cri") {
          continue;
        }
      }

      value = trimZeroDecimals(value);
      raw = trimZeroDecimals(raw);

      const mapKey = String(raw).toLowerCase();
      const prev = aggregated.get(mapKey);
      if (prev){
        prev.count += Number(it?.count ?? 0);
      } else {
        aggregated.set(mapKey, {
          value,
          raw,
          count: Number(it?.count ?? 0),
          __sortNum: sortNum
        });
      }
    }

    const out = Array.from(aggregated.values());
    out.sort((a, b) => {
      const aNum = a.__sortNum;
      const bNum = b.__sortNum;
      if (Number.isFinite(aNum) && Number.isFinite(bNum)) return aNum - bNum;
      if (Number.isFinite(aNum)) return -1;
      if (Number.isFinite(bNum)) return 1;
      return String(a.value).localeCompare(String(b.value));
    });
    return out.map(({ __sortNum, ...rest }) => rest);
  }

  function facetValueToFilterExpr(key, rawValue){
    const n = extractFirstNumber(rawValue);
    if (key === "ik_rating" && Number.isFinite(n)) return `>=IK${String(Math.round(n)).padStart(2, "0")}`;
    if (["ip_rating","ip_visible","ip_non_visible"].includes(key) && Number.isFinite(n)) return `>=IP${String(Math.round(n)).padStart(2, "0")}`;
    if (key === "cri" && Number.isFinite(n)) return `>=${Math.round(n)}`;
    if (key === "ugr"){
      const ugr = extractUgrFacetNumber(rawValue);
      if (Number.isFinite(ugr)) return `<=${Math.round(ugr)}`;
    }
    if (["warranty_years", "lifetime_hours", "led_rated_life_h", "lumen_maintenance_pct"].includes(key) && Number.isFinite(n)) return `>=${Math.round(n)}`;
    if (key === "ambient_temp_min_c" && Number.isFinite(n)) return `>=${Math.round(n)}`;
    if (key === "ambient_temp_max_c" && Number.isFinite(n)) return `>=${Math.round(n)}`;
    return String(rawValue ?? "");
  }

  function renderFacetList(containerId, key, items, searchNeedle){
    const box = $(containerId);
    if (!box) return;
    const normalized = normalizeFacetItems(key, items);
    const filtered = facetFilter(normalized, searchNeedle);
    if (!filtered || !filtered.length){
      box.innerHTML = `<div class="small"></div>`;
      return;
    }
    box.innerHTML = filtered.map(it=>{
      const raw = it.raw ?? it.value;
      const val = facetValueToFilterExpr(key, raw);
      const checked = selectedFilters[key]?.has(String(val)) ? "checked" : "";
      return `
        <div class="facet-item">
          <div class="k">
            <input class="toggle" type="checkbox" data-k="${escapeHtml(key)}" data-v="${escapeHtml(val)}" ${checked}/>
            <div class="facetText">${escapeHtml(it.value ?? val)}</div>
          </div>
          <div class="count">${it.count ?? ""}</div>
        </div>
      `;
    }).join("");
  }

  // --------------- API calls ----------------
  async function postJSON(url, payload){
    const res = await fetch(url, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload),
      credentials:"same-origin"
    });
    if (!res.ok){
      const t = await res.text().catch(()=> "");
      throw new Error(`${res.status} ${res.statusText} ${t}`.trim());
    }
    return res.json();
  }

  function topResultCodesForFeedback(){
    const exact = Array.isArray(allExactResults) ? allExactResults : [];
    const similar = Array.isArray(allSimilarResults) ? allSimilarResults : [];
    const source = exact.length ? exact : similar;
    const seen = new Set();
    const codes = [];
    for (const hit of source){
      const code = String(hit?.product_code || "").trim();
      if (!code || seen.has(code.toLowerCase())) continue;
      seen.add(code.toLowerCase());
      codes.push(code);
      if (codes.length >= 10) break;
    }
    return codes;
  }

  async function saveSearchLearning(){
    const queryText = getCurrentQueryText();
    const correctedFilters = buildFiltersPayload();
    const preferredCodes = topResultCodesForFeedback();
    if (!queryText && !Object.keys(correctedFilters).length && !preferredCodes.length){
      toast(t("toast_save_learning_need_context"));
      return;
    }
    const btn = $("btnSaveLearning");
    const oldText = btn ? btn.textContent : "";
    if (btn){
      btn.disabled = true;
      btn.textContent = t("saving");
    }
    try{
      await postJSON("/feedback/search", {
        query_text: queryText,
        corrected_filters: correctedFilters,
        ignored_ai_filters: ignoredAIFilterPairs.map(x => ({ k: String(x.k || ""), v: String(x.v || "") })),
        interpreted: lastInterpretedSearch || {},
        preferred_product_codes: preferredCodes,
        source: "finder-ui"
      });
      toast(t("toast_learning_saved"));
      if (typeof trackUsage === "function"){
        trackUsage("search_feedback_saved_client", {
          page: "finder",
          query_text: queryText,
          filters: correctedFilters,
          metadata: { preferred_count: preferredCodes.length }
        });
      }
    }catch(e){
      const msg = String(e?.message || e || "");
      if (msg.startsWith("401")){
        toast(t("toast_login_learning"));
        try{ window.ProductFinderAuth?.open?.("login"); }catch(_e){}
      } else if (msg.startsWith("403")){
        toast(t("toast_learning_not_enabled"));
      } else {
        toast(t("toast_learning_failed"));
      }
    }finally{
      if (btn){
        btn.disabled = false;
        btn.textContent = oldText || t("save_learning");
      }
    }
  }

  function hasAuthenticatedSession(){
    try{
      return !!window.ProductFinderAuth?.hasSession?.();
    }catch(_e){
      return false;
    }
  }

  function currentUserRole(){
    try{
      return String(window.ProductFinderAuth?.getUser?.()?.role || "").trim().toLowerCase();
    }catch(_e){
      return "";
    }
  }

  function canContributeLearning(){
    try{
      const user = window.ProductFinderAuth?.getUser?.();
      return !!user?.can_contribute_learning;
    }catch(_e){
      return false;
    }
  }

  function isAdminUser(){
    return currentUserRole() === "admin";
  }

  function isPriceSortMode(mode){
    return mode === "price_asc" || mode === "price_desc";
  }

  function normalizeSortModeForAccess(mode){
    const clean = String(mode || "score_desc");
    return (!isAdminUser() && isPriceSortMode(clean)) ? "score_desc" : clean;
  }

  function updateSortOptionsForAccess(){
    const sel = $("sortSel");
    if (!sel) return;
    Array.from(sel.options).forEach(opt => {
      if (opt.dataset.adminOnly === "1"){
        opt.hidden = !isAdminUser();
        opt.disabled = !isAdminUser();
      }
    });
    finderSortModes.exact = normalizeSortModeForAccess(finderSortModes.exact);
    finderSortModes.similar = normalizeSortModeForAccess(finderSortModes.similar);
    if (isPriceSortMode(sel.value) && !isAdminUser()) sel.value = "score_desc";
  }

  function canUseCompareAndQuote(){
    return hasAuthenticatedSession() && currentUserRole() !== "it";
  }

  function isPublicCatalogMode(){
    return !hasAuthenticatedSession();
  }

  function isPublicQueryWithinLimit(text){
    const raw = String(text || "").trim();
    if (!raw) return true;
    const words = raw.split(/\s+/).filter(Boolean);
    return words.length <= PUBLIC_QUERY_MAX_WORDS && raw.length <= PUBLIC_QUERY_MAX_CHARS;
  }

  function setVisible(el, visible, displayValue = ""){
    if (!el) return;
    el.style.display = visible ? displayValue : "none";
  }

  function applyAccessModeUI(){
    const publicMode = isPublicCatalogMode();
    const q = $("q");
    const qMobile = $("qMobile");
    const title = $("finderQueryTitle");
    const hint = $("finderQueryHint");
    const help = $("finderQueryHelp");
    const buildLabel = $("buildLabel");

    if (title) title.textContent = publicMode ? t("catalog_search") : t("query");
    if (hint) {
      hint.textContent = publicMode
        ? t("catalog_hint")
        : t("query_hint_private");
    }
    if (help) {
      help.textContent = publicMode
        ? t("enter_search")
        : t("query_help_private");
    }
    if (q) {
      q.placeholder = publicMode
        ? t("public_search_placeholder")
        : t("q_placeholder");
    }
    if (qMobile) {
      qMobile.placeholder = publicMode ? t("public_search_placeholder") : t("q_mobile_placeholder");
    }
    if (buildLabel) {
      buildLabel.textContent = publicMode
        ? "browse the catalog by name, code, family, and filters"
        : "search, compare, and quote from one workspace";
    }

    const compareAndQuoteEnabled = canUseCompareAndQuote();

    setVisible($("btnTools"), compareAndQuoteEnabled, "");
    setVisible($("btnQuote"), compareAndQuoteEnabled, "");
    setVisible($("btnSaveLearning"), canContributeLearning(), "");
    setVisible($("toolsComparePreview"), compareAndQuoteEnabled, "");
    setVisible($("finderImportRow"), compareAndQuoteEnabled, "");
    setVisible($("visionInfo"), !publicMode, "");
    setVisible($("onboardingBox"), !publicMode, "");
    updateSortOptionsForAccess();
  }

  function priceSortValue(value){
    if (value === null || value === undefined || value === "") return null;
    if (typeof value === "number") return Number.isFinite(value) ? value : null;

    let normalized = String(value).trim();
    if (!normalized) return null;

    normalized = normalized.replace(/[^\d,.\-]/g, "");
    if (!normalized) return null;

    const lastComma = normalized.lastIndexOf(",");
    const lastDot = normalized.lastIndexOf(".");
    if (lastComma >= 0 && lastDot >= 0) {
      normalized = lastComma > lastDot
        ? normalized.replace(/\./g, "").replace(",", ".")
        : normalized.replace(/,/g, "");
    } else if (lastComma >= 0) {
      normalized = normalized.replace(",", ".");
    }

    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function hitPriceValue(hit){
    return priceSortValue(
      hit?.preview?.price
      ?? hit?.price
      ?? hit?.raw?.price
      ?? hit?.raw?.preview?.price
    );
  }

  function comparePrice(a, b, direction = "asc"){
    const av = hitPriceValue(a);
    const bv = hitPriceValue(b);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return direction === "desc" ? bv - av : av - bv;
  }

  function hitSpecSortValue(hit, key){
    const preview = hit?.preview || {};
    const raw = hit?.raw || {};
    const value = specValueForKey(preview, key) ?? specValueForKey(raw, key) ?? hit?.[key];
    return extractFirstNumber(value);
  }

  function compareSpecNumber(a, b, key, direction = "asc"){
    const av = hitSpecSortValue(a, key);
    const bv = hitSpecSortValue(b, key);
    if (av === null && bv === null) {
      return String(a?.product_code || "").localeCompare(String(b?.product_code || ""));
    }
    if (av === null) return 1;
    if (bv === null) return -1;
    const delta = direction === "desc" ? bv - av : av - bv;
    return delta || String(a?.product_code || "").localeCompare(String(b?.product_code || ""));
  }

  function sortHits(hits, tab = activeResultsTab){
    const fallback = "score_desc";
    const mode = normalizeSortModeForAccess(finderSortModes[tab] || fallback);
    const arr = Array.isArray(hits) ? [...hits] : [];
    if (mode === "score_asc") arr.sort((a,b)=> (a.score??0)-(b.score??0));
    if (mode === "score_desc") arr.sort((a,b)=> (b.score??0)-(a.score??0));
    if (mode === "name_asc") arr.sort((a,b)=> String(a.product_name||"").localeCompare(String(b.product_name||"")) || String(a.product_code||"").localeCompare(String(b.product_code||"")));
    if (mode === "name_desc") arr.sort((a,b)=> String(b.product_name||"").localeCompare(String(a.product_name||"")) || String(a.product_code||"").localeCompare(String(b.product_code||"")));
    if (mode === "code_asc") arr.sort((a,b)=> String(a.product_code||"").localeCompare(String(b.product_code||"")));
    if (mode === "code_desc") arr.sort((a,b)=> String(b.product_code||"").localeCompare(String(a.product_code||"")));
    if (mode === "price_asc") arr.sort((a,b)=> comparePrice(a, b, "asc"));
    if (mode === "price_desc") arr.sort((a,b)=> comparePrice(a, b, "desc"));
    if (mode === "power_asc") arr.sort((a,b)=> compareSpecNumber(a, b, "power_max_w", "asc"));
    if (mode === "power_desc") arr.sort((a,b)=> compareSpecNumber(a, b, "power_max_w", "desc"));
    if (mode === "efficacy_desc") arr.sort((a,b)=> compareSpecNumber(a, b, "efficacy_lm_w", "desc"));
    if (mode === "lumen_asc") arr.sort((a,b)=> compareSpecNumber(a, b, "lumen_output", "asc"));
    if (mode === "lumen_desc") arr.sort((a,b)=> compareSpecNumber(a, b, "lumen_output", "desc"));
    return arr;
  }

  function buildProductNameShortFacetFromHits(hits){
    const counts = new Map();
    const arr = Array.isArray(hits) ? hits : [];
    for (const h of arr){
      const family = String(h?.preview?.product_family || h?.raw?.product_family || "").trim().toLowerCase();
      if (family === "accessories") continue;
      const name = String(h?.product_name || "").trim().toLowerCase();
      if (!name) continue;
      const first = name.split(/\s+/)[0];
      if (!first) continue;
      counts.set(first, (counts.get(first) || 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a,b)=> b[1]-a[1] || a[0].localeCompare(b[0]))
      .slice(0, NAME_FACET_VALUE_LIMIT)
      .map(([value, count]) => ({ value, raw: value, count }));
  }

  function findHitByCode(code){
    const wanted = String(code || "").trim();
    if (!wanted) return null;
    const pool = [...(allExactResults || []), ...(allSimilarResults || [])];
    return pool.find(hit => String(hit?.product_code || "").trim() === wanted) || null;
  }

  function applyClientProductNameShortFilter(hits){
    const wanted = selectedFilters[PRODUCT_NAME_FILTER_KEY] || selectedFilters[LEGACY_PRODUCT_NAME_FILTER_KEY];
    if (!wanted || !wanted.size) return Array.isArray(hits) ? hits : [];
    const allow = new Set(Array.from(wanted).map(v => String(v).trim().toLowerCase()));
    const arr = Array.isArray(hits) ? hits : [];
    return arr.filter(h => {
      const name = String(h?.product_name || "").trim().toLowerCase();
      if (!name) return false;
      const first = name.split(/\s+/)[0];
      return allow.has(first);
    });
  }

  function getProductNameShortFacetSignature(){
    return JSON.stringify({
      text: $("q").value || "",
      filters: buildFiltersPayload()
    });
  }

  async function hydrateProductNameShortFacetFromSearch(){
    const signature = getProductNameShortFacetSignature();
    const reqId = ++productNameShortFacetReqSeq;
    try{
      const payload = {
        text: $("q").value || "",
        filters: buildFiltersPayload(),
        limit: 100,
        include_similar: true,
        include_accessories: includeAccessoriesEnabled(),
        sort: normalizeSortModeForAccess($("sortSel")?.value || finderSortModes[activeResultsTab] || "score_desc"),
        debug: false
      };
      const data = await postJSON("/search", payload);
      if (reqId !== productNameShortFacetReqSeq) return; // stale response
      const fromSearch = buildProductNameShortFacetFromHits([...(data.exact || []), ...(data.similar || [])]);
      if (fromSearch.length){
        // apply only if query/filters are still the same
        if (signature !== getProductNameShortFacetSignature()) return;
        lastProductNameShortFacet = fromSearch;
        lastProductNameShortFacetSignature = signature;
        renderFacetList(PRODUCT_NAME_FILTER_KEY, PRODUCT_NAME_FILTER_KEY, lastProductNameShortFacet, $("simSearch").value);
      }
    }catch(_e){
      // silent fallback
    }
  }

  function getPreviewPills(hit){
    // Try from preview, then from raw
    const p = hit.preview || hit.raw || {};
    const pills = [];
    const add = (label, value, key = "") => {
      if (value===undefined || value===null || String(value).trim()==="") return;
      const displayLabel = window.ProductFinderMeasurements?.labelForKey?.(key, label) || label;
      const displayValue = key ? formatSpecDisplayValue(key, value) : String(value ?? "").trim();
      if (!displayValue) return;
      pills.push(`<span class="pill">${escapeHtml(displayLabel)}: ${escapeHtml(displayValue)}</span>`);
    };
    add("IP", p.ip_rating, "ip_rating");
    add("IK", p.ik_rating, "ik_rating");
    add("CCT", p.cct_k, "cct_k");
    add("CRI", p.cri, "cri");
    add("UGR", p.ugr, "ugr");
    add("W", p.power_max_w ?? p.power_max_value ?? p.power, "power_max_w");
    add("lm", p.lumen_output ?? p.lumen_output_value, "lumen_output");
    add("lm/W", p.efficacy_lm_w ?? p.efficacy_value, "efficacy_lm_w");
    add("CTRL", p.control_protocol, "control_protocol");
    add("Class", p.insulation_class, "insulation_class");
    add("Surge", p.surge_common_mode, "surge_common_mode");
    add("Surge diff", p.surge_differential_mode, "surge_differential_mode");
    add("EM", p.emergency_present, "emergency_present");
    add("T min", p.ambient_temp_min_c, "ambient_temp_min_c");
    add("T max", p.ambient_temp_max_c, "ambient_temp_max_c");
    add("Beam", p.beam_angle_deg, "beam_angle_deg");
    add("Dia", p.diameter, "diameter");
    add("L", p.luminaire_length, "luminaire_length");
    add("Wdt", p.luminaire_width, "luminaire_width");
    add("H", p.luminaire_height, "luminaire_height");
    add("Color", p.housing_color, "housing_color");
    add("Shape", p.shape, "shape");
    add("Warranty", p.warranty_years, "warranty_years");
    add("Life(h)", p.led_rated_life_h ?? p.lifetime_hours, "lifetime_hours");
    add("L maint %", p.lumen_maintenance_pct, "lumen_maintenance_pct");
    return pills.slice(0,16).join("");
  }

  const RESULT_SPEC_FIELDS = [
    ["product_family", "Family"],
    ["ip_rating", "IP"],
    ["ik_rating", "IK"],
    ["cct_k", "CCT"],
    ["cri", "CRI"],
    ["ugr", "UGR"],
    ["power_max_w", "Power max W"],
    ["lumen_output", "Lumen"],
    ["efficacy_lm_w", "Efficacy"],
    ["beam_angle_deg", "Beam"],
    ["control_protocol", "Control"],
    ["interface", "Interface"],
    ["insulation_class", "Insulation"],
    ["surge_common_mode", "Surge common"],
    ["surge_differential_mode", "Surge diff"],
    ["emergency_present", "Emergency"],
    ["ambient_temp_min_c", "Temp min (C)"],
    ["ambient_temp_max_c", "Temp max (C)"],
    ["shape", "Shape"],
    ["diameter", "Diameter"],
    ["luminaire_length", "Length"],
    ["luminaire_width", "Width"],
    ["luminaire_height", "Height"],
    ["housing_color", "Color"],
    ["warranty_years", "Warranty"],
    ["lifetime_hours", "Lifetime h"],
    ["led_rated_life_h", "LED life h"],
    ["lumen_maintenance_pct", "Lumen maint."],
  ];

  function specValueForKey(preview, key){
    const p = preview || {};
    if (key === "ugr") return p.ugr ?? p.ugr_value;
    if (key === "power_max_w") return p.power_max_w ?? p.power_max_value ?? p.power;
    if (key === "lumen_output") return p.lumen_output ?? p.lumen_output_value;
    if (key === "efficacy_lm_w") return p.efficacy_lm_w ?? p.efficacy_value;
    return p[key];
  }

  function formatSpecDisplayValue(key, value){
    let s = String(value ?? "").trim();
    if (!s) return "";
    s = s
      .replaceAll("<lt/>", "<")
      .replaceAll("&lt;", "<")
      .replaceAll("&gt;", ">")
      .replaceAll("<gt/>", ">")
      .replace(/\s+/g, " ");
    if (key === "ugr"){
      s = s.replace(/^UGR\s*/i, "UGR");
      s = s.replace(/^UGR(?=\d)/i, "UGR<");
      const m = s.match(/(?:UGR)?\s*(<=|>=|<|>|=)?\s*(\d+(?:[.,]\d+)?)/i);
      if (m){
        const op = m[1] || "<";
        const n = m[2].replace(",", ".");
        return `${op}${n}`;
      }
    }
    if (["cri", "lumen_maintenance_pct"].includes(key)){
      const m = s.match(/^\s*(<=|>=|<|>|=)?\s*(-?\d+(?:[.,]\d+)?)\s*(%|percent)?\s*$/i);
      if (m){
        const op = m[1] || "";
        const n = Number(String(m[2]).replace(",", "."));
        if (Number.isFinite(n)){
          const display = Number.isInteger(n) ? String(n) : String(Number(n.toFixed(1))).replace(/\.0$/, "");
          return `${op}${display}`;
        }
      }
    }
    s = window.ProductFinderMeasurements?.formatSpecValue?.(key, s) || s;
    return s;
  }

  function deviationKeysForHit(hit){
    const keys = new Set();
    const add = (key) => {
      const clean = normalizeSpecKey(key);
      if (clean) keys.add(clean);
    };
    (Array.isArray(hit?.missing) ? hit.missing : []).forEach(add);
    (Array.isArray(hit?.deviations) ? hit.deviations : []).forEach(raw => {
      const s = String(raw || "").trim();
      let m = s.match(/^hard missing:\s*([a-z0-9_]+)/i)
        || s.match(/^([a-z0-9_]+):/i)
        || s.match(/^([a-z0-9_]+)\s+mismatch:/i);
      if (m) add(m[1]);
      m = s.match(/\b([a-z0-9_]+)\s+mismatch:\s*wanted=/i);
      if (m) add(m[1]);
    });
    return keys;
  }

  function normalizeSpecKey(key){
    const k = String(key || "").trim();
    return ({
      ugr_value: "ugr",
      power_max_value: "power_max_w",
      power: "power_max_w",
      lumen_output_value: "lumen_output",
      efficacy_value: "efficacy_lm_w",
      control: "control_protocol",
      colour: "housing_color",
      color: "housing_color",
      family: "product_family",
      name_prefix: "product_name_short",
    })[k] || k;
  }

  function specStateClass(key, matchedKeys, deviatedKeys){
    if (deviatedKeys.has(key)) return "bad";
    if (matchedKeys.has(key)) return "ok";
    return "neutral";
  }

  function renderSpecList(hit){
    const p = hit?.preview || hit?.raw || {};
    const matched = (hit && typeof hit.matched === "object" && hit.matched) ? hit.matched : {};
    const matchedKeys = new Set(Object.keys(matched).map(normalizeSpecKey));
    const deviatedKeys = deviationKeysForHit(hit);
    const rows = RESULT_SPEC_FIELDS.map(([key, label]) => {
      const value = specValueForKey(p, key);
      const displayValue = formatSpecDisplayValue(key, value);
      if (!displayValue) return "";
      const state = specStateClass(key, matchedKeys, deviatedKeys);
      const baseLabel = filterDisplayLabel(key) || label;
      const displayLabel = window.ProductFinderMeasurements?.labelForKey?.(key, baseLabel) || baseLabel;
      return `
        <div class="specRow ${state}">
          <span class="specKey">${escapeHtml(displayLabel)}</span>
          <span class="specValue">${escapeHtml(displayValue)}</span>
        </div>
      `;
    }).filter(Boolean);
    if (!rows.length) return "";
    return `<div class="specList">${rows.join("")}</div>`;
  }

function formatScorePercent(score, opts = {}){
  const hasIssues = !!opts.hasIssues;
  const n = Number(score);
  const clamped = Math.max(0, Math.min(1, Number.isFinite(n) ? n : 0));
  let pct = Math.round(clamped * 100);
  // Never display 100% if backend already reports deviations/missing for this hit.
  if (hasIssues && pct >= 100) pct = 99;
  return `${pct}%`;
}

function humanJoin(items){
  const arr = (Array.isArray(items) ? items : []).filter(Boolean);
  if (!arr.length) return "";
  if (arr.length === 1) return arr[0];
  if (arr.length === 2) return `${arr[0]} and ${arr[1]}`;
  return `${arr.slice(0, -1).join(", ")}, and ${arr[arr.length - 1]}`;
}

function summarizeMatchedFilters(hit, kind){
  const matched = (hit && typeof hit.matched === "object" && hit.matched) ? hit.matched : {};
  const labels = Array.from(new Set(
    Object.keys(matched)
      .map(k => String(k || "").trim())
      .filter(Boolean)
      .map(prettyFilterLabel)
      .filter(Boolean)
  )).slice(0, 4);
  const tier = resultTierLabel(hit, kind);
  if (!labels.length){
    return "";
  }
  if (tier === "Exact") return t("matches_search_on", { fields: humanJoin(labels) });
  if (tier === "Close") return t("close_search_on", { fields: humanJoin(labels) });
  return t("related_search_on", { fields: humanJoin(labels) });
}

function buildResultExplanation(hit, kind){
  const lines = [];
  const summary = summarizeMatchedFilters(hit, kind);
  if (summary){
    lines.push(`<div><b>${escapeHtml(t("why_it_appears"))}:</b> ${escapeHtml(summary)}</div>`);
  }
  const differences = Array.isArray(hit?.deviations)
    ? hit.deviations.map(formatDeviationText).filter(Boolean).slice(0, 2)
    : [];
  if (differences.length){
    lines.push(`<div><b>${escapeHtml(t("what_differs"))}:</b> ${escapeHtml(differences.join(" | "))}</div>`);
  }
  const missing = Array.isArray(hit?.missing)
    ? hit.missing.map(formatMissingText).filter(Boolean).slice(0, 3)
    : [];
  if (missing.length){
    lines.push(`<div><b>${escapeHtml(t("not_available"))}:</b> ${escapeHtml(missing.join(" | "))}</div>`);
  }
  if (!lines.length) return "";
  return `<div class="small" style="margin-top:10px">${lines.join("")}</div>`;
}

function getCurrentQueryText(){
  return String(($("q")?.value || $("qMobile")?.value || "")).trim();
}

function syncSortSelectToActiveTab(){
  const sel = $("sortSel");
  if (!sel) return;
  updateSortOptionsForAccess();
  const fallback = "score_desc";
  const mode = normalizeSortModeForAccess(finderSortModes[activeResultsTab] || fallback);
  const hasOption = Array.from(sel.options).some(opt => opt.value === mode);
  finderSortModes[activeResultsTab] = hasOption ? mode : fallback;
  sel.value = finderSortModes[activeResultsTab];
}

function buildSearchCompareSpec(rawFilters, queryText){
  const spec = {};
  for (const [key, value] of Object.entries(rawFilters || {})){
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)){
      if (!value.length) continue;
      spec[key] = String(value[0] ?? "").trim();
    } else if (String(value).trim()){
      spec[key] = String(value).trim();
    }
  }
  const aiItems = [
    ...(Array.isArray(lastImportedFilterItems) ? lastImportedFilterItems : []),
    ...(Array.isArray(lastUnderstoodFilterItems) ? lastUnderstoodFilterItems : []),
  ];
  for (const item of aiItems){
    const key = String(item?.key || "").trim();
    const value = String(item?.value || "").trim();
    if (!key || !value) continue;
    if (String(item?.source || "").trim().toLowerCase() === "import" && !isFilterValueSelected(key, value)) continue;
    if (!(key in spec)) spec[key] = value;
  }
  const text = String(queryText || "").trim();
  if (text && !spec.product_name){
    spec.product_name = text;
  }
  return spec;
}

function updateSearchCompareSeed(spec){
  const normalized = (spec && typeof spec === "object") ? spec : null;
  lastSearchCompareSpec = normalized && Object.keys(normalized).length ? normalized : null;
  if (!lastSearchCompareSpec) return;
  try{
    const raw = sessionStorage.getItem(TOOLS_STATE_KEY);
    let state = raw ? (JSON.parse(raw) || {}) : {};
    const fields = (state && typeof state.fields === "object" && state.fields) ? state.fields : {};
    fields.cmpA = "Project requirement";
    state.fields = fields;
    state.finderSeedSpec = lastSearchCompareSpec;
    state.ts = Date.now();
    sessionStorage.setItem(TOOLS_STATE_KEY, JSON.stringify(state));
    renderToolsComparePreview();
  }catch(_e){}
}

function getCurrentFiltersQueryParam(){
  try{
    const f = buildFiltersPayload();
    if (!f || !Object.keys(f).length) return "";
    return encodeURIComponent(JSON.stringify(f));
  }catch(_e){
    return "";
  }
}

function getCurrentCompareSeedQueryParam(){
  try{
    const spec = (lastSearchCompareSpec && typeof lastSearchCompareSpec === "object") ? lastSearchCompareSpec : null;
    if (!spec || !Object.keys(spec).length) return "";
    return encodeURIComponent(JSON.stringify(spec));
  }catch(_e){
    return "";
  }
}

function persistLastIdealQuerySeed(){
  try{
    const q = getCurrentQueryText();
    if (q) sessionStorage.setItem("pf_last_ideal_query", q);
  }catch(_e){}
}

const HIT_IMAGE_PLACEHOLDER_SVG = "data:image/svg+xml;utf8," + encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
    <rect width="96" height="96" rx="10" fill="#f8fafc" stroke="#e5e7eb"/>
    <circle cx="48" cy="40" r="14" fill="#e2e8f0"/>
    <rect x="22" y="61" width="52" height="8" rx="4" fill="#e2e8f0"/>
  </svg>`
);

  function openImageLightbox(src, altText){
  const box = $("imgLightbox");
  const img = $("imgLightboxPreview");
  if (!box || !img || !src) return;
  img.src = String(src);
  img.alt = String(altText || "Preview");
  box.classList.add("show");
  box.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

  function closeImageLightbox(){
  const box = $("imgLightbox");
  const img = $("imgLightboxPreview");
  if (!box) return;
  box.classList.remove("show");
  box.setAttribute("aria-hidden", "true");
  if (img){
    img.removeAttribute("src");
    img.alt = "Preview";
  }

  function trackUsage(eventType, payload){
    try{
      window.ProductFinderConsent?.track?.(eventType, payload || {});
    }catch(_e){}
  }
  document.body.style.overflow = "";
}

function renderHits(containerId, hits, kind){
  const box = $(containerId);
  if (!hits || !hits.length){
    const isInitial = !hasRunSearchOnce;
    const title = isInitial
      ? (kind === "exact" ? "Start a search" : "Similar products will appear here")
      : (kind === "exact" ? "No exact matches" : "No similar products");
    const text = isInitial
      ? (kind === "exact"
          ? "Type a query or use filters on the left to search your catalogue."
          : "Run a search to see alternative suggestions.")
      : (kind === "exact"
          ? "Try a recovery suggestion or relax one filter."
          : "Try a broader query to surface alternatives.");
    box.innerHTML = `
      <div class="emptyState">
        <p class="emptyTitle">${title}</p>
        <p class="emptyText">${text}</p>
      </div>
    `;
    return;
  }
  const arr = sortHits(hits, kind === "similar" ? "similar" : "exact");

  box.innerHTML = arr.map((h, idx)=>{
    const score = (h.score ?? 0);
    const hasIssues = !!((h.deviations && h.deviations.length) || (h.missing && h.missing.length));
    const badgeClass = kind==="exact" ? "ok" : "warn";
    const badgeText = resultTierLabel(h, kind);
    const isPrimary = kind === "exact" && idx === 0;
    const showProductActions = canUseCompareAndQuote();

    const orderCode = h.product_code || "";
    const inQuote = quoteCart.has(String(orderCode));
    const p = h.preview || {};
    const manufacturer = String(p.manufacturer || "").trim();
    const datasheetUrl = buildDatasheetUrl(orderCode, currentLang);
    const websiteUrl = p.website_url || `https://www.disano.it/it/search/?q=${encodeURIComponent(orderCode)}`;
    const imageUrl = p.image_preview_url || `/preview-image?product_code=${encodeURIComponent(orderCode)}&manufacturer=${encodeURIComponent(manufacturer)}&website_url=${encodeURIComponent(websiteUrl)}`;
    const fullImageUrl = `/full-image?product_code=${encodeURIComponent(orderCode)}&manufacturer=${encodeURIComponent(manufacturer)}&website_url=${encodeURIComponent(websiteUrl)}`;
    const isFosnova = /fosnova/i.test(manufacturer);
    const mfrLogoUrl = isFosnova
      ? LOCAL_MANUFACTURER_LOGOS.fosnova
      : LOCAL_MANUFACTURER_LOGOS.disano;
    const mfrAlt = isFosnova ? "Fosnova" : "Disano";

    return `
      <div class="hit ${isPrimary ? "primary" : ""}">
        <div class="hitBody">
          <div class="hitMedia">
            <img class="hitImg" src="${escapeHtml(imageUrl)}" data-full-img="${escapeHtml(fullImageUrl)}" alt="${escapeHtml(orderCode)}" loading="lazy" decoding="async" />
            <a class="mfrLogoLink" href="${websiteUrl}" target="_blank" rel="noopener noreferrer" title="Go to website">
              <img class="mfrLogo" src="${mfrLogoUrl}" alt="${mfrAlt}" loading="lazy" decoding="async" width="72" height="18" />
              <span class="mfrLogoFallback" aria-hidden="true">${escapeHtml(mfrAlt)}</span>
            </a>
            <div class="hitLinks">
              <a href="${datasheetUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("datasheet"))}</a>
              <a href="${websiteUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("website"))}</a>
            </div>
            <div class="hitActions">
              <div class="badge ${badgeClass}">${badgeText} | ${formatScorePercent(score, { hasIssues })}</div>
              ${showProductActions ? `<button class="btn hitActionBtn ${inQuote ? "secondary" : ""}" data-quote-toggle="${escapeHtml(orderCode)}">${escapeHtml(inQuote ? t("remove") : t("add_to_quote"))}</button>` : ``}
              ${showProductActions ? `<button class="btn secondary hitActionBtn" type="button" data-compare-add="${escapeHtml(orderCode)}">${escapeHtml(t("compare"))}</button>` : ``}
              ${showProductActions ? `<a class="btn secondary hitActionBtn" href="/frontend/tools.html?fresh=1&altCode=${encodeURIComponent(orderCode)}&auto=1${getCurrentQueryText() ? `&idealQuery=${encodeURIComponent(getCurrentQueryText())}` : ``}${getCurrentFiltersQueryParam() ? `&finderFilters=${getCurrentFiltersQueryParam()}` : ``}${getCurrentCompareSeedQueryParam() ? `&finderSeedSpec=${getCurrentCompareSeedQueryParam()}` : ``}">${escapeHtml(t("alternatives"))}</a>` : ``}
            </div>
          </div>
          <div class="hitInfo">
            <div class="hitHead">
              <div>
                ${isPrimary ? `<div class="topMark">${escapeHtml(t("top_match"))}</div>` : ``}
                <div class="code">
                  <a href="${datasheetUrl}" target="_blank" rel="noopener noreferrer" style="text-decoration:none; color:inherit;">
                    ${escapeHtml(orderCode)}
                  </a>
                </div>
                <div class="name">${escapeHtml(h.product_name || "")}</div>
              </div>
            </div>
            ${renderSpecList(h)}
            ${buildResultExplanation(h, kind)}
          </div>
        </div>
      </div>
    `;
  }).join("");

  Array.from(box.querySelectorAll("img.hitImg")).forEach(img => {
    img.addEventListener("error", ()=>{
      if (img.dataset.fallbackApplied === "1") return;
      img.dataset.fallbackApplied = "1";
      img.src = HIT_IMAGE_PLACEHOLDER_SVG;
      img.style.objectFit = "contain";
      img.style.background = "#f8fafc";
    }, { once: true });
  });
  Array.from(box.querySelectorAll("img.mfrLogo")).forEach(img => {
    img.addEventListener("error", ()=>{
      const link = img.closest(".mfrLogoLink");
      if (link) link.classList.add("logoFail");
    }, { once: true });
  });
}

function buildDatasheetUrl(code, lang){
  const c = String(code || "").trim();
  if (!c) return "";
  const cfg = DATASHEET_LANGS[String(lang || "").toLowerCase()] || DATASHEET_LANGS.en;
  const q = encodeURIComponent(c);
  return `https://www.disano.it/download/mediafiles/-${cfg.media}_${q}.pdf/${cfg.prefix}_${q}.pdf`;
}

document.addEventListener("click", (ev)=>{
  const t = ev.target;
  if (!(t instanceof Element)) return;
  if (t.id === "btnImgLightboxClose" || t.matches("[data-img-close='1']")){
    closeImageLightbox();
    return;
  }

  const selectedBox = $("selected");
  const selectedChip = t.closest(".chip[data-k][data-v]");
  if (selectedChip && selectedBox?.contains(selectedChip)){
    const action = t.closest("[data-chip-action]")?.getAttribute("data-chip-action") || "remove";
    if (action !== "remove") return;
    removeFilter(selectedChip.dataset.k, selectedChip.dataset.v);
    runSearch();
    return;
  }

  const aiChip = t.closest(".chip.ai[data-ai-k][data-ai-v]");
  if (aiChip && selectedBox?.contains(aiChip)){
    const key = String(aiChip.dataset.aiK || "").trim();
    const value = String(aiChip.dataset.aiV || "").trim();
    const src = String(aiChip.dataset.aiSrc || "query").trim().toLowerCase();
    const action = t.closest("[data-chip-action]")?.getAttribute("data-chip-action") || "ignore";
    if (!key || !value) return;
    if (action === "mandatory"){
      addFilter(key, value);
      if (src !== "import"){
        const existsIgnored = ignoredAIFilterPairs.some(x => String(x.k) === key && String(x.v) === value);
        if (!existsIgnored) ignoredAIFilterPairs.push({ k: key, v: value });
      }
      if (src === "import"){
        const existsImport = (lastImportedFilterItems || []).some(it => String(it?.key || "") === key && String(it?.value || "") === value);
        if (!existsImport){
          lastImportedFilterItems.push({ key, value, label: filterDisplayLabel(key), source: "import" });
        }
      }
      runSearch();
      return;
    }
    if (src === "import"){
      removeImportedFilter(key, value);
      runSearch();
      return;
    }
    if (key === "product_family"){
      ignoredAIFilterPairs = ignoredAIFilterPairs.filter(x => String(x.k || "") !== key);
      ignoredAIFilterPairs.push({ k: key, v: "" });
    } else {
      const exists = ignoredAIFilterPairs.some(x => String(x.k) === key && String(x.v) === value);
      if (!exists) ignoredAIFilterPairs.push({ k: key, v: value });
    }
    runSearch();
    return;
  }

  const visionBox = $("visionInfo");
  const visionChip = t.closest(".chip[data-vision-k][data-vision-v]");
  if (visionChip && visionBox?.contains(visionChip)){
    const key = String(visionChip.dataset.visionK || "").trim();
    const value = String(visionChip.dataset.visionV || "").trim();
    if (!key || !value) return;
    removeImportedFilter(key, value);
    visionChip.remove();
    runSearch();
    return;
  }

  const quoteBtn = t.closest("button[data-quote-toggle]");
  if (quoteBtn){
    const code = String(quoteBtn.dataset.quoteToggle || "").trim();
    const hit = findHitByCode(code);
    const kind = quoteBtn.closest("#similar") ? "similar" : "exact";
    if (!hit) return;
    toggleQuoteItem(hit, kind);
    trackUsage("quote_add_from_search", {
      page: "finder",
      product_code: code,
      query_text: getCurrentQueryText(),
      filters: buildFiltersPayload(),
      metadata: { tab: kind }
    });
    return;
  }

  const compareBtn = t.closest("button[data-compare-add]");
  if (compareBtn){
    const code = normalizeCode(compareBtn.getAttribute("data-compare-add"));
    const kind = compareBtn.closest("#similar") ? "similar" : "exact";
    const res = upsertCompareCodeInToolsState(code);
    if (res.ok && res.reason === "inserted"){
      const slot = ["A","B","C"][Number(res.slot)] || String(Number(res.slot) + 1);
      toast(`Added ${code} to compare slot ${slot}`);
    } else if (res.ok && res.reason === "duplicate"){
      toast(`${code} is already in the comparison sheet`);
    } else if (res.reason === "full"){
      toast("Comparison sheet is full (3/3)");
    } else {
      toast("Could not update comparison sheet");
    }
    renderToolsComparePreview();
    trackUsage("compare_add_from_search", {
      page: "finder",
      product_code: String(code || ""),
      query_text: getCurrentQueryText(),
      filters: buildFiltersPayload(),
      metadata: { tab: kind }
    });
    return;
  }

  const hitImage = t.closest("img.hitImg");
  if (hitImage){
    const src = hitImage.dataset.fullImg || hitImage.currentSrc || hitImage.src;
    if (!src || src.startsWith("data:image/svg+xml")) return;
    openImageLightbox(src, hitImage.alt || "Product preview");
    return;
  }

  const datasheetLink = t.closest(".code a");
  if (datasheetLink){
    const code = String(datasheetLink.textContent || "").trim();
    trackUsage("product_open_datasheet", {
      page: "finder",
      product_code: code,
      query_text: getCurrentQueryText(),
      filters: buildFiltersPayload(),
    });
    return;
  }

  const logoLink = t.closest(".mfrLogoLink");
  if (logoLink){
    const wrap = logoLink.closest(".hit");
    const code = String(wrap?.querySelector(".code")?.textContent || "").trim();
    trackUsage("product_open_website", {
      page: "finder",
      product_code: code,
      query_text: getCurrentQueryText(),
      filters: buildFiltersPayload(),
    });
  }
});
document.addEventListener("change", (ev)=>{
  const t = ev.target;
  if (!(t instanceof HTMLInputElement)) return;
  if (t.id === "includeAccessories"){
    loadFacets({ showErrorToast: false });
    if (hasRunSearchOnce) runSearch();
    saveFinderState();
    return;
  }
  if (!t.matches(".facet-list input.toggle[data-k][data-v]")) return;
  const k = t.dataset.k;
  const v = t.dataset.v;
  if (t.checked) addFilter(k, v); else removeFilter(k, v);
  runSearch();
});
document.addEventListener("keydown", (ev)=>{
  if (ev.key === "Escape") closeImageLightbox();
});


  async function loadFacets(options = {}){
    const showErrorToast = options.showErrorToast !== false;
    const payload = { text: $("q").value || "", filters: buildFacetsFiltersPayload(), include_accessories: includeAccessoriesEnabled(), debug: false };
    payload.allow_ai = !isPublicCatalogMode();
    // /facets endpoint expected by your original UI
    // If backend doesn't have /facets, this call will fail gracefully.
    try{
      const data = await postJSON("/facets", payload);
      // Families
      renderFacetList("families","product_family", data.families || [], $("famSearch").value);
      renderFacetList("manufacturer","manufacturer", data.power_voltage?.manufacturer || [], $("mfrSearch").value);
      const backendSimilar = data.product_name_short || data.similar_names || [];
      const signature = getProductNameShortFacetSignature();
      const canReuseLocal = lastProductNameShortFacetSignature === signature && lastProductNameShortFacet.length;
      const similarItems = backendSimilar.length ? backendSimilar : (canReuseLocal ? lastProductNameShortFacet : []);
      renderFacetList(PRODUCT_NAME_FILTER_KEY, PRODUCT_NAME_FILTER_KEY, similarItems, $("simSearch").value);
      if (!similarItems.length){
        hydrateProductNameShortFacetFromSearch();
      } else if (backendSimilar.length){
        lastProductNameShortFacet = backendSimilar;
        lastProductNameShortFacetSignature = signature;
      }

      // Photometrics
      renderFacetList("cct_k","cct_k", data.photometrics?.cct_k || [], $("cctSearch").value);
      renderFacetList("cri","cri", data.photometrics?.cri || [], $("criSearch").value);
      renderFacetList("ugr","ugr", data.photometrics?.ugr || [], $("ugrSearch").value);

      // Optics & Finish
      renderFacetList(
        "beam_angle_deg",
        "beam_angle_deg",
        data.dimensions_options?.options?.beam_angle_deg || [],
        $("beamSearch").value
      );

      renderFacetList(
        "housing_color",
        "housing_color",
        data.dimensions_options?.options?.housing_color || [],
        $("colSearch").value
      );
      renderFacetList(
        "shape",
        "shape",
        data.dimensions_options?.shape || data.dimensions_options?.options?.shape || [],
        $("shapeSearch")?.value || ""
      );


      // Power & Control
      renderFacetList("control_protocol","control_protocol", data.power_voltage?.control_protocol || [], $("ctrlSearch").value);
      renderFacetList("interface","interface", data.power_voltage?.interface || [], $("cpSearch").value);
      renderFacetList("insulation_class","insulation_class", data.power_voltage?.insulation_class || [], $("insulationSearch")?.value || "");
      renderFacetList("surge_common_mode","surge_common_mode", data.power_voltage?.surge_common_mode || [], $("surgeCommonSearch")?.value || "");
      renderFacetList("surge_differential_mode","surge_differential_mode", data.power_voltage?.surge_differential_mode || [], $("surgeDifferentialSearch")?.value || "");
      renderFacetList("emergency_present","emergency_present", data.power_voltage?.emergency_present || [], "");

      // Protection (if backend returns them in dimensions_options, adapt; otherwise attempt common keys)
      renderFacetList("ip_rating","ip_rating", data.dimensions_options?.ip_rating || data.power_voltage?.ip_rating || [], $("ipTotalSearch").value);
      renderFacetList("ip_visible","ip_visible", data.dimensions_options?.ip_visible || data.power_voltage?.ip_visible || [], $("ipVisibleSearch").value);
      renderFacetList("ip_non_visible","ip_non_visible", data.dimensions_options?.ip_non_visible || data.power_voltage?.ip_non_visible || [], $("ipNonVisibleSearch").value);
      renderFacetList("ik_rating","ik_rating", data.dimensions_options?.ik_rating || data.power_voltage?.ik_rating || [], $("ikSearch").value);

      // Regulations
      renderFacetList("led_rated_life_h","led_rated_life_h", data.warranty_lifetime?.led_rated_life_h || data.warranty_lifetime?.lifetime_hours || [], $("ledLifeSearch").value);
      renderFacetList("warranty_years","warranty_years", data.warranty_lifetime?.warranty_years || [], $("warrSearch").value);
      renderFacetList("lumen_maintenance_pct","lumen_maintenance_pct", data.warranty_lifetime?.lumen_maintenance_pct || [], $("lumMaintSearch").value);
      facetsHydratedAtLeastOnce = true;

    }catch(e){
      // It's ok if /facets not implemented in backend version
      // Keep UI usable via search only.
      console.debug("Facets load failed:", e);
      if (showErrorToast) toast(t("toast_facets_failed"));
    }
  }

  function ensureInitialFacetsLoaded(options = {}){
    if (facetsHydratedAtLeastOnce) return Promise.resolve();
    if (!initialFacetsLoadPromise){
      initialFacetsLoadPromise = loadFacets(options).finally(()=>{
        initialFacetsLoadPromise = null;
      });
    }
    return initialFacetsLoadPromise;
  }

  async function runSearch(){
    const startedAt = performance.now();
    hasRunSearchOnce = true;
    const queryText = $("q").value || "";
    const rawFilters = buildFiltersPayload();
    if (!String(queryText || "").trim() && Object.keys(rawFilters).length === 0){
      toast(t("toast_enter_search"));
      return;
    }
    if (isPublicCatalogMode() && !isPublicQueryWithinLimit(queryText)){
      toast("Please log in to run longer searches. Public search is limited to short queries.");
      try{
        window.ProductFinderAuth?.open?.("login");
      }catch(_e){}
      return;
    }
    setBusy(true);
    renderLoadingState();
    persistLastIdealQuerySeed();
    const payload = {
      text: queryText,
      filters: rawFilters,
      limit: 100,
      include_similar: true,
      include_accessories: includeAccessoriesEnabled(),
      sort: normalizeSortModeForAccess($("sortSel")?.value || finderSortModes[activeResultsTab] || "score_desc"),
      allow_ai: !isPublicCatalogMode(),
      debug: false
    };
    const qSig = String(payload.text || "");
    if (qSig !== ignoredAIQuerySignature){
      ignoredAIQuerySignature = qSig;
      ignoredAIFilterPairs = [];
    }
    if (ignoredAIFilterPairs.length){
      payload.ignored_ai_filters = ignoredAIFilterPairs.map(x => ({ k: String(x.k || ""), v: String(x.v || "") }));
    }

    try{
      const data = await postJSON("/search", payload);
      lastInterpretedSearch = data?.interpreted || null;
      const elapsedMs = Math.round(performance.now() - startedAt);
      let exact = data.exact || [];
      let similar = data.similar || [];
      const iLine = $("interpretedLine");
      const uLine = $("understoodLine");
      const sizeLabel = data?.interpreted?.size_label;
      const tiers = data?.interpreted?.result_tiers || null;
      if (iLine) {
        if (tiers && typeof tiers === "object"){
          const exactCount = Number(tiers.exact || 0);
          const closeCount = Number(tiers.close || 0);
          const broaderCount = Number(tiers.broader || 0);
          iLine.textContent = t("results_summary", { exact: exactCount, close: closeCount, broader: broaderCount });
        } else {
          iLine.textContent = sizeLabel ? `Interpreted size: ${sizeLabel}` : "";
        }
      }
      lastUnderstoodFilterChips = Array.isArray(data?.interpreted?.understood_filters) ? data.interpreted.understood_filters : [];
      lastUnderstoodFilterItems = Array.isArray(data?.interpreted?.understood_filter_items) ? data.interpreted.understood_filter_items : [];
      const compareSpec = buildSearchCompareSpec(rawFilters, payload.text);
      renderFinderAIStatus(data?.interpreted || null);
      if (uLine) uLine.textContent = "";
      renderSelected();
      lastProductNameShortFacet = buildProductNameShortFacetFromHits([...exact, ...similar]);
      updateSearchCompareSeed(compareSpec);
      allExactResults = exact;
      allSimilarResults = similar;
      // Re-render chips after results are updated so AI deviation severity colors are current.
      renderSelected();
      currentPage = 1;
      const visibleSimilarCount = similar.filter(h => Number(h?.score ?? 0) >= MIN_SIMILAR_SCORE).length;
      setResultsTab(exact.length ? "exact" : (visibleSimilarCount ? "similar" : "exact"), { resetPage: true, render: false });
      if (pendingFinderViewState){
        const requestedTab = pendingFinderViewState.tab === "similar" ? "similar" : "exact";
        setResultsTab(requestedTab, { resetPage: false, render: false });
        currentPage = Math.max(1, Math.min(pageCountFromTotals(), Number(pendingFinderViewState.page || 1)));
        pendingFinderViewState = null;
      }
      const filterCount = Object.keys(rawFilters || {}).length;
      if ($("stats")) $("stats").textContent = `${exact.length} exact | ${similar.length} similar`;
      renderMetrics(elapsedMs, exact.length, similar.length, filterCount);
      renderPage();
      const backendRecovery = Array.isArray(data?.interpreted?.recovery_actions) ? data.interpreted.recovery_actions : [];
      const recovery = backendRecovery.length ? backendRecovery : buildRecoveryActions();
      showRecovery(exact.length === 0 ? recovery : []);
      loadFacets();
    }catch(e){
      console.error(e);
      toast(t("toast_search_error"));
      if ($("stats")) $("stats").textContent = t("stats_search_failed");
      if ($("interpretedLine")) $("interpretedLine").textContent = "";
      renderFinderAIStatus(null);
      lastInterpretedSearch = null;
      if ($("understoodLine")) $("understoodLine").textContent = "";
      lastUnderstoodFilterChips = [];
      lastUnderstoodFilterItems = [];
      lastImportedFilterItems = [];
      renderSelected();
      renderMetrics(NaN, 0, 0, Object.keys(payload.filters || {}).length);
      showRecovery([]);
    }finally{
      saveFinderState();
      setBusy(false);
    }
  }

  // --------------- Events ----------------
  function wireFacetSearch(){
    let facetTimer = null;
    const ids = ["famSearch","simSearch","mfrSearch","cctSearch","criSearch","ugrSearch","beamSearch","colSearch","shapeSearch","ctrlSearch","cpSearch","insulationSearch","surgeCommonSearch","surgeDifferentialSearch","ipTotalSearch","ipVisibleSearch","ipNonVisibleSearch","ikSearch","ledLifeSearch","warrSearch","lumMaintSearch"];
    ids.forEach(id=>{
      const el = $(id);
      if (!el) return;
      el.addEventListener("focus", ()=>{
        ensureInitialFacetsLoaded({ showErrorToast: false });
      });
      el.addEventListener("input", ()=>{
        if (!facetsHydratedAtLeastOnce){
          ensureInitialFacetsLoaded({ showErrorToast: false });
        }
        clearTimeout(facetTimer);
        facetTimer = setTimeout(()=> loadFacets(), 250);
      });
    });
  }

  function updateFilePickerLabels(){
    const pdfName = $("finderPdfFileName");
    const imageName = $("finderImageFileName");
    const pdfFile = $("finderPdfFile")?.files?.[0];
    const imageFile = $("finderImageFile")?.files?.[0];
    if (pdfName) pdfName.textContent = pdfFile?.name || t("no_file_selected");
    if (imageName) imageName.textContent = imageFile?.name || t("no_file_selected");
  }

  function wireFilePickers(){
    const pdfInput = $("finderPdfFile");
    const imageInput = $("finderImageFile");
    $("btnSelectPdfFile")?.addEventListener("click", ()=> pdfInput?.click());
    $("btnSelectImageFile")?.addEventListener("click", ()=> imageInput?.click());
    pdfInput?.addEventListener("change", updateFilePickerLabels);
    imageInput?.addEventListener("change", updateFilePickerLabels);
    updateFilePickerLabels();
  }

  function isMobileViewport(){
    return window.matchMedia("(max-width: 980px)").matches;
  }

  function openFiltersPanel(){
    const panel = $("filterPanel");
    const backdrop = $("filtersBackdrop");
    if (!panel || !backdrop || !isMobileViewport()) return;
    panel.classList.add("open");
    backdrop.classList.add("show");
    document.body.style.overflow = "hidden";
  }

  function closeFiltersPanel(){
    const panel = $("filterPanel");
    const backdrop = $("filtersBackdrop");
    if (!panel || !backdrop) return;
    panel.classList.remove("open");
    backdrop.classList.remove("show");
    document.body.style.overflow = "";
  }

  function wireMobileFilters(){
    const openBtn = $("btnOpenFilters");
    const closeBtn = $("btnCloseFilters");
    const backdrop = $("filtersBackdrop");
    if (openBtn){
      openBtn.addEventListener("click", ()=>{
        ensureInitialFacetsLoaded({ showErrorToast: false });
        openFiltersPanel();
      });
    }
    if (closeBtn){
      closeBtn.addEventListener("click", ()=> closeFiltersPanel());
    }
    if (backdrop){
      backdrop.addEventListener("click", ()=> closeFiltersPanel());
    }
    window.addEventListener("keydown", (e)=>{
      if (e.key === "Escape") closeFiltersPanel();
    });
    window.addEventListener("resize", ()=>{
      if (!isMobileViewport()) closeFiltersPanel();
    });
  }

  function wireTopButtons(){
    $("btnTools").addEventListener("click", ()=>{
      saveFinderState();
      if (hasPendingToolsCompareState()){
        window.location.href = "/frontend/tools.html";
        return;
      }
      const q = getCurrentQueryText();
      const ff = getCurrentFiltersQueryParam();
      const fs = getCurrentCompareSeedQueryParam();
      const url = q
        ? `/frontend/tools.html?fresh=1&idealQuery=${encodeURIComponent(q)}${ff ? `&finderFilters=${ff}` : ""}${fs ? `&finderSeedSpec=${fs}` : ""}`
        : `/frontend/tools.html?fresh=1${ff ? `&finderFilters=${ff}` : ""}${fs ? `&finderSeedSpec=${fs}` : ""}`;
      window.location.href = url;
    });
    const btnIdealTools = $("btnIdealTools");
    if (btnIdealTools){
      btnIdealTools.addEventListener("click", ()=>{
        saveFinderState();
        const q = String(($("q")?.value || $("qMobile")?.value || "")).trim();
        const ff = getCurrentFiltersQueryParam();
        const fs = getCurrentCompareSeedQueryParam();
        const url = q
          ? `/frontend/tools.html?fresh=1&idealQuery=${encodeURIComponent(q)}&idealAuto=1${ff ? `&finderFilters=${ff}` : ""}${fs ? `&finderSeedSpec=${fs}` : ""}`
          : `/frontend/tools.html?fresh=1${ff ? `&finderFilters=${ff}` : ""}${fs ? `&finderSeedSpec=${fs}` : ""}`;
        window.location.href = url;
      });
    }
    $("btnQuote").addEventListener("click", ()=>{
      saveFinderState();
      window.location.href = "/frontend/quote.html";
    });
    $("btnRun")?.addEventListener("click", ()=>{
      runSearch();
      if (isMobileViewport()) closeFiltersPanel();
    });
    $("btnClearAll").addEventListener("click", ()=>{
      clearAll();
      if (isMobileViewport()) closeFiltersPanel();
    });
    $("btnSaveLearning")?.addEventListener("click", ()=>{
      saveSearchLearning();
    });
    $("sortSel").addEventListener("change", ()=>{
      finderSortModes[activeResultsTab] = normalizeSortModeForAccess($("sortSel")?.value || finderSortModes[activeResultsTab] || "score_desc");
      runSearch();
      saveFinderState();
    });
    $("btnFinderFilesParse")?.addEventListener("click", async ()=>{
      const pdfFile = $("finderPdfFile")?.files?.[0];
      const imageFile = $("finderImageFile")?.files?.[0];
      if (!pdfFile && !imageFile){
        toast(t("toast_select_file_first"));
        return;
      }
      const btn = $("btnFinderFilesParse");
      const prev = btn ? btn.textContent : "";
      if (btn){
        btn.disabled = true;
        btn.textContent = t("analyzing");
      }
      try{
        let merged = {};
        let mergedRefImage = "";
        let imagePayload = null;
        if (pdfFile){
          const pdfRes = await importFiltersFromPdf(pdfFile, { applyNow: false, showToast: false, manageButton: false });
          const p = pdfRes?.parsed && typeof pdfRes.parsed === "object" ? pdfRes.parsed : {};
          merged = { ...merged, ...p };
          if (pdfRes?.compareReferenceImage) mergedRefImage = String(pdfRes.compareReferenceImage);
        }
        if (imageFile){
          const imgRes = await importFiltersFromImage(imageFile, { applyNow: false, showToast: false, manageButton: false });
          const p = imgRes?.parsed && typeof imgRes.parsed === "object" ? imgRes.parsed : {};
          for (const [k, v] of Object.entries(p)){
            if (!(k in merged)) merged[k] = v;
          }
          if (imgRes?.compareReferenceImage) mergedRefImage = String(imgRes.compareReferenceImage);
          imagePayload = imgRes?.raw || null;
        }
        if (!Object.keys(merged).length){
          toast("Could not extract filters from selected file(s)");
          return;
        }
        applyParsedFiltersObject(merged, { clearFirst: true });
        setImportedAiItemsFromParsedFilters(merged);
        if (mergedRefImage){
          try { sessionStorage.setItem(COMPARE_REF_IMAGE_KEY, mergedRefImage); } catch(_e){}
          setCompareReferenceImageInToolsState(mergedRefImage);
        }
        if (imagePayload) renderVisionInfoFromImageParse(imagePayload);
        else hideVisionInfo();
        await runSearch();
        toast("Files analyzed and filters applied");
      }catch(e){
        toast(`Analyze failed: ${String(e?.message || e)}`);
      }finally{
        if (btn){
          btn.disabled = false;
          btn.textContent = prev || t("analyze_files");
        }
      }
    });
    $("btnPrevPage").addEventListener("click", ()=>{
      currentPage = Math.max(1, currentPage - 1);
      renderPage();
    });
    $("btnNextPage").addEventListener("click", ()=>{
      currentPage = Math.min(pageCountFromTotals(), currentPage + 1);
      renderPage();
    });
    $("btnPrevPageTop")?.addEventListener("click", ()=>{
      currentPage = Math.max(1, currentPage - 1);
      renderPage();
    });
    $("btnNextPageTop")?.addEventListener("click", ()=>{
      currentPage = Math.min(pageCountFromTotals(), currentPage + 1);
      renderPage();
    });
    $("btnTabExact")?.addEventListener("click", ()=> setResultsTab("exact"));
    $("btnTabSimilar")?.addEventListener("click", ()=> setResultsTab("similar"));
    function insertNewlineAtCursor(el){
      if (!el) return;
      const start = Number(el.selectionStart ?? el.value.length);
      const end = Number(el.selectionEnd ?? el.value.length);
      const v = String(el.value || "");
      el.value = `${v.slice(0, start)}\n${v.slice(end)}`;
      const pos = start + 1;
      try { el.setSelectionRange(pos, pos); } catch (_e) {}
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }

    $("q").addEventListener("keydown", (e)=>{
      if (e.key !== "Enter") return;
      if (e.ctrlKey || e.metaKey){
        e.preventDefault();
        insertNewlineAtCursor($("q"));
        return;
      }
      e.preventDefault();
      runSearch();
      if (isMobileViewport()) closeFiltersPanel();
    });
    const qMobile = $("qMobile");
    if (qMobile){
      qMobile.addEventListener("keydown", (e)=>{
        if (e.key !== "Enter") return;
        if (e.ctrlKey || e.metaKey){
          e.preventDefault();
          insertNewlineAtCursor(qMobile);
          return;
        }
        e.preventDefault();
        runSearch();
      });
    }
  }

  function initWelcomeGate(){
    const gate = $("welcomeGate");
    const nextBtn = $("btnWelcomeNext");
    if (!gate || !nextBtn) return;
    try{
      if (localStorage.getItem(WELCOME_GATE_KEY) === "1"){
        gate.classList.add("isHidden");
        gate.setAttribute("aria-hidden", "true");
        return;
      }
    }catch(_e){}
    welcomeGateActive = true;
    document.body.classList.add("welcomeActive");
    function closeGate(){
      gate.classList.add("isHidden");
      gate.setAttribute("aria-hidden", "true");
      document.body.classList.remove("welcomeActive");
      welcomeGateActive = false;
      try { localStorage.setItem(WELCOME_GATE_KEY, "1"); } catch(_e){}
      scheduleInitialFacetsWarmup();
      window.setTimeout(()=>{
        try { $("q")?.focus(); } catch(_e){}
      }, 220);
    }
    nextBtn.addEventListener("click", closeGate);
  }

  // init
  initWelcomeGate();
  scheduleOptionalUiScripts();
  initLanguageUI();
  console.log("UI build:", UI_BUILD);
  renderSelected();
  renderMetrics(NaN, 0, 0, 0);
  loadQuoteCart();
  renderPage();
  refreshResultsTabLabels();
  renderQuoteCart();
  wireGroupCollapsers();
  wireGroupNav();
  wireRanges();
  wireFacetSearch();
  wireFilePickers();
  wireQuerySync();
  wireMobileFilters();
  wireTopButtons();
  renderToolsComparePreview();
  window.addEventListener("focus", renderToolsComparePreview);
  window.addEventListener("beforeunload", saveFinderState);
  showOnboardingIfNeeded();
  const restoredFinder = restoreFinderState();
  applyAccessModeUI();
  if (restoredFinder){
    runSearch();
  } else {
    scheduleInitialFacetsWarmup();
  }

  document.addEventListener("productfinder:auth-changed", (ev)=>{
    const authenticated = !!ev?.detail?.authenticated;
    applyAccessModeUI();
    loadQuoteCart();
    renderQuoteCart();
    renderPage();
    renderToolsComparePreview();
    if (authenticated){
      if (restoreFinderState()) runSearch();
      else loadFacets();
      return;
    }
    if (restoreFinderState()) runSearch();
    else loadFacets();
  });





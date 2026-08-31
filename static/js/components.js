/* =========================================================================
 * THKU UI - Reusable Components (v1.0)
 * - Backend'e HIC dokunmaz, sadece client-side render
 * - Kullanim:
 *   THKU_UI.Navbar.render('#navbarRoot', { is_logged_in: true/false, active: 'home' })
 *   THKU_UI.Footer.render('#footerRoot')
 *   THKU_UI.Card.Stats(kutu)
 * ========================================================================= */
(function () {
  'use strict';

  const NAV_DESKTOP_LINKS = [
    { href: '/',                    label: 'Ana Sayfa',     icon: '🏠', active: 'home' },
    { href: '/yemekhane',           label: 'Yemekhane',    icon: '🍽️', active: 'yemekhane' },
    { href: '/otobus-saatleri',     label: 'Otobüs',       icon: '🚌', active: 'otobus' },
    { href: '/bit-pazari',          label: 'Bit Pazarı',   icon: '🛍️', active: 'bitpazari' },
    { href: '/liderlik-tablosu',    label: 'Liderler',     icon: '🏆', active: 'liderlik', color: '#F59E0B' },
  ];
  const NAV_DESKTOP_LOGIN_EXTRA = [
    { href: '/KampusteHayat',       label: 'Kampüste Hayat',  icon: '📸', active: 'kampus' },
    { href: '/kayiplar',            label: 'Kayıp Eşya',      icon: '☂️', active: 'kayiplar' },
    { href: '/ofis-saatleri',       label: 'Ofis Saatleri',   icon: '📅', active: 'ofis' },
    { href: '/forum',               label: 'Forum',           icon: '💬', active: 'forum' },
    { href: '/ders-notlari',        label: 'Ders Notları',    icon: '📚', active: 'notlar' },
    { href: '/ogretmen-listesi',    label: 'Öğretmenler',     icon: '👨‍🏫', active: 'ogretmen' },
    { href: '/profilim',            label: 'Profilim',        icon: '👤', active: 'profil', color: '#818CF8' },
    { href: '/elci-paneli',         label: 'Elçi Panelim',    icon: '📊', active: 'elci',   color: '#F59E0B' },
    { href: '/katkida-bulunanlar',  label: 'Katkıda Bulunanlar', icon: '👥', active: 'katkida' },
    { href: '/moderatorler',        label: 'Moderatör',       icon: '🛡️', active: 'mod' },
  ];
  const DROPDOWN_ELCILIK = [
    { href: '/ogrenci-elcisi',    label: '📋 Elçi Başvurusu' },
    { href: '/liderlik-tablosu',  label: '🏆 Liderlik Tablosu' },
    { href: '/elci-paneli',       label: '📊 Elçi Panelim',  loginOnly: true },
  ];
  const DROPDOWN_KULUPLER = [
    { href: '/fsource',         label: '👨‍💻 FSource Topluluğu' },
    { href: '/utaa',            label: '🇹🇷 UTAA - Uluslararası Türk Akademisyenler' },
    { href: '/kanatlibulten',   label: '✈️ Kanatlı Bülten Havacılık Kulübü' },
    { href: '/ergenekon',       label: '🏛️ Ergenekon Destan Kulübü' },
    { href: '/tarih',           label: '📜 Türk Tarih ve Kültür Kulübü' },
    { href: '/makinemuh',       label: '⚙️ Makine Mühendisliği Topluluğu' },
  ];

  // --- MOBILE MENU (3+1 bölüm) ---
  function buildMobileSections(isLoggedIn){
    const genel = [
      { href:'/',                  label:'Ana Sayfa',        icon:'🏠' },
    ];
    if(isLoggedIn){
      genel.push({ href:'/KampusteHayat',  label:'Kampüste Hayat', icon:'📸' });
      genel.push({ href:'/kayiplar',       label:'Kayıp Eşya',     icon:'☂️' });
      genel.push({ href:'/ofis-saatleri',  label:'Ofis Saatleri',  icon:'📅' });
    }
    genel.push(
      { href:'/yemekhane',        label:'Yemekhane',       icon:'🍽️' },
      { href:'/otobus-saatleri',  label:'Otobüs Saatleri', icon:'🚌' },
      { href:'/bit-pazari',       label:'Bit Pazarı',      icon:'🛍️' },
      { href:'/kroki',            label:'Kampüs Krokisi',  icon:'🗺️' }
    );
    const elcilik = [
      { href:'/liderlik-tablosu', label:'Liderlik Tablosu',   icon:'🏆' },
      { href:'/ogrenci-elcisi',   label:'Elçi Başvurusu',     icon:'📋' },
    ];
    if(isLoggedIn){
      elcilik.push({ href:'/elci-paneli', label:'Elçi Panelim', icon:'📊' });
    }
    const ogrenci = !isLoggedIn ? [] : [
      { href:'/profilim',         label:'Profilim',          icon:'👤' },
      { href:'/forum',            label:'Forum',             icon:'💬' },
      { href:'/ders-notlari',     label:'Ders Notları',     icon:'📚' },
      { href:'/ogretmen-listesi', label:'Öğretmenler',       icon:'👨‍🏫' },
      { href:'/katkida-bulunanlar', label:'Katkıda Bulunanlar', icon:'👥' },
      { href:'/moderatorler',     label:'Moderatör Ekibi',  icon:'🛡️' },
    ];
    const kulupler = DROPDOWN_KULUPLER.map(k => ({ href:k.href, label:k.label.replace(/^[^\s]+\s*/, ''), icon:k.label.split(' ')[0] }));
    return [
      { title:'Genel',          icon:'📋', items:genel },
      { title:'Öğrenci Elçiliği', icon:'🌟', items:elcilik, titleColor:'#F59E0B' },
      { title:'Öğrenci Araçları', icon:'🛠️', items:ogrenci, hideWhenLoggedOut:true },
      { title:'Kulüpler',        icon:'🎓', items:kulupler },
    ];
  }

  function esc(s){ return (s==null?'':String(s)).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function linkColor(styleColor, fallback){
    return (styleColor ? ` style="color:${esc(styleColor)}"` : (fallback?` style="color:${esc(fallback)}"` :''));
  }

  /* ---------------- NAVBAR ---------------- */
  function renderNavbar(root, opts){
    const active = opts.active || 'home';
    const isLoggedIn = !!opts.is_logged_in;
    const sections = buildMobileSections(isLoggedIn);

  // Desktop linkleri
    let navLinksHtml = '';
    NAV_DESKTOP_LINKS.forEach(l => {
      const a = (l.active===active) ? ' active' : '';
      navLinksHtml += `<a href="${esc(l.href)}" class="nav-link${a}"${linkColor(l.color)}>${esc(l.label)}</a>\n`;
    });
    // Logged in ise SADECE 2 kritik ekstra: Forum + Ders Notları
    if(isLoggedIn){
      [
        { href:'/forum', label:'Forum', icon:'💬', active:'forum' },
        { href:'/ders-notlari', label:'Ders Notları', icon:'📚', active:'notlar' }
      ].forEach(l => {
        const a = (l.active===active) ? ' active' : '';
        navLinksHtml += `<a href="${esc(l.href)}" class="nav-link${a}">${esc(l.label)}</a>\n`;
      });
    }
    // Dropdowns: Elcilik + Kulupler
    navLinksHtml += dropdownHtml('🌟 Elçilik', DROPDOWN_ELCILIK, isLoggedIn);
    navLinksHtml += dropdownHtml('🎓 Kulüpler', DROPDOWN_KULUPLER, isLoggedIn);
    // Logged in ise EN SON Profilim (SADECE 1 KEZ!)
    if(isLoggedIn){
      navLinksHtml += `<a href="/profilim" class="nav-link" style="color:#818cf8;">👤 Profilim</a>`;
    }

    // Auth (sag ust)
    let authHtml = '';
    if(isLoggedIn){
      authHtml = `
        <button class="btn btn-secondary" id="logoutBtn">Çıkış</button>`;
    } else {
      authHtml = `
        <a href="/login" class="btn btn-secondary">Giriş</a>
        <a href="/signup" class="btn btn-primary">Kayıt Ol</a>`;
    }

    // Mobile menu
    let mobileSectionsHtml = '';
    sections.forEach((sec, idx) => {
      if (sec.hideWhenLoggedOut && !isLoggedIn) return;
      const loggedIn = (idx === 2);
      const idAttr = loggedIn ? ' id="mobileLoggedInLinks" style="display:none;"' : '';
      mobileSectionsHtml += `
    <nav class="mobile-nav-section" aria-label="${esc(sec.title)}"${idAttr}>
      <div class="mobile-nav-title"${sec.titleColor?` style="color:${esc(sec.titleColor)};"`:''}>${esc(sec.icon)} ${esc(sec.title)}</div>\n`;
      sec.items.forEach(it => {
        mobileSectionsHtml += `      <a class="mobile-nav-link" href="${esc(it.href)}"><span class="icon" aria-hidden="true">${esc(it.icon)}</span>${esc(it.label)}</a>\n`;
      });
      mobileSectionsHtml += `    </nav>\n`;
    });

    const tmpl = `
<!-- Accessibility Skip link (WCAG 2.1) -->
<a href="#main-content" class="skip-link">Ana içeriğe atla</a>

<header class="site-header" role="banner">
  <div class="container nav-inner">
    <a href="/" class="brand" aria-label="THKÜ Öğrenci Portalı Ana Sayfa">
      <span class="brand-mark" aria-hidden="true">
        <img src="/static/kedi.ico" alt="Logo" width="36" height="36" style="border-radius: 8px; object-fit: cover;">
      </span>
      <span class="brand-text">
        <span class="brand-title">THKÜ</span>
        <span class="brand-sub">Öğrenci Portalı</span>
      </span>
    </a>

    <nav class="nav-desktop" id="navDesktop" role="navigation" aria-label="Ana menü">
      ${navLinksHtml}
    </nav>

    <div class="nav-auth" role="navigation" aria-label="Hesap menüsü">
      ${authHtml}
    </div>

    <button class="hamburger" id="hamburgerBtn" aria-expanded="false" aria-controls="mobileDrawer" aria-label="Menüyü aç">
      <span></span><span></span><span></span>
    </button>
  </div>
</header>

<!-- Mobile Drawer -->
<div class="mobile-backdrop" id="mobileBackdrop" hidden></div>
<div class="mobile-drawer" id="mobileDrawer" role="dialog" aria-modal="true" aria-label="Mobil menü" tabindex="-1">
  <div class="mobile-header">
    <div class="mobile-title">Menü</div>
    <button class="mobile-close" id="mobileClose" aria-label="Menüyü kapat">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6L18 18M6 18L18 6"/></svg>
    </button>
  </div>
  <div class="mobile-body" role="menu">
    ${mobileSectionsHtml}

    <div class="mobile-auth" id="mobileAuth">
      ${isLoggedIn ? `
        <button class="btn btn-primary btn-block" id="mobileLogoutBtn">Çıkış</button>
      ` : `
        <a href="/login" class="btn btn-secondary btn-block">Giriş</a>
        <a href="/signup" class="btn btn-primary btn-block">Kayıt Ol</a>
      `}
    </div>
  </div>
</div>
`.trim();

    const r = typeof root === 'string' ? document.querySelector(root) : root;
    if(!r) return;
    r.innerHTML = tmpl;
    bindNav(root, opts);
  }

  function dropdownHtml(label, items, isLoggedIn){
    let inner = '';
    items.forEach(it => {
      if (it.loginOnly && !isLoggedIn) return;
      inner += `<a class="dropdown-item" href="${esc(it.href)}" role="menuitem"><span class="dropdown-item-text">${it.label}</span></a>\n`;
    });
    return `
<div class="dropdown">
  <button class="dropdown-trigger" aria-haspopup="true" aria-expanded="false">
    ${label}
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
  </button>
  <div class="dropdown-menu" role="menu">
    ${inner}
  </div>
</div>`.trim();
  }

  /* ---------------- NAVBAR EVENTS ---------------- */
  function bindNav(root, opts){
    const hamburger = document.getElementById('hamburgerBtn');
    const drawer    = document.getElementById('mobileDrawer');
    const backdrop  = document.getElementById('mobileBackdrop');
    const closeBtn  = document.getElementById('mobileClose');
    const logoutB1  = document.getElementById('logoutBtn');
    const logoutB2  = document.getElementById('mobileLogoutBtn');

    function open(){
      drawer.classList.add('open');
      if(backdrop) { backdrop.hidden = false; }
      hamburger.setAttribute('aria-expanded','true');
      document.body.style.overflow='hidden';
      try { setTimeout(()=>closeBtn && closeBtn.focus(), 50); } catch(_){}
    }
    function close(){
      drawer.classList.remove('open');
      if(backdrop) { backdrop.hidden = true; }
      hamburger.setAttribute('aria-expanded','false');
      document.body.style.overflow='';
    }
    hamburger && hamburger.addEventListener('click', ()=> drawer.classList.contains('open') ? close() : open());
    backdrop  && backdrop.addEventListener('click', close);
    closeBtn  && closeBtn.addEventListener('click', close);
    document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') close(); });

    // Mobilde login ise ogrenci araclari goster
    if (opts.is_logged_in) {
      const links = document.getElementById('mobileLoggedInLinks');
      if (links) links.style.display = '';
    }

    // Dropdown klavyle (mobile desktop icin)
    document.querySelectorAll('.dropdown-trigger').forEach(btn=>{
      btn.addEventListener('click', (e)=>{
        e.preventDefault();
        const parent = btn.parentElement;
        const wasOpen = parent.classList.contains('open');
        document.querySelectorAll('.dropdown.open').forEach(d=>d.classList.remove('open'));
        if(!wasOpen) parent.classList.add('open');
        btn.setAttribute('aria-expanded', (!wasOpen).toString());
      });
    });
    document.addEventListener('click', (e)=>{
      if(!e.target.closest('.dropdown')){
        document.querySelectorAll('.dropdown.open').forEach(d=>{
          d.classList.remove('open');
          d.querySelector('.dropdown-trigger')?.setAttribute('aria-expanded','false');
        });
      }
    });

    // Logout (auth.py /logout endpointi POST bekler ama cookie tabanli logout JS ile localStorage + /login yonlendirme yeterli)
    function doLogout(){
      try { localStorage.removeItem('token'); sessionStorage.clear(); } catch(_){}
      // HttpOnly cookie oldugu icin server'a da bir istek atmak gerekirse auth.py /logout var, kullan
      fetch('/logout', { method:'POST', credentials:'include' }).finally(()=> { window.location.href='/login'; });
    }
    logoutB1 && logoutB1.addEventListener('click', doLogout);
    logoutB2 && logoutB2.addEventListener('click', doLogout);
  }

  /* ---------------- FOOTER ---------------- */
  function renderFooter(root){
    const tmpl = `
<footer class="site-footer" role="contentinfo">
  <div class="container footer-grid">
    <div>
      <div class="footer-brand">
        <span class="brand-mark" aria-hidden="true">
          <img src="/static/kedi.ico" alt="Logo" width="36" height="36" style="border-radius: 8px; object-fit: cover;">
        </span>
        <div>
          <div class="footer-title">THKÜ Öğrenci Portalı</div>
          <div class="footer-sub">Öğrenciler için · Öğrenciler tarafından</div>
        </div>
      </div>
      <p class="footer-desc">
        Kampüs hayatını kolaylaştıran, bağımsız öğrenci projesi. Ders notları, yemekhane, otobüs, bit pazarı ve daha fazlası tek yerde.
      </p>
    </div>
    <div>
      <h4 class="footer-heading">Hızlı Erişim</h4>
      <ul class="footer-links">
        <li><a href="/yemekhane">🍽️ Yemekhane</a></li>
        <li><a href="/otobus-saatleri">🚌 Otobüs Saatleri</a></li>
        <li><a href="/bit-pazari">🛍️ Bit Pazarı</a></li>
        <li><a href="/kroki">🗺️ Kampüs Krokisi</a></li>
      </ul>
    </div>
    <div>
      <h4 class="footer-heading">Topluluk</h4>
      <ul class="footer-links">
        <li><a href="/ogrenci-elcisi">🌟 Öğrenci Elçisi Ol</a></li>
        <li><a href="/liderlik-tablosu">🏆 Liderlik Tablosu</a></li>
        <li><a href="/forum">💬 Forum</a></li>
        <li><a href="/katkida-bulunanlar">👥 Katkıda Bulunanlar</a></li>
      </ul>
    </div>
    <div>
      <h4 class="footer-heading">Yasal</h4>
      <ul class="footer-links">
        <li><a href="/moderatorler">🛡️ Moderatör Ekibi</a></li>
        <li><a href="/kayiplar">☂️ Kayıp Eşya</a></li>
        <li><a href="/ofis-saatleri">📅 Ofis Saatleri</a></li>
      </ul>
      <div class="footer-badges">
        <span class="mini-badge" title="Gayriresmi">🏫 Gayriresmi</span>
        <span class="mini-badge" title="Açık kaynak">✨ Öğrenci Projesi</span>
      </div>
    </div>
  </div>
  <div class="container copyright">
    <span>© ${new Date().getFullYear()} THKÜ Öğrenci Portalı · Tüm hakları saklıdır.</span>
    <span class="footer-legal">THK Üniversitesi ile resmi, kurumsal veya hukuki bir bağlantısı yoktur.</span>
  </div>
</footer>
`.trim();
    const r = typeof root === 'string' ? document.querySelector(root) : root;
    if(!r) return;
    r.innerHTML = tmpl;
  }

  /* ---------------- KARTLAR (reusable) ---------------- */
  const Card = {
    Stats(options){
      const {icon, label, value, sub, accent, onClick} = options || {};
      return `
<section class="card-ui card-stat"${onClick?` role="button" tabindex="0" onclick="${esc(onClick)}" onkeydown="if(event.key==='Enter')${esc(onClick).replace(/"/g,'&quot;')}"`:''}>
  <div class="card-stat-icon"${accent?` style="background:${esc(accent)}22;color:${esc(accent)};border-color:${esc(accent)}44;"`:''}>${esc(icon||'📊')}</div>
  <div class="card-stat-body">
    <div class="card-stat-label">${esc(label||'')}</div>
    <div class="card-stat-value">${value==null?'-':esc(String(value))}</div>
    ${sub?`<div class="card-stat-sub">${esc(sub)}</div>`:''}
  </div>
</section>`.trim();
    }
  };

  // Public API
  window.THKU_UI = {
    Navbar: { render: renderNavbar },
    Footer: { render: renderFooter },
    Card
  };
})();

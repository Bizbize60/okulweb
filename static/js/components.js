(function () {
  'use strict';

  // Sayfa Hazır / Kedi Loader Gizleme Kontrolü
  function markPageReady(){
    if (document.body) {
      document.body.classList.add('thku-page-ready');
      document.body.classList.add('loaded');
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', markPageReady);
  } else {
    markPageReady();
  }
  window.addEventListener('load', markPageReady);
  setTimeout(markPageReady, 1200);

  // Üst bant yüksekliğini hesaplama
  function syncBarHeight(){
    var bar = document.querySelector('.unofficial-bar');
    var h = bar ? bar.offsetHeight : 0;
    document.documentElement.style.setProperty('--bar-h', h + 'px');
  }
  window.addEventListener('DOMContentLoaded', syncBarHeight);
  window.addEventListener('resize', syncBarHeight);

  // Navbar Menü Yapısı
  const NAV_DESKTOP_LINKS = [
    { href: '/', label: 'Ana Sayfa', icon: '🏠', active: 'home' },
    { href: '/yemekhane', label: 'Yemekhane', icon: '🍽️', active: 'yemekhane' },
    { href: '/otobus-saatleri', label: 'Otobüs', icon: '🚌', active: 'otobus' },
    { href: '/bit-pazari', label: 'Bit Pazarı', icon: '🛍️', active: 'bitpazari' },
  ];

  function renderNavbar(root, opts){
    const isLoggedIn = !!opts.is_logged_in;
    let navLinksHtml = '';
    NAV_DESKTOP_LINKS.forEach(l => {
      navLinksHtml += `<a href="${l.href}" class="nav-link">${l.label}</a>`;
    });

    let authHtml = isLoggedIn ? 
      `<button class="btn btn-secondary" id="logoutBtn">Çıkış</button>` :
      `<a href="/login" class="btn btn-secondary">Giriş</a><a href="/signup" class="btn btn-primary">Kayıt Ol</a>`;

    const tmpl = `
    <header class="site-header" role="banner">
      <div class="nav-inner">
        <a href="/" class="brand" style="display:flex;align-items:center;gap:10px;text-decoration:none;color:#fff;">
          <img src="/static/kedi.ico" alt="Logo" width="36" height="36" style="border-radius: 8px;">
          <span style="font-weight:700;">THKÜ Portal</span>
        </a>
        <nav class="nav-desktop" style="display:flex;gap:10px;margin-left:20px;">
          ${navLinksHtml}
        </nav>
        <div class="nav-auth" style="margin-left:auto;display:flex;gap:10px;">
          ${authHtml}
        </div>
      </div>
    </header>`.trim();

    const r = typeof root === 'string' ? document.querySelector(root) : root;
    if(r) r.innerHTML = tmpl;
  }

  function renderFooter(root){
    const tmpl = `<footer style="padding:40px;text-align:center;color:#8A8F98;border-top:1px solid rgba(255,255,255,0.06);margin-top:60px;">
      <p>© 2026 THKÜ Öğrenci Portalı · Bağımsız Öğrenci Projesi</p>
    </footer>`;
    const r = typeof root === 'string' ? document.querySelector(root) : root;
    if(r) r.innerHTML = tmpl;
  }

  window.THKU_UI = {
    Navbar: { render: renderNavbar },
    Footer: { render: renderFooter }
  };

  /* ---------- AKILLI SCROLL NAVBAR (Smart Sticky) ---------- */
  let lastScrollY = window.scrollY;
  window.addEventListener('scroll', () => {
    const currentScrollY = window.scrollY;
    if (currentScrollY > 20) {
      document.body.classList.add('nav-scrolled');
    } else {
      document.body.classList.remove('nav-scrolled');
    }

    if (currentScrollY > lastScrollY && currentScrollY > 150) {
      document.body.classList.add('nav-hidden');
    } else if (currentScrollY < lastScrollY - 10 || currentScrollY <= 0) {
      document.body.classList.remove('nav-hidden');
    }
    lastScrollY = currentScrollY;
  });
})();

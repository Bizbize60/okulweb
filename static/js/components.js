(function () {
  'use strict';

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

  function syncBarHeight(){
    var bar = document.querySelector('.unofficial-bar');
    var h = bar ? bar.offsetHeight : 0;
    document.documentElement.style.setProperty('--bar-h', h + 'px');
  }
  window.addEventListener('DOMContentLoaded', syncBarHeight);
  window.addEventListener('load', syncBarHeight);
  window.addEventListener('resize', syncBarHeight);

  function initScrollReveal(){
    var targets = document.querySelectorAll('.reveal-on-scroll');
    if (!targets.length) return;
    var observer = new IntersectionObserver(function(entries, obs){
      entries.forEach(function(entry){
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    targets.forEach(function(el){ observer.observe(el); });
  }
  document.addEventListener('DOMContentLoaded', initScrollReveal);

  const NAV_DESKTOP_LINKS = [
    { href: '/', label: 'Ana Sayfa', icon: '🏠', active: 'home' },
    { href: '/yemekhane', label: 'Yemekhane', icon: '🍽️', active: 'yemekhane' },
    { href: '/otobus-saatleri', label: 'Otobüs', icon: '🚌', active: 'otobus' },
    { href: '/bit-pazari', label: 'Bit Pazarı', icon: '🛍️', active: 'bitpazari' },
    { href: '/liderlik-tablosu', label: 'Liderler', icon: '🏆', active: 'liderlik', color: '#F59E0B' },
  ];

  const DROPDOWN_ELCILIK = [
    { href: '/ogrenci-elcisi', label: '📋 Elçi Başvurusu' },
    { href: '/liderlik-tablosu', label: '🏆 Liderlik Tablosu' },
    { href: '/elci-paneli', label: '📊 Elçi Panelim', loginOnly: true },
  ];

  const DROPDOWN_KULUPLER = [
    { href: '/fsource', label: '👨‍💻 FSource Topluluğu' },
    { href: '/utaa', label: '🇹🇷 UTAA' },
    { href: '/kanatlibulten', label: '✈️ Kanatlı Bülten' },
  ];

  function esc(s){ return (s==null?'':String(s)).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  function renderNavbar(root, opts){
    const active = opts.active || 'home';
    const isLoggedIn = !!opts.is_logged_in;

    let navLinksHtml = '';
    NAV_DESKTOP_LINKS.forEach(l => {
      const activeClass = (l.active === active) ? ' active' : '';
      navLinksHtml += `<a href="${esc(l.href)}" class="nav-link${activeClass}">${esc(l.label)}</a>`;
    });

    if(isLoggedIn){
      navLinksHtml += `<a href="/forum" class="nav-link">Forum</a><a href="/ders-notlari" class="nav-link">Ders Notları</a>`;
    }

    let authHtml = isLoggedIn ? 
      `<button class="btn btn-secondary" id="logoutBtn">Çıkış</button>` :
      `<a href="/login" class="btn btn-secondary">Giriş</a><a href="/signup" class="btn btn-primary">Kayıt Ol</a>`;

    const tmpl = `
    <header class="site-header" role="banner">
      <div class="container nav-inner" style="display:flex;align-items:center;justify-content:space-between;height:68px;max-width:1400px;margin:0 auto;">
        <a href="/" class="brand" style="display:flex;align-items:center;gap:11px;text-decoration:none;color:#fff;">
          <img src="/static/kedi.ico" alt="Logo" width="36" height="36" style="border-radius:8px;object-fit:cover;">
          <div style="display:flex;flex-direction:column;line-height:1.1;">
            <span style="font-weight:700;font-size:1.05rem;">THKÜ</span>
            <span style="font-size:.72rem;color:#8A8F98;">Öğrenci Portalı</span>
          </div>
        </a>
        <nav class="nav-desktop" style="display:flex;align-items:center;gap:4px;">
          ${navLinksHtml}
        </nav>
        <div class="nav-auth" style="display:flex;align-items:center;gap:10px;">
          ${authHtml}
        </div>
      </div>
    </header>`.trim();

    const r = typeof root === 'string' ? document.querySelector(root) : root;
    if(r) r.innerHTML = tmpl;

    const logoutBtn = document.getElementById('logoutBtn');
    if(logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        fetch('/logout', { method:'POST', credentials:'include' }).finally(()=> { window.location.href='/login'; });
      });
    }
  }

  function renderFooter(root){
    const tmpl = `<footer class="site-footer" style="padding:40px 24px;border-top:1px solid rgba(255,255,255,.06);text-align:center;color:#8A8F98;margin-top:80px;">
      <p>© 2026 THKÜ Öğrenci Portalı · Tüm hakları saklıdır.</p>
    </footer>`;
    const r = typeof root === 'string' ? document.querySelector(root) : root;
    if(r) r.innerHTML = tmpl;
  }

  window.THKU_UI = { Navbar: { render: renderNavbar }, Footer: { render: renderFooter } };

  // Smart Sticky Scroll
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

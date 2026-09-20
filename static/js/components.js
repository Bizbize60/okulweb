/* THKU shared components: navbar + footer.
 * Light theme matching homepage target design.
 * Icon set: Lucide (no emoji). Requires lucide UMD on page.
 * API:
 *   THKU_UI.Navbar.render(root, { is_logged_in, active })
 *   THKU_UI.Footer.render(root)
 */
(function () {
  'use strict';

  function markPageReady() {
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

  function refreshIcons() {
    try { if (window.lucide && window.lucide.createIcons) window.lucide.createIcons(); } catch (e) {}
  }

  /* Giriş durumu: jwt_token çerezi varsa kullanıcı giriş yapmış demektir.
   * Şablonlar `is_logged_in: 'auto'` geçerse buradan tespit edilir. */
  function hasJwt() {
    try { return /(?:^|;\s*)jwt_token=[^;]+/.test(document.cookie); }
    catch (e) { return false; }
  }

  function resolveLogin(opts) {
    if (opts && opts.is_logged_in === true) return true;
    return hasJwt();
  }

  /* Lucide ikon paketi sayfada yoksa otomatik yükle (tema bütünlüğü:
   * her sayfada <i data-lucide> çalışır, tek tek eklemeye gerek yok). */
  function ensureLucide() {
    if (window.lucide && window.lucide.createIcons) { refreshIcons(); return; }
    if (document.querySelector('script[data-lucide-loader]')) return;
    var s = document.createElement('script');
    s.src = 'https://unpkg.com/lucide@latest/dist/umd/lucide.min.js';
    s.defer = true;
    s.setAttribute('data-lucide-loader', '1');
    s.onload = refreshIcons;
    document.head.appendChild(s);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureLucide);
  } else {
    ensureLucide();
  }

  function syncBarHeight() {
    var bar = document.querySelector('.unofficial-bar') || document.querySelector('.top-notice');
    var h = bar ? bar.offsetHeight : 0;
    document.documentElement.style.setProperty('--bar-h', h + 'px');
  }
  window.addEventListener('DOMContentLoaded', syncBarHeight);
  window.addEventListener('load', syncBarHeight);
  window.addEventListener('resize', syncBarHeight);

  function initScrollReveal() {
    var targets = document.querySelectorAll('.reveal-on-scroll');
    if (!targets.length) return;
    if (!('IntersectionObserver' in window)) {
      targets.forEach(function (el) { el.classList.add('is-revealed'); });
      return;
    }
    var observer = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    targets.forEach(function (el) { observer.observe(el); });
  }
  document.addEventListener('DOMContentLoaded', initScrollReveal);

  var NAV_DESKTOP_LINKS = [
    { href: '/', label: 'Ana Sayfa', active: 'home', icon: 'house' },
    { href: '/yemekhane', label: 'Yemekhane', active: 'yemekhane', icon: 'utensils' },
    { href: '/otobus-saatleri', label: 'Otobüs', active: 'otobus', icon: 'bus' },
    { href: '/bit-pazari', label: 'Bit Pazarı', active: 'bitpazari', icon: 'package' },
    { href: '/liderlik-tablosu', label: 'Liderler', active: 'liderlik', icon: 'trophy' }
  ];

  var NAV_LOGGED_LINKS = [
    { href: '/forum', label: 'Forum', active: 'forum', icon: 'messages-square' },
    { href: '/ders-notlari', label: 'Ders Notları', active: 'ders', icon: 'book-open' },
    { href: '/profilim', label: 'Profilim', active: 'profil', icon: 'user' }
  ];

  function esc(s) {
    return (s == null ? '' : String(s)).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function linksHtml(list, active) {
    return list.map(function (l) {
      var cls = 'nav-link' + ((l.active && l.active === active) ? ' active' : '');
      var aria = (l.active && l.active === active) ? ' aria-current="page"' : '';
      var ico = l.icon ? '<i data-lucide="' + esc(l.icon) + '"></i>' : '';
      return '<a href="' + esc(l.href) + '" class="' + cls + '"' + aria + '>' + ico + '<span>' + esc(l.label) + '</span></a>';
    }).join('');
  }

  function drawerLinksHtml(list, active) {
    return list.map(function (l) {
      var cls = 'mobile-nav-link' + ((l.active && l.active === active) ? ' active' : '');
      var ico = l.icon ? '<span class="icon"><i data-lucide="' + esc(l.icon) + '"></i></span>' : '';
      return '<a href="' + esc(l.href) + '" class="' + cls + '">' + ico + '<span>' + esc(l.label) + '</span></a>';
    }).join('');
  }

  function closeDrawer() {
    var drawer = document.getElementById('thkuDrawer');
    var backdrop = document.getElementById('thkuBackdrop');
    var btn = document.getElementById('thkuMenuBtn');
    if (drawer) drawer.classList.remove('open');
    if (backdrop && backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
    if (btn) btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  function openDrawer(allLinks, isLoggedIn) {
    closeDrawer();
    var backdrop = document.createElement('div');
    backdrop.className = 'mobile-backdrop';
    backdrop.id = 'thkuBackdrop';
    backdrop.addEventListener('click', closeDrawer);

    var drawer = document.createElement('div');
    drawer.className = 'mobile-drawer';
    drawer.id = 'thkuDrawer';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-label', 'Site menüsü');

    var authHtml = isLoggedIn
      ? '<button class="btn btn-secondary btn-block" id="mLogoutBtn"><i data-lucide="log-out"></i> Çıkış</button>'
      : '<a href="/login" class="btn btn-secondary btn-block">Giriş</a>' +
        '<a href="/signup" class="btn btn-primary btn-block"><i data-lucide="user-plus"></i> Kayıt Ol</a>';

    drawer.innerHTML =
      '<div class="mobile-header">' +
        '<span class="mobile-title">THKÜ Öğrenci Portalı</span>' +
        '<button class="mobile-close" id="thkuCloseBtn" aria-label="Menüyü kapat"><i data-lucide="x"></i></button>' +
      '</div>' +
      '<div class="mobile-body">' +
        '<nav>' + allLinks + '</nav>' +
        '<div class="mobile-auth">' + authHtml + '</div>' +
      '</div>';

    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(function () { drawer.classList.add('open'); });
    refreshIcons();

    document.getElementById('thkuCloseBtn').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function onKey(e) {
      if (e.key === 'Escape') { closeDrawer(); document.removeEventListener('keydown', onKey); }
    });
    var ml = document.getElementById('mLogoutBtn');
    if (ml) ml.addEventListener('click', doLogout);
  }

  function doLogout() {
    fetch('/logout', { method: 'POST', credentials: 'include' })
      .finally(function () { window.location.href = '/login'; });
  }

  function renderNavbar(root, opts) {
    opts = opts || {};
    var active = opts.active || 'home';
    var isLoggedIn = resolveLogin(opts);

    var desktopHtml = linksHtml(NAV_DESKTOP_LINKS, active);
    if (isLoggedIn) desktopHtml += linksHtml(NAV_LOGGED_LINKS, active);
    var allLinks = desktopHtml;
    var drawerList = drawerLinksHtml(NAV_DESKTOP_LINKS.concat(isLoggedIn ? NAV_LOGGED_LINKS : []), active);

    var authHtml = isLoggedIn
      ? '<button class="btn btn-secondary btn-giris" id="logoutBtn"><i data-lucide="log-out"></i> Çıkış</button>'
      : '<a href="/login" class="btn btn-giris">Giriş</a>' +
        '<a href="/signup" class="btn btn-kayit"><i data-lucide="user-plus"></i> Kayıt Ol</a>';

    var tmpl =
      '<header class="site-header" role="banner">' +
        '<div class="container nav-inner">' +
          '<a href="/" class="brand">' +
            '<img class="brand-logo" src="/static/img/logo.png" alt="THKÜ Öğrenci Portalı" width="38" height="38" onerror="this.onerror=null;this.src=\'/static/img/kedi.ico\'">' +
            '<span class="brand-text">' +
              '<span class="brand-title">THKÜ</span>' +
              '<span class="brand-sub">Öğrenci Portalı</span>' +
            '</span>' +
          '</a>' +
          '<nav class="nav-desktop" aria-label="Ana gezinme">' + allLinks + '</nav>' +
          '<div class="nav-auth">' +
            '<label class="nav-search"><i data-lucide="search"></i><input type="search" placeholder="Site içinde ara..." aria-label="Site içinde ara"></label>' +
            authHtml +
          '</div>' +
          '<button class="hamburger" id="thkuMenuBtn" aria-label="Menüyü aç" aria-expanded="false" aria-controls="thkuDrawer">' +
            '<span></span><span></span><span></span>' +
          '</button>' +
        '</div>' +
      '</header>';

    var r = typeof root === 'string' ? document.querySelector(root) : root;
    if (!r) return;
    r.innerHTML = tmpl;
    refreshIcons();
    ensureLucide();

    var logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', doLogout);

    var menuBtn = document.getElementById('thkuMenuBtn');
    if (menuBtn) {
      menuBtn.addEventListener('click', function () {
        var opened = document.getElementById('thkuDrawer');
        if (opened) { closeDrawer(); return; }
        menuBtn.setAttribute('aria-expanded', 'true');
        openDrawer(drawerList, isLoggedIn);
      });
    }
  }

  function renderFooter(root) {
    // Tüm sayfalarda ortak sade footer (ana sayfa ile aynı dil).
    var r = typeof root === 'string' ? document.querySelector(root) : root;
    if (!r) return;
    var tmpl =
      '<footer class="mini-footer">' +
        '<div class="mini-footer-inner">' +
          '<div class="mini-brand"><img class="mini-brand-logo" src="/static/img/logo.png" alt="THKÜ" width="32" height="32" onerror="this.onerror=null;this.src=\'/static/img/kedi.ico\'"><span>THKÜ<small>Öğrenci Portalı</small></span></div>' +
          '<div class="mini-tagline">Daha iyi bir öğrenci hayatı için, birlikte. <i data-lucide="heart"></i></div>' +
          '<div class="mini-links">' +
            '<a href="/haberler">Hakkında</a>' +
            '<a href="/istekler">İletişim</a>' +
            '<a href="/istekler">Destek</a>' +
            '<a href="https://www.thk.edu.tr" target="_blank" rel="noopener noreferrer">Resmi Site</a>' +
            '<span class="socials">' +
              '<a href="#" aria-label="Discord"><i data-lucide="message-circle"></i></a>' +
              '<a href="#" aria-label="Instagram"><i data-lucide="instagram"></i></a>' +
              '<a href="#" aria-label="X"><i data-lucide="twitter"></i></a>' +
              '<a href="#" aria-label="YouTube"><i data-lucide="youtube"></i></a>' +
            '</span>' +
          '</div>' +
        '</div>' +
      '</footer>';
    r.innerHTML = tmpl;
    refreshIcons();
    ensureLucide();
  }

  window.THKU_UI = { Navbar: { render: renderNavbar }, Footer: { render: renderFooter } };

  var lastScrollY = window.scrollY;
  window.addEventListener('scroll', function () {
    var y = window.scrollY;
    if (y > 20) document.body.classList.add('nav-scrolled');
    else document.body.classList.remove('nav-scrolled');
    if (y > lastScrollY && y > 150) document.body.classList.add('nav-hidden');
    else if (y < lastScrollY - 10 || y <= 0) document.body.classList.remove('nav-hidden');
    lastScrollY = y;
  }, { passive: true });
})();

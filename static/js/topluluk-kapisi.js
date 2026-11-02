(function () {
  if (window.ToplulukKapisi) return;

  var style = document.createElement('style');
  style.textContent = [
    '#kapisi-modal{position:fixed;inset:0;z-index:100000;background:rgba(6,8,14,.72);display:flex;align-items:flex-end;justify-content:center;padding:12px;}',
    '#kapisi-modal[hidden]{display:none !important;}',
    '@media (min-width:640px){#kapisi-modal{align-items:center;padding:24px;}}',
    '.kapisi-card{width:min(440px,100%);max-height:min(92vh,760px);overflow:auto;background:#161b27;color:#e8eaf0;border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:20px 18px 16px;box-shadow:0 24px 60px rgba(0,0,0,.45);font-family:inherit;}',
    '.kapisi-card h2{margin:0 0 8px;font-size:1.05rem;letter-spacing:-.02em;}',
    '.kapisi-card p{margin:0;font-size:.92rem;line-height:1.55;color:#c5cada;}',
    '.kapisi-progress{margin-top:10px;font-size:.78rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#f0c878;}',
    '.kapisi-card ul{list-style:none;padding:0;margin:12px 0 4px;}',
    '.kapisi-card li{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:9px 0;border-top:1px solid rgba(255,255,255,.08);font-size:.9rem;}',
    '.kapisi-card a{color:#9ec0ff;text-decoration:none;}',
    '.kapisi-card li span{flex-shrink:0;font-size:.75rem;color:#9aa3b8;}',
    '.kapisi-card li.is-done span{color:#7dcea0;}',
    '.kapisi-card button{width:100%;margin-top:12px;padding:12px 14px;border:0;border-radius:12px;background:#4f8ef7;color:#fff;font:inherit;font-weight:700;cursor:pointer;}',
  ].join('');
  document.head.appendChild(style);

  function esc(value) {
    return String(value || '').replace(/[&<>"']/g, function (ch) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch];
    });
  }

  function root() {
    var modal = document.getElementById('kapisi-modal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'kapisi-modal';
    modal.hidden = true;
    modal.innerHTML = '<div class="kapisi-card" role="dialog" aria-modal="true" aria-labelledby="kapisi-title"><h2 id="kapisi-title"></h2><div class="kapisi-body"></div><button type="button" data-close>Tamam</button></div>';
    document.body.appendChild(modal);
    modal.querySelector('[data-close]').addEventListener('click', close);
    modal.addEventListener('click', function (event) {
      if (event.target === modal) close();
    });
    return modal;
  }

  function close() {
    var modal = document.getElementById('kapisi-modal');
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = '';
  }

  function open(title, body) {
    var modal = root();
    modal.querySelector('#kapisi-title').textContent = title;
    modal.querySelector('.kapisi-body').innerHTML = body;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    var button = modal.querySelector('[data-close]');
    button.onclick = close;
    button.focus();
    return button;
  }

  window.ToplulukKapisi = {
    showRemoved: function (message) {
      var button = open('Hesabınız silindi', '<p>' + esc(message || 'Hesabınız silinmiştir.') + '</p>');
      button.onclick = function () {
        window.location.href = '/';
      };
    },
    showActivity: function (data) {
      data = data || {};
      var done = {};
      (data.completed || []).forEach(function (id) { done[id] = true; });
      var items = (data.activities || []).map(function (item) {
        var href = String(item.href || '').charAt(0) === '/' ? item.href : '/';
        var state = done[item.id] ? 'is-done' : '';
        var mark = done[item.id] ? 'Tamam' : 'Eksik';
        return '<li class="' + state + '"><a href="' + esc(href) + '">' + esc(item.label) + '</a><span>' + mark + '</span></li>';
      }).join('');
      var count = (data.completed || []).length;
      var required = data.required || 2;
      open(
        'Aktiflik gerekli',
        '<p>' + esc(data.message || '') + '</p>' +
        '<div class="kapisi-progress">' + count + '/' + required + ' katkı</div>' +
        '<ul>' + items + '</ul>'
      );
    },
    consume: function (data) {
      if (data && data.code === 'account_removed') {
        this.showRemoved(data.message);
        return true;
      }
      return false;
    },
  };
})();

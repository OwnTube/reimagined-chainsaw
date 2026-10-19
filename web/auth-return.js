/* Only the pinned local client may be an authentication return destination. */
(() => {
  'use strict';
  window.mewtubeAuthReturn = search => {
    const target = new URLSearchParams(search).get('return_to');
    return /^\/official(?:\?v=[A-Za-z0-9_-]{11})?$/.test(target || '') ? target : null;
  };
})();

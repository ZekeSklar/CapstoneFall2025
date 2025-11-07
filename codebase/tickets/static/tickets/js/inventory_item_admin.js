(function(){
  function ready(fn){
    if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', fn); }
    else { fn(); }
  }

  function enforceSingleLetter(input){
    if(!input) return;
    input.setAttribute('maxlength','1');
    input.setAttribute('pattern','[A-Za-z]');
    input.setAttribute('title','Single letter A-Z');
    input.addEventListener('input', function(){
      let v = (input.value || '').toString();
      // Keep letters only, uppercase, single char
      v = v.replace(/[^A-Za-z]/g, '').toUpperCase();
      if(v.length > 1) v = v.slice(0,1);
      if(input.value !== v) input.value = v;
    });
    input.addEventListener('blur', function(){
      input.value = (input.value || '').replace(/[^A-Za-z]/g, '').toUpperCase().slice(0,1);
    });
  }

  ready(function(){
    var el = document.getElementById('id_shelf_row');
    enforceSingleLetter(el);

    // Enhance compatible_printers with a bulk picker button
    try {
      function findSelect(){
        return document.getElementById('id_compatible_printers')
          || document.querySelector('select[name="compatible_printers"]')
          || null;
      }
      function ensureButton(){
        var sel = findSelect();
        if (!sel) return sel;
        var wrapper = sel.closest('.related-widget-wrapper') || sel.parentElement;
        if (!wrapper || wrapper.dataset.pickBtnInjected === '1') return sel;
        var pickUrl = sel.getAttribute('data-pick-url') || '/admin/tickets/inventoryitem/pick_printers/';
        var btn = document.createElement('a');
        btn.href = pickUrl;
        btn.className = 'button';
        btn.textContent = 'Pick printers...';
        btn.style.marginLeft = '0.5rem';
        btn.title = 'Pick multiple printers by make/model';
        btn.addEventListener('click', function(ev){
          ev.preventDefault();
          try {
            var ids = [];
            for (var i=0;i<sel.options.length;i++){ if(sel.options[i].selected){ ids.push(sel.options[i].value); } }
            var url = pickUrl;
            if (ids.length) {
              url += (url.indexOf('?')>-1? '&' : '?') + 'selected=' + encodeURIComponent(ids.join(','));
            }
            window.open(url, 'pick_printers', 'width=900,height=650,menubar=0,toolbar=0,location=0');
          } catch(_e) {}
        });
        // If the add-related (+) link exists, replace it with our picker
        try {
          var addLink = wrapper.querySelector('a.related-widget-wrapper-link.add-related');
          if (addLink) {
            // Hide the original add button and insert ours after it
            addLink.style.display = 'none';
            addLink.insertAdjacentElement('afterend', btn);
          } else {
            wrapper.appendChild(btn);
          }
        } catch(_e) {
          // Fallback
          wrapper.appendChild(btn);
        }
        wrapper.dataset.pickBtnInjected = '1';
        // Expose a helper for the popup to call
        window.ticketsAddCompatiblePrinters = function(items){
          if (!sel || !items || !items.length) return;
          items.forEach(function(it){
            var idStr = String(it.id);
            var existsIndex = -1;
            for (var i=0;i<sel.options.length;i++){ if (sel.options[i].value === idStr) { existsIndex = i; break; } }
            if (existsIndex === -1) {
              var opt = document.createElement('option');
              opt.value = idStr;
              opt.text = it.label || ('Printer #' + idStr);
              opt.selected = true;
              sel.appendChild(opt);
            } else {
              sel.options[existsIndex].selected = true;
            }
          });
          try { sel.dispatchEvent(new Event('change', {bubbles:true})); } catch(_e) {}
        };
        return sel;
      }
      // Run once after a tiny delay to let admin widgets initialize
      setTimeout(ensureButton, 0);
      // Observe for dynamic changes just in case
      try {
        var root = document.getElementById('content') || document.body;
        var mo = new MutationObserver(function(){ ensureButton(); });
        mo.observe(root, { childList: true, subtree: true });
      } catch(_e) {}
    } catch(_e) {}
  });
})();


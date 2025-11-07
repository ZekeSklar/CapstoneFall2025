// Simple one-click delete helper for Django TabularInline rows.
// Adds a small "Delete" button next to each inline DELETE checkbox.
// Clicking it checks the box and optionally submits the form (with confirm).
(function(){
  function ready(fn){
    if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', fn); }
    else { fn(); }
  }

  function enhanceDeleteCheckbox(cb){
    if(!cb || cb.dataset.enhanced === '1') return;
    cb.dataset.enhanced = '1';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Delete';
    btn.style.marginLeft = '0.5rem';
    btn.className = 'one-click-delete-btn';

    btn.addEventListener('click', function(ev){
      ev.preventDefault();
      try { cb.checked = true; } catch(_e) {}
      const row = cb.closest('tr') || cb.closest('.inline-related');
      if(row){ row.style.opacity = '0.55'; row.style.transition = 'opacity .2s'; }
      const form = cb.form || document.querySelector('form#change-form') || document.querySelector('form');
      // Hold Shift to skip confirm and submit immediately.
      const auto = ev.shiftKey || window.confirm('Delete this comment now and save changes?');
      if(auto && form){
        // Ensure the admin treats this as a regular Save
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = '_save';
        hidden.value = 'Save';
        form.appendChild(hidden);
        form.submit();
      }
    });

    // Insert button right after the checkbox
    cb.insertAdjacentElement('afterend', btn);

    // If the user clicks the built-in delete checkbox directly, auto-submit too
    cb.addEventListener('change', function(){
      if(!cb.checked) return;
      const form = cb.form || document.querySelector('form#change-form') || document.querySelector('form');
      const ok = window.confirm('Delete this comment now and save changes?');
      if(ok && form){
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = '_save';
        hidden.value = 'Save';
        form.appendChild(hidden);
        form.submit();
      } else if(!ok) {
        try { cb.checked = false; } catch(_e) {}
      }
    });
  }

  function scan(){
    // Target any inline delete checkbox (name ends with -DELETE)
    const boxes = document.querySelectorAll(".inline-group input[type='checkbox'][name$='-DELETE']");
    boxes.forEach(enhanceDeleteCheckbox);
  }

  ready(scan);
  // In case inlines are added dynamically (add another link), observe mutations
  try {
    const root = document.querySelector('#content') || document.body;
    const mo = new MutationObserver(function(){ scan(); });
    mo.observe(root, { childList: true, subtree: true });
  } catch(_e) { /* ignore */ }
})();


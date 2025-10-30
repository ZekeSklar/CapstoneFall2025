(function(){
  function ready(fn){
    if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', fn); }
    else { fn(); }
  }

  function enforceSingleLetter(input){
    if(!input) return;
    input.setAttribute('maxlength','1');
    input.setAttribute('pattern','[A-Za-z]');
    input.setAttribute('title','Single letter A–Z');
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
  });
})();


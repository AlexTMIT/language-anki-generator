document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.btn').forEach(b=>{
    b.addEventListener('mousedown', ()=>b.style.transform='translateY(0)');
    ['mouseup','mouseleave'].forEach(ev=>b.addEventListener(ev,()=>b.style.transform=''));
  });
});
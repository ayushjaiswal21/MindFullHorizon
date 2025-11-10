
function toggleFaq(btn) {
    var item = btn.parentElement;
    var isActive = item.classList.contains('active');
    document.querySelectorAll('.faq-item').forEach(function(faq) {
        faq.classList.remove('active');
    });
    if (!isActive) {
        item.classList.add('active');
    }
}

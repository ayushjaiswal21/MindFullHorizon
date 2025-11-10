document.addEventListener('DOMContentLoaded', function() {
    const printBtn = document.getElementById('print-doc-btn');
    if (printBtn) {
        printBtn.addEventListener('click', function() {
            window.print();
        });
    }
});

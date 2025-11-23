function toggleYogaVideos() {
    const section = document.getElementById('yoga-videos-section');
    const btn = document.getElementById('show-videos-btn');
    if (section.classList.contains('hidden')) {
        section.classList.remove('hidden');
        btn.innerHTML = '<i class="fas fa-video mr-2"></i>Hide Yoga Video Library';
        btn.setAttribute('aria-expanded', 'true');
    } else {
        section.classList.add('hidden');
        btn.innerHTML = '<i class="fas fa-video mr-2"></i>Show Yoga Video Library';
        btn.setAttribute('aria-expanded', 'false');
    }
}
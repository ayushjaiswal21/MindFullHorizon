
// Word count functionality
function updateWordCount() {
    const content = document.getElementById('content').value;
    const wordCount = content.trim() === '' ? 0 : content.trim().split(/\s+/).length;
    document.getElementById('wordCount').textContent = wordCount;
}

// Preview functionality
function togglePreview() {
    const container = document.getElementById('previewContainer');
    const toggleText = document.getElementById('previewToggleText');
    
    if (container.classList.contains('hidden')) {
        updatePreview();
        container.classList.remove('hidden');
        toggleText.textContent = 'Hide Preview';
    } else {
        container.classList.add('hidden');
        toggleText.textContent = 'Show Preview';
    }
}

function updatePreview() {
    const title = document.getElementById('title').value || 'Untitled Post';
    const category = document.getElementById('category').value;
    const tags = document.getElementById('tags').value;
    const content = document.getElementById('content').value || 'No content yet...';
    
    document.getElementById('previewTitle').textContent = title;
    document.getElementById('previewCategory').textContent = category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' ');
    document.getElementById('previewTags').textContent = tags ? `Tags: ${tags}` : '';
    document.getElementById('previewContent').textContent = content;
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    const contentTextarea = document.getElementById('content');
    contentTextarea.addEventListener('input', updateWordCount);
    
    // Auto-resize textarea
    contentTextarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });
    
    // Initial word count
    updateWordCount();
});

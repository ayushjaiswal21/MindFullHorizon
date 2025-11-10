// New content for blog_list_inline_1.js
function toggleDropdown(postId) {
    const dropdown = document.getElementById(`dropdown-${postId}`);
    // Hide all other dropdowns
    document.querySelectorAll('[id^="dropdown-"]').forEach(d => {
        if (d.id !== `dropdown-${postId}`) d.classList.add('hidden');
    });
    dropdown.classList.toggle('hidden');
}

function confirmDelete(postId, title) {
    // Ensure title is not empty
    const displayTitle = title || 'this post';
    document.getElementById('deletePostTitle').textContent = displayTitle;
    document.getElementById('deleteForm').action = `/blog/${postId}/delete`;
    const modal = document.getElementById('deleteModal');
    modal.style.display = 'flex';
    modal.classList.remove('hidden');
}

function hideDeleteModal() {
    const modal = document.getElementById('deleteModal');
    modal.style.display = 'none';
    modal.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', function() {
    // Event delegation for toggleDropdown and confirmDelete buttons
    document.body.addEventListener('click', function(event) {
        const target = event.target.closest('button');

        if (target && target.classList.contains('toggle-dropdown-btn')) {
            const postId = target.dataset.postId;
            toggleDropdown(postId);
            event.stopPropagation(); // Prevent document click listener from immediately closing
        } else if (target && target.classList.contains('confirm-delete-btn')) {
            const postId = target.dataset.postId;
            const postTitle = target.dataset.postTitle;
            confirmDelete(postId, postTitle);
            event.stopPropagation();
        }
    });

    // Event listener for hideDeleteModal button
    document.getElementById('hide-delete-modal-btn')?.addEventListener('click', hideDeleteModal);

    // New logic to close dropdowns when clicking outside
    document.addEventListener('click', function(event) {
        document.querySelectorAll('[id^="dropdown-"]').forEach(dropdown => {
            const button = dropdown.previousElementSibling; // Assuming button is sibling before dropdown
            if (dropdown.classList.contains('hidden')) return; // Already hidden

            if (!dropdown.contains(event.target) && (!button || !button.contains(event.target))) {
                dropdown.classList.add('hidden');
            }
        });
    });
});
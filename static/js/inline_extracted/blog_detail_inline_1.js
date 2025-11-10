
// Like functionality
function toggleLike(postId) {
    fetch(`/api/blog/${postId}/like`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const likeBtn = document.getElementById('likeBtn');
            const likeCount = document.getElementById('likeCount');
            const heartIcon = likeBtn.querySelector('i');
            
            if (data.liked) {
                likeBtn.className = 'flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors bg-red-100 text-red-600';
                heartIcon.className = 'fas fa-heart';
            } else {
                likeBtn.className = 'flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors bg-gray-100 text-gray-600 hover:bg-red-50 hover:text-red-600';
                heartIcon.className = 'far fa-heart';
            }
            
            likeCount.textContent = data.like_count;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessageBox('Error', 'Failed to update like. Please try again.', 'error');
    });
}

// Comment functionality
function addComment() {
    const commentText = document.getElementById('commentText');
    const content = commentText.value.trim();
    
    if (!content) {
        showMessageBox('Error', 'Please enter a comment.', 'error');
        return;
    }
    
    fetch(`/api/blog/{{ post.id }}/comment`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify({ content: content })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            commentText.value = '';
            addCommentToDOM(data.comment);
            document.getElementById('commentCount').textContent = data.comment_count;
            showMessageBox('Success', 'Comment added successfully!', 'success');
        } else {
            showMessageBox('Error', data.message || 'Failed to add comment.', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessageBox('Error', 'Failed to add comment. Please try again.', 'error');
    });
}

function addCommentToDOM(comment) {
    const commentsList = document.getElementById('commentsList');
    const commentHTML = `
        <div class="comment" data-comment-id="${comment.id}">
            <div class="flex items-start space-x-4">
                <div class="w-10 h-10 bg-gradient-to-r from-green-500 to-blue-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                    ${comment.author_name[0].toUpperCase()}
                </div>
                <div class="flex-1">
                    <div class="bg-gray-50 rounded-lg p-4">
                        <div class="flex items-center justify-between mb-2">
                            <h4 class="font-semibold text-gray-900">${comment.author_name}</h4>
                            <span class="text-sm text-gray-500">${comment.created_at}</span>
                        </div>
                        <p class="text-gray-700">${comment.content}</p>
                    </div>
                    {% if session.get('user_id') %}
                    <button onclick="toggleReplyForm(${comment.id})" 
                            class="mt-2 text-sm text-blue-600 hover:text-blue-800">
                        <i class="fas fa-reply mr-1"></i> Reply
                    </button>
                    {% endif %}
                    <div id="replyForm-${comment.id}" class="mt-4 ml-4 hidden">
                        <!-- Reply form will be added here -->
                    </div>
                    <div id="replies-${comment.id}" class="mt-4 ml-4 space-y-3">
                        <!-- Replies will be loaded here -->
                    </div>
                </div>
            </div>
        </div>
    `;
    
    if (commentsList.querySelector('.text-center')) {
        commentsList.innerHTML = commentHTML;
    } else {
        commentsList.insertAdjacentHTML('afterbegin', commentHTML);
    }
}

// Reply functionality
function toggleReplyForm(commentId) {
    const replyForm = document.getElementById(`replyForm-${commentId}`);
    replyForm.classList.toggle('hidden');
    
    if (!replyForm.classList.contains('hidden')) {
        document.getElementById(`replyText-${commentId}`).focus();
    }
}

function addReply(commentId) {
    const replyText = document.getElementById(`replyText-${commentId}`);
    const content = replyText.value.trim();
    
    if (!content) {
        showMessageBox('Error', 'Please enter a reply.', 'error');
        return;
    }
    
    fetch(`/api/blog/{{ post.id }}/comment`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify({ content: content, parent_id: commentId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            replyText.value = '';
            toggleReplyForm(commentId);
            loadReplies(commentId);
            document.getElementById('commentCount').textContent = data.comment_count;
            showMessageBox('Success', 'Reply added successfully!', 'success');
        } else {
            showMessageBox('Error', data.message || 'Failed to add reply.', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessageBox('Error', 'Failed to add reply. Please try again.', 'error');
    });
}

function loadReplies(commentId) {
    fetch(`/api/blog/{{ post.id }}/comments/${commentId}/replies`)
    .then(response => response.json())
    .then(data => {
        const repliesContainer = document.getElementById(`replies-${commentId}`);
        repliesContainer.innerHTML = data.replies.map(reply => `
            <div class="bg-gray-100 rounded-lg p-3">
                <div class="flex items-center justify-between mb-1">
                    <h5 class="font-medium text-gray-900 text-sm">${reply.author_name}</h5>
                    <span class="text-xs text-gray-500">${reply.created_at}</span>
                </div>
                <p class="text-gray-700 text-sm">${reply.content}</p>
            </div>
        `).join('');
    })
    .catch(error => {
        console.error('Error loading replies:', error);
    });
}

// Share functionality
function sharePost() {
    if (navigator.share) {
        navigator.share({
            title: '{{ post.title }}',
            text: 'Check out this blog post on mental health:',
            url: window.location.href
        });
    } else {
        // Fallback: copy URL to clipboard
        navigator.clipboard.writeText(window.location.href).then(() => {
            showMessageBox('Success', 'Post URL copied to clipboard!', 'success');
        }).catch(() => {
            showMessageBox('Info', 'Share this post: ' + window.location.href, 'info');
        });
    }
}

// Delete functionality
function confirmDelete() {
    const modal = document.getElementById('deleteModal');
    modal.style.display = 'flex';
    modal.classList.remove('hidden');
}

function hideDeleteModal() {
    const modal = document.getElementById('deleteModal');
    modal.style.display = 'none';
    modal.classList.add('hidden');
}

// Load replies on page load
document.addEventListener('DOMContentLoaded', function() {
    const comments = document.querySelectorAll('.comment');
    comments.forEach(comment => {
        const commentId = comment.dataset.commentId;
        loadReplies(commentId);
    });
});

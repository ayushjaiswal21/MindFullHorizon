
        // Initialize advanced features on page load
        document.addEventListener('DOMContentLoaded', function() {
            if (typeof initializeChartJS === 'function') {
                initializeChartJS();
            }

            // Initialize advanced UI features after scripts are loaded
            setTimeout(function() {
                if (typeof initializeAdvancedUI === 'function') {
                    initializeAdvancedUI();
                }
            }, 100);

            // Show loading overlay for dynamic content
            hideLoadingOverlay();
        });

        // Advanced UI Functions
        function initializeAdvancedUI() {
            // Initialize smooth scrolling
            initializeSmoothScrolling();

            // Initialize tooltips
            initializeTooltips();

            // Initialize animations
            initializeAnimations();

            // Initialize mobile menu
            if (typeof initializeMobileMenu === 'function') {
                initializeMobileMenu();
            }

            // Initialize user menu
            if (typeof initializeUserMenu === 'function') {
                initializeUserMenu();
            }

            // Initialize alerts
            initializeAlerts();

            // Add event listeners for CSP compliance
            document.getElementById('user-menu-btn')?.addEventListener('click', toggleUserMenu);
            document.getElementById('mobile-menu-btn')?.addEventListener('click', toggleMobileMenu);
            document.querySelectorAll('.alert-close-btn').forEach(btn => {
                btn.addEventListener('click', () => closeAlert(btn));
            });
            document.getElementById('scroll-to-top')?.addEventListener('click', scrollToTop);
        }

        function initializeSmoothScrolling() {
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', function (e) {
                    const href = this.getAttribute('href');
                    if (href && href !== '#') {
                        e.preventDefault();
                        const target = document.querySelector(href);
                        if (target) {
                            target.scrollIntoView({
                                behavior: 'smooth',
                                block: 'start'
                            });
                        }
                    }
                });
            });
        }

        function initializeTooltips() {
            // Advanced tooltip functionality
            const tooltipElements = document.querySelectorAll('[data-tooltip]');
            tooltipElements.forEach(element => {
                element.addEventListener('mouseenter', showTooltip);
                element.addEventListener('mouseleave', hideTooltip);
            });
        }

        function showTooltip(e) {
            const tooltip = document.createElement('div');
            tooltip.className = 'advanced-tooltip';
            tooltip.textContent = e.target.getAttribute('data-tooltip');
            document.body.appendChild(tooltip);

            const rect = e.target.getBoundingClientRect();
            tooltip.style.left = rect.left + rect.width / 2 + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
        }

        function hideTooltip() {
            const tooltip = document.querySelector('.advanced-tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        }

        function initializeAnimations() {
            // Intersection Observer for animations
            const observerOptions = {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            };

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('animate-in');
                    }
                });
            }, observerOptions);

            document.querySelectorAll('.animate-on-scroll').forEach(el => {
                observer.observe(el);
            });
        }

        function toggleMobileMenu() {
            const mobileMenu = document.getElementById('mobile-menu');
            const isOpen = mobileMenu.classList.contains('open');

            if (isOpen) {
                mobileMenu.classList.remove('open');
            } else {
                mobileMenu.classList.add('open');
            }
        }

        function toggleUserMenu() {
            const userMenu = document.getElementById('user-menu');
            userMenu.classList.toggle('open');
        }

        function initializeAlerts() {
            // Auto-hide alerts after 5 seconds
            setTimeout(() => {
                document.querySelectorAll('.advanced-alert').forEach(alert => {
                    if (!alert.classList.contains('dismissed')) {
                        closeAlert(alert.querySelector('.alert-close'));
                    }
                });
            }, 5000);
        }

        function closeAlert(button) {
            const alert = button.closest('.advanced-alert');
            alert.classList.add('dismissed');
            setTimeout(() => alert.remove(), 300);
        }

        function scrollToTop() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        }

        function showLoadingOverlay() {
            document.getElementById('loading-overlay').style.display = 'flex';
        }

        function hideLoadingOverlay() {
            setTimeout(() => {
                document.getElementById('loading-overlay').style.display = 'none';
            }, 1000);
        }

        // Close user menu when clicking outside
        document.addEventListener('click', function(e) {
            const userMenu = document.getElementById('user-menu');
            const userMenuBtn = document.querySelector('.user-menu-btn');

            if (!userMenu.contains(e.target) && !userMenuBtn.contains(e.target)) {
                userMenu.classList.remove('open');
            }
        });

        // Advanced keyboard navigation
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                document.getElementById('user-menu')?.classList.remove('open');
                document.getElementById('mobile-menu')?.classList.remove('open');
            }
        });
    
// Ensure google translate wrapper exists and is positioned so it doesn't push nav items
(function ensureGoogleTranslateWrapper(){
  document.addEventListener('DOMContentLoaded', function(){
    let wrapper = document.getElementById('google-translate-wrapper');
    if (!wrapper) {
      // try to find google_translate_element and wrap it
      const el = document.getElementById('google_translate_element') || document.querySelector('.google-translate-element');
      if (el) {
        wrapper = document.createElement('div');
        wrapper.id = 'google-translate-wrapper';
        wrapper.className = 'google-translate-wrapper';
        el.parentNode.insertBefore(wrapper, el);
        wrapper.appendChild(el);
      }
    }
    // keep fixed width so it doesn't push nearby nav links
    if (wrapper) {
      wrapper.style.display = 'inline-block';
      wrapper.style.width = wrapper.style.width || '180px';
      wrapper.style.verticalAlign = 'middle';
      wrapper.style.position = 'relative';
    }
  });
})();
document.addEventListener('click', function(e){
  try {
    const a = e.target.closest && e.target.closest('a[href=""#""]');
    if (!a) return;
    // if anchor is used as JS trigger (has data-* or class), prevent default
    const isTrigger = a.classList.contains('start-assessment-btn') || a.dataset?.assessment || a.dataset?.questionsUrl;
    if (isTrigger || a.querySelector('.start-assessment-btn')) {
      if (e.cancelable) e.preventDefault();
      e.stopPropagation();
      const btn = a.closest('.start-assessment-btn') || a.querySelector('.start-assessment-btn') || a;
      if (btn) { btn.click(); }
    }
  } catch(err){ /* ignore */ }
});

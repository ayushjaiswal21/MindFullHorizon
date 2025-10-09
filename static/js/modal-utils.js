/**
 * MindfulHorizon - Universal Modal Layout Shift Prevention Utility
 * Centralized solution to eliminate scroll jump/layout shift for all modals
 */

class ModalManager {
    constructor() {
        this.scrollbarWidth = 0;
        this.originalBodyStyles = {
            overflow: '',
            paddingRight: '',
            position: ''
        };
        this.isModalOpen = false;
        this.activeModals = new Set();
        
        // Calculate scrollbar width on initialization
        this.calculateScrollbarWidth();
        
        // Bind methods to preserve context
        this.openModal = this.openModal.bind(this);
        this.closeModal = this.closeModal.bind(this);
        this.closeAllModals = this.closeAllModals.bind(this);
    }

    /**
     * Calculate the browser's scrollbar width dynamically
     * This accounts for different browsers and OS settings
     */
    calculateScrollbarWidth() {
        // Method 1: Using window.innerWidth vs documentElement.clientWidth
        const scrollbarWidth1 = window.innerWidth - document.documentElement.clientWidth;
        
        // Method 2: Creating test elements (more reliable)
        const outer = document.createElement('div');
        outer.style.cssText = `
            position: absolute;
            top: -9999px;
            width: 100px;
            height: 100px;
            overflow: scroll;
            visibility: hidden;
        `;
        
        document.body.appendChild(outer);
        const scrollbarWidth2 = outer.offsetWidth - outer.clientWidth;
        document.body.removeChild(outer);
        
        // Use the more reliable method or fallback
        this.scrollbarWidth = scrollbarWidth2 || scrollbarWidth1 || 17; // 17px fallback
        
        // Set CSS custom property for use in stylesheets
        document.documentElement.style.setProperty('--scrollbar-width', `${this.scrollbarWidth}px`);
        
        console.log(`[ModalManager] Detected scrollbar width: ${this.scrollbarWidth}px`);
        return this.scrollbarWidth;
    }

    /**
     * Store original body styles before applying modal styles
     */
    storeOriginalBodyStyles() {
        const computedStyle = window.getComputedStyle(document.body);
        this.originalBodyStyles = {
            overflow: document.body.style.overflow || computedStyle.overflow,
            paddingRight: document.body.style.paddingRight || computedStyle.paddingRight,
            position: document.body.style.position || computedStyle.position
        };
    }

    /**
     * Apply body lock with scrollbar compensation
     * This prevents background scrolling and eliminates layout shift
     */
    applyBodyLock() {
        // Store original styles if this is the first modal
        if (this.activeModals.size === 0) {
            this.storeOriginalBodyStyles();
        }

        // Apply the lock styles
        const body = document.body;
        
        // Prevent scrolling
        body.style.overflow = 'hidden';
        
        // Compensate for scrollbar width to prevent layout shift
        const currentPaddingRight = parseInt(this.originalBodyStyles.paddingRight) || 0;
        body.style.paddingRight = `${currentPaddingRight + this.scrollbarWidth}px`;
        
        // Add class for CSS targeting
        body.classList.add('modal-open');
        
        console.log(`[ModalManager] Body lock applied. Padding: ${currentPaddingRight + this.scrollbarWidth}px`);
    }

    /**
     * Remove body lock and restore original styles
     */
    removeBodyLock() {
        const body = document.body;
        
        // Restore original styles
        body.style.overflow = this.originalBodyStyles.overflow;
        body.style.paddingRight = this.originalBodyStyles.paddingRight;
        
        // Remove class
        body.classList.remove('modal-open');
        
        console.log('[ModalManager] Body lock removed, original styles restored');
    }

    /**
     * Open a modal with layout shift prevention
     * @param {string} modalId - Unique identifier for the modal
     * @param {HTMLElement} modalElement - The modal DOM element
     */
    openModal(modalId, modalElement = null) {
        if (this.activeModals.has(modalId)) {
            console.warn(`[ModalManager] Modal ${modalId} is already open`);
            return;
        }

        // Add to active modals set
        this.activeModals.add(modalId);
        
        // Apply body lock if this is the first modal
        if (this.activeModals.size === 1) {
            this.applyBodyLock();
        }

        // Show the modal element if provided
        if (modalElement) {
            modalElement.style.display = 'flex';
            modalElement.classList.remove('hidden');
            
            // Add ARIA attributes for accessibility
            modalElement.setAttribute('aria-modal', 'true');
            modalElement.setAttribute('role', 'dialog');
        }

        this.isModalOpen = true;
        console.log(`[ModalManager] Modal ${modalId} opened. Active modals: ${this.activeModals.size}`);
        
        // Dispatch custom event for other components to listen to
        window.dispatchEvent(new CustomEvent('modalOpened', { 
            detail: { modalId, activeCount: this.activeModals.size } 
        }));
    }

    /**
     * Close a specific modal
     * @param {string} modalId - Unique identifier for the modal
     * @param {HTMLElement} modalElement - The modal DOM element
     */
    closeModal(modalId, modalElement = null) {
        if (!this.activeModals.has(modalId)) {
            console.warn(`[ModalManager] Modal ${modalId} is not open`);
            return;
        }

        // Remove from active modals set
        this.activeModals.delete(modalId);

        // Hide the modal element if provided
        if (modalElement) {
            modalElement.style.display = 'none';
            modalElement.classList.add('hidden');
            
            // Remove ARIA attributes
            modalElement.removeAttribute('aria-modal');
            modalElement.removeAttribute('role');
        }

        // Remove body lock if no modals are active
        if (this.activeModals.size === 0) {
            this.removeBodyLock();
            this.isModalOpen = false;
        }

        console.log(`[ModalManager] Modal ${modalId} closed. Active modals: ${this.activeModals.size}`);
        
        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('modalClosed', { 
            detail: { modalId, activeCount: this.activeModals.size } 
        }));
    }

    /**
     * Close all active modals (emergency cleanup)
     */
    closeAllModals() {
        const modalIds = Array.from(this.activeModals);
        modalIds.forEach(modalId => {
            this.closeModal(modalId);
        });
        
        // Force cleanup
        this.activeModals.clear();
        this.removeBodyLock();
        this.isModalOpen = false;
        
        console.log('[ModalManager] All modals force-closed');
    }

    /**
     * Get current modal state
     */
    getState() {
        return {
            isModalOpen: this.isModalOpen,
            activeModals: Array.from(this.activeModals),
            scrollbarWidth: this.scrollbarWidth
        };
    }

    /**
     * Recalculate scrollbar width (useful for responsive design changes)
     */
    recalculateScrollbarWidth() {
        const wasOpen = this.isModalOpen;
        const activeModalIds = Array.from(this.activeModals);
        
        // Temporarily close all modals
        if (wasOpen) {
            this.closeAllModals();
        }
        
        // Recalculate
        this.calculateScrollbarWidth();
        
        // Reopen modals if they were open
        if (wasOpen && activeModalIds.length > 0) {
            activeModalIds.forEach(modalId => {
                this.openModal(modalId);
            });
        }
    }
}

// Create global instance
const modalManager = new ModalManager();

// Global utility functions for easy access
window.ModalUtils = {
    open: modalManager.openModal,
    close: modalManager.closeModal,
    closeAll: modalManager.closeAllModals,
    getState: modalManager.getState,
    recalculate: modalManager.recalculateScrollbarWidth
};

// Handle window resize to recalculate scrollbar width
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        modalManager.recalculateScrollbarWidth();
    }, 250);
});

// Handle escape key to close modals
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modalManager.isModalOpen) {
        modalManager.closeAllModals();
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ModalManager, modalManager };
}

console.log('[ModalManager] Initialized successfully');

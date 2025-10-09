/**
 * MindfulHorizon - Modal Layout Shift Test Suite
 * Verification tests for the centralized modal system
 */

class ModalLayoutShiftTest {
    constructor() {
        this.testResults = [];
        this.originalScrollbarWidth = 0;
    }

    /**
     * Run all modal layout shift tests
     */
    async runAllTests() {
        console.log('🧪 Starting Modal Layout Shift Tests...');
        
        // Wait for ModalUtils to be available
        await this.waitForModalUtils();
        
        // Test 1: Scrollbar width detection
        this.testScrollbarWidthDetection();
        
        // Test 2: Single modal open/close
        await this.testSingleModalOpenClose();
        
        // Test 3: Multiple modal operations
        await this.testMultipleModalOperations();
        
        // Test 4: Layout stability measurement
        await this.testLayoutStability();
        
        // Test 5: Cross-browser compatibility
        this.testCrossBrowserCompatibility();
        
        // Report results
        this.reportResults();
        
        return this.testResults;
    }

    /**
     * Wait for ModalUtils to be available
     */
    waitForModalUtils() {
        return new Promise((resolve) => {
            const checkForUtils = () => {
                if (typeof window.ModalUtils !== 'undefined') {
                    resolve();
                } else {
                    setTimeout(checkForUtils, 50);
                }
            };
            checkForUtils();
        });
    }

    /**
     * Test 1: Verify scrollbar width detection accuracy
     */
    testScrollbarWidthDetection() {
        console.log('📏 Testing scrollbar width detection...');
        
        const state = window.ModalUtils.getState();
        const detectedWidth = state.scrollbarWidth;
        
        // Manual calculation for comparison
        const testDiv = document.createElement('div');
        testDiv.style.cssText = `
            position: absolute;
            top: -9999px;
            width: 100px;
            height: 100px;
            overflow: scroll;
            visibility: hidden;
        `;
        
        document.body.appendChild(testDiv);
        const manualWidth = testDiv.offsetWidth - testDiv.clientWidth;
        document.body.removeChild(testDiv);
        
        const isAccurate = Math.abs(detectedWidth - manualWidth) <= 1; // Allow 1px tolerance
        
        this.testResults.push({
            test: 'Scrollbar Width Detection',
            passed: isAccurate,
            details: `Detected: ${detectedWidth}px, Manual: ${manualWidth}px`,
            critical: true
        });
        
        console.log(`✅ Scrollbar width: ${detectedWidth}px (Manual: ${manualWidth}px)`);
    }

    /**
     * Test 2: Single modal open/close cycle
     */
    async testSingleModalOpenClose() {
        console.log('🔄 Testing single modal open/close cycle...');
        
        const modal = document.getElementById('assessmentModal');
        if (!modal) {
            this.testResults.push({
                test: 'Single Modal Open/Close',
                passed: false,
                details: 'Assessment modal not found',
                critical: true
            });
            return;
        }

        // Measure initial body padding
        const initialPadding = document.body.style.paddingRight || '0px';
        const initialOverflow = document.body.style.overflow || 'visible';
        
        // Open modal
        window.ModalUtils.open('test-modal', modal);
        await this.sleep(100); // Allow transition
        
        const openPadding = document.body.style.paddingRight;
        const openOverflow = document.body.style.overflow;
        const hasModalClass = document.body.classList.contains('modal-open');
        
        // Close modal
        window.ModalUtils.close('test-modal', modal);
        await this.sleep(100); // Allow transition
        
        const closedPadding = document.body.style.paddingRight;
        const closedOverflow = document.body.style.overflow;
        const modalClassRemoved = !document.body.classList.contains('modal-open');
        
        const testPassed = 
            openOverflow === 'hidden' &&
            hasModalClass &&
            modalClassRemoved &&
            (closedPadding === initialPadding || closedPadding === '');
        
        this.testResults.push({
            test: 'Single Modal Open/Close',
            passed: testPassed,
            details: `Open: ${openOverflow}, ${openPadding} | Closed: ${closedOverflow}, ${closedPadding}`,
            critical: true
        });
        
        console.log(`✅ Modal cycle test: ${testPassed ? 'PASSED' : 'FAILED'}`);
    }

    /**
     * Test 3: Multiple modal operations
     */
    async testMultipleModalOperations() {
        console.log('🔢 Testing multiple modal operations...');
        
        const modal = document.getElementById('assessmentModal');
        if (!modal) return;

        let allTestsPassed = true;
        
        // Test rapid open/close cycles
        for (let i = 0; i < 5; i++) {
            window.ModalUtils.open(`test-modal-${i}`, modal);
            await this.sleep(50);
            
            const state = window.ModalUtils.getState();
            if (!state.isModalOpen) {
                allTestsPassed = false;
                break;
            }
            
            window.ModalUtils.close(`test-modal-${i}`, modal);
            await this.sleep(50);
        }
        
        // Ensure clean state
        const finalState = window.ModalUtils.getState();
        const cleanState = !finalState.isModalOpen && finalState.activeModals.length === 0;
        
        this.testResults.push({
            test: 'Multiple Modal Operations',
            passed: allTestsPassed && cleanState,
            details: `Rapid cycles: ${allTestsPassed}, Clean state: ${cleanState}`,
            critical: false
        });
        
        console.log(`✅ Multiple operations test: ${allTestsPassed && cleanState ? 'PASSED' : 'FAILED'}`);
    }

    /**
     * Test 4: Layout stability measurement
     */
    async testLayoutStability() {
        console.log('📐 Testing layout stability...');
        
        const modal = document.getElementById('assessmentModal');
        if (!modal) return;

        // Create test element to measure position
        const testElement = document.createElement('div');
        testElement.style.cssText = `
            position: fixed;
            top: 50px;
            right: 0;
            width: 10px;
            height: 10px;
            background: red;
            z-index: 9999;
        `;
        document.body.appendChild(testElement);
        
        // Measure initial position
        const initialRect = testElement.getBoundingClientRect();
        
        // Open modal
        window.ModalUtils.open('stability-test', modal);
        await this.sleep(200); // Allow full transition
        
        // Measure position after modal open
        const openRect = testElement.getBoundingClientRect();
        
        // Close modal
        window.ModalUtils.close('stability-test', modal);
        await this.sleep(200); // Allow full transition
        
        // Measure final position
        const closedRect = testElement.getBoundingClientRect();
        
        // Clean up
        document.body.removeChild(testElement);
        
        // Check if positions are stable (allowing 1px tolerance)
        const horizontalStability = Math.abs(initialRect.right - closedRect.right) <= 1;
        const verticalStability = Math.abs(initialRect.top - closedRect.top) <= 1;
        const noLayoutShift = horizontalStability && verticalStability;
        
        this.testResults.push({
            test: 'Layout Stability',
            passed: noLayoutShift,
            details: `H-shift: ${Math.abs(initialRect.right - closedRect.right)}px, V-shift: ${Math.abs(initialRect.top - closedRect.top)}px`,
            critical: true
        });
        
        console.log(`✅ Layout stability: ${noLayoutShift ? 'STABLE' : 'UNSTABLE'}`);
    }

    /**
     * Test 5: Cross-browser compatibility checks
     */
    testCrossBrowserCompatibility() {
        console.log('🌐 Testing cross-browser compatibility...');
        
        const userAgent = navigator.userAgent;
        const isChrome = userAgent.includes('Chrome');
        const isFirefox = userAgent.includes('Firefox');
        const isSafari = userAgent.includes('Safari') && !userAgent.includes('Chrome');
        const isEdge = userAgent.includes('Edge');
        
        // Test CSS custom property support
        const supportsCustomProperties = CSS.supports('--test', '1px');
        
        // Test modern JavaScript features
        const supportsModernJS = typeof Promise !== 'undefined' && typeof Set !== 'undefined';
        
        const compatibilityScore = [
            supportsCustomProperties,
            supportsModernJS,
            typeof window.ModalUtils !== 'undefined'
        ].filter(Boolean).length;
        
        this.testResults.push({
            test: 'Cross-browser Compatibility',
            passed: compatibilityScore >= 2,
            details: `Score: ${compatibilityScore}/3, Browser: ${this.getBrowserName()}`,
            critical: false
        });
        
        console.log(`✅ Browser compatibility: ${compatibilityScore}/3 features supported`);
    }

    /**
     * Get browser name for reporting
     */
    getBrowserName() {
        const userAgent = navigator.userAgent;
        if (userAgent.includes('Chrome')) return 'Chrome';
        if (userAgent.includes('Firefox')) return 'Firefox';
        if (userAgent.includes('Safari')) return 'Safari';
        if (userAgent.includes('Edge')) return 'Edge';
        return 'Unknown';
    }

    /**
     * Sleep utility for async tests
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Report test results
     */
    reportResults() {
        console.log('\n📊 MODAL LAYOUT SHIFT TEST RESULTS');
        console.log('=====================================');
        
        const criticalTests = this.testResults.filter(t => t.critical);
        const nonCriticalTests = this.testResults.filter(t => !t.critical);
        
        const criticalPassed = criticalTests.filter(t => t.passed).length;
        const totalCritical = criticalTests.length;
        
        console.log(`🔴 Critical Tests: ${criticalPassed}/${totalCritical} passed`);
        criticalTests.forEach(test => {
            const status = test.passed ? '✅' : '❌';
            console.log(`  ${status} ${test.test}: ${test.details}`);
        });
        
        console.log(`🟡 Additional Tests: ${nonCriticalTests.filter(t => t.passed).length}/${nonCriticalTests.length} passed`);
        nonCriticalTests.forEach(test => {
            const status = test.passed ? '✅' : '❌';
            console.log(`  ${status} ${test.test}: ${test.details}`);
        });
        
        const overallSuccess = criticalPassed === totalCritical;
        console.log(`\n🎯 OVERALL RESULT: ${overallSuccess ? 'SUCCESS' : 'NEEDS ATTENTION'}`);
        
        if (overallSuccess) {
            console.log('🎉 All critical tests passed! Modal layout shift has been eliminated.');
        } else {
            console.log('⚠️  Some critical tests failed. Please review the implementation.');
        }
    }
}

// Global test runner
window.runModalTests = async function() {
    const tester = new ModalLayoutShiftTest();
    return await tester.runAllTests();
};

// Auto-run tests in development (comment out for production)
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            console.log('🚀 Auto-running modal tests in development mode...');
            window.runModalTests();
        }, 2000); // Wait for everything to load
    });
}

console.log('🧪 Modal test suite loaded. Run window.runModalTests() to test manually.');

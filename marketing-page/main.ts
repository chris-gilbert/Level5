/**
 * Level5 Marketing Page - Main TypeScript
 * Handles animations, interactions, and dynamic content
 */

// Types
interface AnimationConfig {
    threshold: number;
    rootMargin: string;
    once: boolean;
}

interface StatCounter {
    element: HTMLElement;
    target: number;
    prefix: string;
    suffix: string;
    duration: number;
}

// DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    initNavScroll();
    initScrollAnimations();
    initStatCounters();
    initSmoothScroll();
    initTerminalAnimation();
    initParallax();
});

/**
 * Navigation scroll effect
 */
function initNavScroll(): void {
    const nav = document.getElementById('main-nav');
    if (!nav) return;

    const scrollThreshold = 50;

    window.addEventListener('scroll', () => {
        const currentScroll = window.scrollY;

        // Add/remove scrolled class
        if (currentScroll > scrollThreshold) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
    }, { passive: true });
}

/**
 * Intersection Observer for scroll animations
 */
function initScrollAnimations(): void {
    const config: AnimationConfig = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px',
        once: true
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');

                if (config.once) {
                    observer.unobserve(entry.target);
                }
            }
        });
    }, {
        threshold: config.threshold,
        rootMargin: config.rootMargin
    });

    // Elements to animate
    const animatedElements = document.querySelectorAll(
        '.feature-card, .problem-card, .step, .level, .tech-card'
    );

    animatedElements.forEach((el) => {
        // Add initial state
        (el as HTMLElement).style.opacity = '0';
        (el as HTMLElement).style.transform = 'translateY(30px)';
        (el as HTMLElement).style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// Add animation class handler
const style = document.createElement('style');
style.textContent = `
  .animate-in {
    opacity: 1 !important;
    transform: translateY(0) !important;
  }
`;
document.head.appendChild(style);

/**
 * Animated stat counters
 */
function initStatCounters(): void {
    const savingsElement = document.getElementById('stat-savings');
    if (!savingsElement) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                animateCounter({
                    element: savingsElement,
                    target: 450,
                    prefix: '$',
                    suffix: '',
                    duration: 2000
                });
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    observer.observe(savingsElement);
}

function animateCounter(config: StatCounter): void {
    const { element, target, prefix, suffix, duration } = config;
    const startTime = performance.now();
    const startValue = 0;

    function update(currentTime: number): void {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function (ease-out-cubic)
        const eased = 1 - Math.pow(1 - progress, 3);
        const currentValue = Math.round(startValue + (target - startValue) * eased);

        element.textContent = `${prefix}${currentValue}${suffix}`;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

/**
 * Smooth scroll for anchor links
 */
function initSmoothScroll(): void {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = (anchor as HTMLAnchorElement).getAttribute('href');
            if (!targetId || targetId === '#') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                const navHeight = document.getElementById('main-nav')?.offsetHeight || 0;
                const targetPosition = targetElement.getBoundingClientRect().top + window.scrollY - navHeight;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Terminal code animation
 */
function initTerminalAnimation(): void {
    const codeLines = document.querySelectorAll('.code-line');
    if (codeLines.length === 0) return;

    // Initial state - handled by CSS animation
    // Add hover interactivity
    const terminal = document.querySelector('.terminal-window');
    if (terminal) {
        terminal.addEventListener('mouseenter', () => {
            terminal.classList.add('terminal-active');
        });
        terminal.addEventListener('mouseleave', () => {
            terminal.classList.remove('terminal-active');
        });
    }
}

/**
 * Parallax effect for background
 */
function initParallax(): void {
    const bgGradient = document.querySelector('.bg-gradient') as HTMLElement;
    if (!bgGradient) return;

    let ticking = false;

    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                const scrolled = window.scrollY;
                const rate = scrolled * 0.3;
                bgGradient.style.transform = `translateY(${rate}px)`;
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
}

/**
 * Button hover effects
 */
document.querySelectorAll('.btn').forEach((btn) => {
    btn.addEventListener('mouseenter', (e) => {
        const target = e.target as HTMLElement;
        const rect = target.getBoundingClientRect();
        const x = (e as MouseEvent).clientX - rect.left;
        const y = (e as MouseEvent).clientY - rect.top;

        target.style.setProperty('--mouse-x', `${x}px`);
        target.style.setProperty('--mouse-y', `${y}px`);
    });
});

/**
 * Add dynamic glow effect on mouse move for feature cards
 */
document.querySelectorAll('.feature-card').forEach((card) => {
    card.addEventListener('mousemove', (e) => {
        const target = e.currentTarget as HTMLElement;
        const rect = target.getBoundingClientRect();
        const x = (e as MouseEvent).clientX - rect.left;
        const y = (e as MouseEvent).clientY - rect.top;

        const glow = target.querySelector('.feature-glow') as HTMLElement;
        if (glow) {
            glow.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(249, 115, 22, 0.15), transparent 50%)`;
        }
    });
});

/**
 * Typing effect for hero subtitle (optional enhancement)
 */
function typeWriter(element: HTMLElement, text: string, speed: number = 50): void {
    let i = 0;
    element.textContent = '';

    function type(): void {
        if (i < text.length) {
            element.textContent += text.charAt(i);
            i++;
            setTimeout(type, speed);
        }
    }

    type();
}

// Export for potential module usage
export { initNavScroll, initScrollAnimations, initStatCounters, typeWriter };

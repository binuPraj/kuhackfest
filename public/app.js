/**
 * LogicLens - AI Fallacy Detector & Reasoning Coach
 * Frontend JavaScript - Interactions & UI Logic
 */

// =============================================
// NAVIGATION
// =============================================


// Navbar scroll effect
const navbar = document.getElementById('navbar');

function handleNavbarScroll() {
  if (window.scrollY > 50) {
    navbar?.classList.add('scrolled');
  } else {
    navbar?.classList.remove('scrolled');
  }
}

window.addEventListener('scroll', handleNavbarScroll);

// Mobile navigation toggle
const navToggle = document.getElementById('navToggle');
const navLinks = document.querySelector('.nav-links');

navToggle?.addEventListener('click', () => {
  navLinks?.classList.toggle('active');
  navToggle.classList.toggle('active');
});

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    const href = this.getAttribute('href');
    if (href === '#') return;
    
    e.preventDefault();
    const target = document.querySelector(href);
    
    if (target) {
      target.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
      
      // Close mobile menu if open
      navLinks?.classList.remove('active');
      navToggle?.classList.remove('active');
    }
  });
});

// =============================================
// ACTIVE SECTION HIGHLIGHTING
// =============================================

const navItemsForScroll = document.querySelectorAll('.nav-links a[href^="#"]');

function highlightActiveSection() {
  const scrollPosition = window.scrollY;
  const windowHeight = window.innerHeight;
  const documentHeight = document.documentElement.scrollHeight;
  
  // Get all target elements from nav links
  const sectionData = [];
  navItemsForScroll.forEach(link => {
    const href = link.getAttribute('href');
    if (href && href.startsWith('#')) {
      const targetId = href.substring(1);
      const targetElement = document.getElementById(targetId);
      if (targetElement) {
        // Get the actual position accounting for parent containers
        const rect = targetElement.getBoundingClientRect();
        const absoluteTop = rect.top + window.scrollY;
        sectionData.push({
          id: targetId,
          top: absoluteTop,
          link: link
        });
      }
    }
  });
  
  // Sort by position (top to bottom)
  sectionData.sort((a, b) => a.top - b.top);
  
  // Remove all active classes first
  navItemsForScroll.forEach(item => item.classList.remove('active'));
  
  // Check if at bottom of page
  if (scrollPosition + windowHeight >= documentHeight - 50) {
    // At bottom, activate last section
    if (sectionData.length > 0) {
      sectionData[sectionData.length - 1].link.classList.add('active');
    }
    return;
  }
  
  // Find current section based on scroll position
  // Use a smaller offset for more accurate detection
  const offset = 120;
  let activeSection = null;
  
  for (let i = sectionData.length - 1; i >= 0; i--) {
    if (scrollPosition >= sectionData[i].top - offset) {
      activeSection = sectionData[i];
      break;
    }
  }
  
  // If no section found or at very top, default to first (Home)
  if (!activeSection && sectionData.length > 0) {
    activeSection = sectionData[0];
  }
  
  if (activeSection) {
    activeSection.link.classList.add('active');
  }
}

// Throttle scroll event for better performance
let scrollTimeout;
function throttledHighlight() {
  if (scrollTimeout) return;
  scrollTimeout = setTimeout(() => {
    highlightActiveSection();
    scrollTimeout = null;
  }, 30);
}

window.addEventListener('scroll', throttledHighlight);

// Run on page load and after a slight delay for layout
document.addEventListener('DOMContentLoaded', () => {
  highlightActiveSection();
  setTimeout(highlightActiveSection, 100);
});

// =============================================
// CHAT PAGE FUNCTIONALITY
// =============================================

const chatWelcome = document.getElementById('chatWelcome');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const chatSubmit = document.getElementById('chatSubmit');
const supportBtn = document.getElementById('supportBtn');
const opposeBtn = document.getElementById('opposeBtn');
const examplePrompts = document.querySelectorAll('.example-prompt');

let currentMode = 'support';

// Mode toggle
function setMode(mode) {
  currentMode = mode;
  
  if (mode === 'support') {
    supportBtn?.classList.add('active');
    opposeBtn?.classList.remove('active');
  } else {
    opposeBtn?.classList.add('active');
    supportBtn?.classList.remove('active');
  }
}

supportBtn?.addEventListener('click', () => setMode('support'));
opposeBtn?.addEventListener('click', () => setMode('oppose'));

// Example prompts click
examplePrompts.forEach(prompt => {
  prompt.addEventListener('click', () => {
    const text = prompt.getAttribute('data-prompt');
    if (chatInput && text) {
      chatInput.value = text;
      chatInput.focus();
      autoResizeTextarea(chatInput);
    }
  });
});

// Auto-resize textarea
function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

chatInput?.addEventListener('input', function() {
  autoResizeTextarea(this);
});

// Submit analysis
chatSubmit?.addEventListener('click', handleSubmit);

chatInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
});

function handleSubmit() {
  const text = chatInput?.value.trim();
  if (!text) return;
  
  // Show messages area, hide welcome
  if (chatWelcome && chatMessages) {
    chatWelcome.style.display = 'none';
    chatMessages.classList.add('active');
  }
  
  // Add user message
  addMessage(text, 'user');
  
  // Clear input
  if (chatInput) {
    chatInput.value = '';
    autoResizeTextarea(chatInput);
  }
  
  // Simulate AI response (Frontend only - will be replaced with Flask backend)
  setTimeout(() => {
    addAnalysisResult(text);
  }, 1000);
}

function addMessage(text, type) {
  if (!chatMessages) return;
  
  const message = document.createElement('div');
  message.className = `message message-${type}`;
  message.innerHTML = `
    <div class="message-content">
      <p>${escapeHtml(text)}</p>
    </div>
  `;
  
  chatMessages.appendChild(message);
  scrollToBottom();
}

function addAnalysisResult(userText) {
  if (!chatMessages) return;
  
  // Simulated fallacy detection (Frontend demo - will be replaced with backend)
  const fallacies = [
    {
      name: 'Ad Hominem',
      description: 'This argument attacks the person making the claim rather than the claim itself.',
      confidence: 87,
      explanation: 'The argument dismisses someone\'s opinion based on their credentials rather than addressing the merits of their actual argument.',
      improvement: 'Consider addressing the specific points raised rather than questioning the person\'s qualifications to make them.'
    },
    {
      name: 'Bandwagon Fallacy',
      description: 'This argument assumes something is true or good because many people believe it or do it.',
      confidence: 82,
      explanation: 'The popularity of an action or belief doesn\'t necessarily make it correct or the best choice.',
      improvement: 'Provide specific evidence for why the position is correct, independent of how many people support it.'
    },
    {
      name: 'Slippery Slope',
      description: 'This argument assumes that one event will inevitably lead to a chain of negative events without sufficient evidence.',
      confidence: 79,
      explanation: 'The argument suggests an extreme outcome will follow from a moderate action, without proving the causal chain.',
      improvement: 'Focus on the immediate effects of the proposed change and provide evidence for any predicted consequences.'
    },
    {
      name: 'Straw Man',
      description: 'This argument misrepresents or oversimplifies someone\'s position to make it easier to attack.',
      confidence: 75,
      explanation: 'Instead of addressing the actual argument, a weaker, distorted version is created and attacked.',
      improvement: 'Ensure you\'re responding to what was actually said, not an exaggerated or simplified version.'
    }
  ];
  
  // Pick a random fallacy for demo
  const detected = fallacies[Math.floor(Math.random() * fallacies.length)];
  
  const analysisHtml = `
    <div class="message message-bot">
      <div class="analysis-result">
        <div class="analysis-header">
          <div class="analysis-badge">
            <span>⚠</span>
            ${detected.name}
          </div>
          <span class="analysis-confidence">${detected.confidence}% confidence</span>
        </div>
        <div class="analysis-body">
          <div class="analysis-section">
            <h4>What We Found</h4>
            <p>${detected.description}</p>
          </div>
          <div class="analysis-section">
            <h4>Why It Matters</h4>
            <p>${detected.explanation}</p>
          </div>
          <div class="analysis-section">
            <h4>${currentMode === 'support' ? 'How to Improve' : 'Counter-argument'}</h4>
            <p class="improved-text">${detected.improvement}</p>
          </div>
        </div>
      </div>
    </div>
  `;
  
  chatMessages.insertAdjacentHTML('beforeend', analysisHtml);
  scrollToBottom();
}

function scrollToBottom() {
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// =============================================
// ANIMATIONS & EFFECTS
// =============================================

// Intersection Observer for scroll animations
const observerOptions = {
  threshold: 0.1,
  rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('animate-in');
      observer.unobserve(entry.target);
    }
  });
}, observerOptions);

// Observe masonry cards for animation
document.querySelectorAll('.masonry-card').forEach(card => {
  card.style.opacity = '0';
  card.style.transform = 'translateY(20px)';
  card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
  observer.observe(card);
});

// Add animate-in styles
const style = document.createElement('style');
style.textContent = `
  .animate-in {
    opacity: 1 !important;
    transform: translateY(0) !important;
  }
`;
document.head.appendChild(style);

// =============================================
// ADDITIONAL STYLES (Mobile nav handled in CSS)
// =============================================

// =============================================
// INITIALIZE
// =============================================

document.addEventListener('DOMContentLoaded', () => {
  // Initial navbar check
  handleNavbarScroll();
  
  console.log('LogicLens Frontend Initialized');
});



// Add active state to navigation links based on current page
document.addEventListener('DOMContentLoaded', function() {
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const navLinks = document.querySelectorAll('.nav-links a');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        
        // Check if link matches current page
        if (href === currentPage || 
            (currentPage === 'index.html' && href === '#home') ||
            (currentPage === '' && href === '#home')) {
            link.classList.add('active');
        }
        
        // Special handling for fallacies page
        if (currentPage === 'fallacies.html' && href === 'fallacies.html') {
            link.classList.add('active');
        }
    });
});

// Navbar scroll effect
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  if (window.scrollY > 20) {
    navbar.style.background = 'rgba(10,10,15,0.97)';
  } else {
    navbar.style.background = 'rgba(10,10,15,0.85)';
  }
});

// Mobile menu toggle
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const navLinks = document.querySelector('.nav-links');
if (mobileMenuBtn && navLinks) {
  mobileMenuBtn.addEventListener('click', () => {
    navLinks.classList.toggle('mobile-open');
  });
}

// Hero search loading state
const heroForm = document.getElementById('heroSearchForm');
const searchBtn = document.getElementById('searchBtn');
if (heroForm && searchBtn) {
  heroForm.addEventListener('submit', () => {
    searchBtn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Searching...';
    searchBtn.disabled = true;
  });
}

// Pincode Modal and Location Management
const modalOverlay = document.getElementById('locationModalOverlay');
const pincodeForm = document.getElementById('pincodeForm');
const pincodeInput = document.getElementById('pincodeInput');
const pincodeError = document.getElementById('pincodeError');
const navLocationBtn = document.getElementById('navLocationBtn');
const navLocationText = document.getElementById('navLocationText');

// Helper to get cookie
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// Check and initialize pincode
function initLocation() {
  let pincode = getCookie('pincode') || localStorage.getItem('pincode');
  
  if (pincode && /^\d{6}$/.test(pincode)) {
    localStorage.setItem('pincode', pincode);
  } else {
    // If no valid pincode, show modal
    showLocationModal();
  }
}

function showLocationModal() {
  if (modalOverlay) {
    modalOverlay.style.display = 'flex';
    setTimeout(() => {
      modalOverlay.classList.add('active');
    }, 10);
    if (pincodeInput) {
      const current = localStorage.getItem('pincode');
      if (current) pincodeInput.value = current;
      pincodeInput.focus();
    }
  }
}

function hideLocationModal() {
  if (modalOverlay) {
    modalOverlay.classList.remove('active');
    setTimeout(() => {
      modalOverlay.style.display = 'none';
    }, 300);
  }
}

// Click on navbar badge to edit location
if (navLocationBtn) {
  navLocationBtn.addEventListener('click', showLocationModal);
}

// Handle modal form submit
if (pincodeForm) {
  pincodeForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const pin = pincodeInput.value.trim();
    if (/^\d{6}$/.test(pin)) {
      pincodeError.classList.remove('active');
      localStorage.setItem('pincode', pin);
      document.cookie = `pincode=${pin}; max-age=${30*24*60*60}; path=/`;
      
      hideLocationModal();
      
      // Update hidden inputs across forms
      document.querySelectorAll('input[name="pincode"]').forEach(input => {
        input.value = pin;
      });

      // Reload/redirect to refresh prices for new location
      const query = new URLSearchParams(window.location.search).get('q');
      if (window.location.pathname === '/search' && query) {
        window.location.href = `/search?q=${encodeURIComponent(query)}&pincode=${pin}`;
      } else {
        window.location.reload();
      }
    } else {
      pincodeError.classList.add('active');
    }
  });
}

// Handle clicks outside the modal card to close, but only if they already have a pincode set
if (modalOverlay) {
  modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) {
      const current = localStorage.getItem('pincode');
      if (current && /^\d{6}$/.test(current)) {
        hideLocationModal();
      }
    }
  });
}

// Sync pincode in search forms before submitting
const searchForms = document.querySelectorAll('form[action="/search"]');
searchForms.forEach(form => {
  form.addEventListener('submit', () => {
    const pin = localStorage.getItem('pincode') || '560001';
    let pinInput = form.querySelector('input[name="pincode"]');
    if (!pinInput) {
      pinInput = document.createElement('input');
      pinInput.type = 'hidden';
      pinInput.name = 'pincode';
      form.appendChild(pinInput);
    }
    pinInput.value = pin;
  });
});

// Run initialization
document.addEventListener('DOMContentLoaded', initLocation);

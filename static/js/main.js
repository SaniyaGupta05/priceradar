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

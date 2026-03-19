/**
 * Enhanced Features for Shopora Marketplace
 * - Wishlist management
 * - Recently viewed item tracking
 */

(function() {
  'use strict';

  // Utility function to get CSRF token from meta tag or cookies
  function getCsrfToken() {
    // First try to get from meta tag (most reliable)
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    if (metaToken && metaToken.getAttribute('content')) {
      return metaToken.getAttribute('content');
    }

    // Fallback to cookies
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [key, value] = cookie.trim().split('=');
      if (key === 'csrftoken') {
        return decodeURIComponent(value);
      }
    }
    return null;
  }

  // Wishlist Toggle Handler
  class WishlistManager {
    constructor() {
      this.csrfToken = getCsrfToken();
      this.init();
    }

    init() {
      // Find all wishlist buttons
      document.querySelectorAll('[data-bh-wishlist]').forEach(button => {
        button.addEventListener('click', (e) => this.handleToggle(e, button));
      });
    }

    handleToggle(event, button) {
      event.preventDefault();
      if (!this.csrfToken) {
        console.warn('CSRF token not found. User might not be authenticated.');
        return;
      }

      const itemId = button.dataset.bhWishlist;
      this.toggleWishlist(itemId, button);
    }

    toggleWishlist(itemId, button) {
      button.classList.add('loading');
      button.disabled = true;

      fetch(`/wishlist/toggle/${itemId}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
        },
        body: JSON.stringify({}),
      })
        .then(response => {
          if (!response.ok) throw new Error('Network response was not ok');
          return response.json();
        })
        .then(data => {
          if (data.success) {
            button.classList.toggle('active', data.is_wishlisted);
            this.updateButton(button, data);
            this.showNotification(
              data.is_wishlisted 
                ? '❤️ Added to wishlist' 
                : '♡ Removed from wishlist'
            );
          }
        })
        .catch(error => {
          console.error('Error:', error);
          this.showNotification('Something went wrong. Please try again.', 'error');
        })
        .finally(() => {
          button.classList.remove('loading');
          button.disabled = false;
        });
    }

    updateButton(button, data) {
      const countElement = button.querySelector('[data-bh-wishlist-count]');
      if (countElement) {
        countElement.textContent = data.wishlist_count;
      }
    }

    showNotification(message, type = 'success') {
      const notification = document.createElement('div');
      notification.className = `alert alert-${type === 'error' ? 'danger' : 'success'} position-fixed`;
      notification.style.cssText = 'bottom: 20px; right: 20px; z-index: 9999;';
      notification.textContent = message;
      
      document.body.appendChild(notification);
      
      setTimeout(() => {
        notification.remove();
      }, 3000);
    }
  }

  // Recently Viewed Tracker
  class RecentlyViewedTracker {
    constructor() {
      this.csrfToken = getCsrfToken();
      this.init();
    }

    init() {
      // Track item view if there's a specific item ID
      const itemId = document.body.dataset.itemId;
      if (itemId && this.csrfToken) {
        this.trackView(itemId);
      }
    }

    trackView(itemId) {
      fetch(`/items/${itemId}/track/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
        },
        body: JSON.stringify({}),
      })
        .then(response => {
          if (!response.ok) throw new Error('Failed to track view');
          return response.json();
        })
        .catch(error => {
          console.debug('Could not track view:', error);
          // Silent fail for tracking
        });
    }
  }

  // Helper function to render star rating
  window.renderStars = function(rating, maxRating = 5) {
    let stars = '';
    for (let i = 0; i < maxRating; i++) {
      stars += i < Math.floor(rating) ? '★' : '☆';
    }
    return stars;
  };

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    new WishlistManager();
    new RecentlyViewedTracker();
  });

  // Expose for global access if needed
  window.Shopora = window.Shopora || {};
  window.Shopora.WishlistManager = WishlistManager;
  window.Shopora.RecentlyViewedTracker = RecentlyViewedTracker;
})();

// Polling-based messaging for delivery coordination

class MessagePoller {
    constructor(deliveryId, options = {}) {
        this.deliveryId = deliveryId;
        this.pollInterval = options.pollInterval || 10000; // 10 seconds
        this.lastMessageId = options.lastMessageId || 0;
        this.messageContainer = options.messageContainer || document.getElementById('messages');
        this.statusContainer = options.statusContainer || document.getElementById('delivery-status');
        this.polling = false;
        this.pollTimer = null;
    }
    
    start() {
        if (this.polling) return;
        this.polling = true;
        this.poll();
    }
    
    stop() {
        this.polling = false;
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }
    
    async poll() {
        if (!this.polling) return;
        
        try {
            const response = await fetch(`/api/messages/${this.deliveryId}?after=${this.lastMessageId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Handle new messages
            if (data.messages && data.messages.length > 0) {
                this.appendMessages(data.messages);
                this.lastMessageId = data.messages[data.messages.length - 1].id;
            }
            
            // Update status if changed
            if (this.statusContainer && data.status) {
                this.updateStatus(data.status);
            }
            
        } catch (error) {
            console.error('Polling error:', error);
        }
        
        // Schedule next poll
        if (this.polling) {
            this.pollTimer = setTimeout(() => this.poll(), this.pollInterval);
        }
    }
    
    removeEmptyState() {
        // Remove the "No messages yet" placeholder if it exists
        if (!this.messageContainer) return;
        
        const emptyState = this.messageContainer.querySelector('.chat-empty');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Also check for any div with centered text-muted styling (alternate empty state)
        const altEmptyState = this.messageContainer.querySelector('div[style*="text-align: center"]');
        if (altEmptyState && altEmptyState.textContent.includes('No messages yet')) {
            altEmptyState.remove();
        }
    }
    
    appendMessages(messages) {
        if (!this.messageContainer) return;
        
        // Remove empty state placeholder before adding messages
        this.removeEmptyState();
        
        messages.forEach(msg => {
            // Check if message already exists (prevent duplicates)
            if (this.messageContainer.querySelector(`[data-message-id="${msg.id}"]`)) {
                return;
            }
            
            const messageEl = this.createMessageElement(msg);
            this.messageContainer.appendChild(messageEl);
        });
        
        // Scroll to bottom
        this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
    }
    
    createMessageElement(msg) {
        const div = document.createElement('div');
        div.className = `message ${msg.sender_id === window.currentUserId ? 'message-sent' : 'message-received'}`;
        div.dataset.messageId = msg.id;
        
        const header = document.createElement('div');
        header.className = 'message-header';
        header.innerHTML = `
            <span class="message-sender">${this.escapeHtml(msg.sender_name)}</span>
            <span class="message-time">${this.formatTime(msg.sent_at)}</span>
        `;
        
        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = msg.content;
        
        div.appendChild(header);
        div.appendChild(content);
        
        return div;
    }
    
    updateStatus(status) {
        if (!this.statusContainer) return;
        
        const badge = this.statusContainer.querySelector('.status-badge');
        if (badge) {
            badge.className = `status-badge status-${status}`;
            badge.textContent = status.replace('_', ' ');
        }
        
        // If completed or canceled, stop polling
        if (status === 'completed' || status === 'canceled') {
            this.stop();
            // Optionally show a notification
            this.showNotification(`Delivery has been ${status}.`);
        }
    }
    
    showNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'flash flash-info';
        notification.innerHTML = `
            ${message}
            <button class="flash-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        const flashContainer = document.querySelector('.flash-messages') || document.querySelector('main');
        if (flashContainer) {
            flashContainer.insertBefore(notification, flashContainer.firstChild);
        }
    }
    
    formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Message sending
class MessageSender {
    constructor(deliveryId, options = {}) {
        this.deliveryId = deliveryId;
        this.form = options.form || document.getElementById('message-form');
        this.input = options.input || document.getElementById('message-input');
        this.button = options.button || document.getElementById('send-button');
        this.onMessageSent = options.onMessageSent || (() => {});
        
        if (this.form) {
            this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        }
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        
        const content = this.input?.value?.trim();
        if (!content) return;
        
        // Disable while sending
        if (this.button) this.button.disabled = true;
        if (this.input) this.input.disabled = true;
        
        try {
            const response = await fetch(`/api/messages/${this.deliveryId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ content })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to send message');
            }
            
            const data = await response.json();
            
            // Clear input
            if (this.input) this.input.value = '';
            
            // Callback
            this.onMessageSent(data.message);
            
        } catch (error) {
            console.error('Send error:', error);
            alert('Failed to send message. Please try again.');
        } finally {
            // Re-enable
            if (this.button) this.button.disabled = false;
            if (this.input) {
                this.input.disabled = false;
                this.input.focus();
            }
        }
    }
    
    getCSRFToken() {
        return document.querySelector('input[name="csrf_token"]')?.value || '';
    }
}

// Initialize messaging on pages that need it
document.addEventListener('DOMContentLoaded', function() {
    const messageContainer = document.getElementById('messages');
    const deliveryId = messageContainer?.dataset?.deliveryId;
    
    if (deliveryId) {
        // Get last message ID from existing messages
        const messages = messageContainer.querySelectorAll('.message');
        let lastMessageId = 0;
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            lastMessageId = parseInt(lastMessage.dataset.messageId) || 0;
        }
        
        // Start polling
        const poller = new MessagePoller(deliveryId, {
            lastMessageId: lastMessageId,
            messageContainer: messageContainer
        });
        poller.start();
        
        // Set up message sending
        const sender = new MessageSender(deliveryId, {
            onMessageSent: (msg) => {
                // Message will be picked up by next poll, but we can add it immediately
                poller.appendMessages([msg]);
                poller.lastMessageId = msg.id;
            }
        });
        
        // Stop polling when leaving page
        window.addEventListener('beforeunload', () => poller.stop());
    }
});
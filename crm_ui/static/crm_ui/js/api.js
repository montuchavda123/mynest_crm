/**
 * Tele CRM API & Common JS Helpers
 */

const API = {
    // Helper for Fetch requests
    async request(url, method = 'GET', data = null) {
        console.log(`[API Call] ${method} ${url}`, data);
        
        // Mocking the response for now
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({
                    success: true,
                    message: "Operation completed successfully (MOCKED)",
                    data: data
                });
            }, 500);
        });
        
        /* 
        Real implementation would be:
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken')
            },
            body: data ? JSON.stringify(data) : null
        });
        return await response.json();
        */
    },

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },
    
    // UI Feedback Helpers
    showAlert(message, type = 'success') {
        // Simple toast or alert mechanism
        const alertPlaceholder = document.getElementById('alertPlaceholder');
        if (alertPlaceholder) {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = [
                `<div class="alert alert-${type} alert-dismissible fade show shadow-sm" role="alert">`,
                `   <div>${message}</div>`,
                '   <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>',
                '</div>'
            ].join('');
            alertPlaceholder.append(wrapper);
            
            // Auto hide after 3 seconds
            setTimeout(() => {
                const alert = bootstrap.Alert.getOrCreateInstance(wrapper.querySelector('.alert'));
                alert.close();
            }, 3000);
        } else {
            alert(message);
        }
    }
};

// Handle generic status updates
document.addEventListener('click', async (e) => {
    if (e.target.matches('.btn-update-status')) {
        const leadId = e.target.dataset.id;
        const status = e.target.dataset.status;
        
        const result = await API.request(`/api/leads/${leadId}/status/`, 'POST', { status });
        if (result.success) {
            API.showAlert(`Status updated to ${status}!`);
            // Optionally refresh the part of the UI or reload
            // location.reload();
        }
    }
});

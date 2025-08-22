// HA Log Debugger AI JavaScript

class HALogDebuggerAI {
    constructor() {
        this.recommendations = [];
        this.logs = [];
        this.stats = {};
        this.currentTab = 'recommendations';
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadData();
        this.updateHealthStatus();
        
        // Auto-refresh every 30 seconds
        setInterval(() => this.loadData(), 30000);
        setInterval(() => this.updateHealthStatus(), 10000);
    }
    
    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });
        
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.loadData();
        });
        
        // Analyze button
        document.getElementById('analyze-btn').addEventListener('click', () => {
            this.triggerAnalysis();
        });
        
        // Show resolved checkbox
        document.getElementById('show-resolved').addEventListener('change', () => {
            this.filterRecommendations();
        });
        
        // Severity filter
        document.getElementById('severity-filter').addEventListener('change', () => {
            this.filterRecommendations();
        });
        
        // Log lines selector
        document.getElementById('log-lines').addEventListener('change', () => {
            this.loadLogs();
        });
        
        // Log level filter
        document.getElementById('log-level-filter').addEventListener('change', () => {
            this.loadLogs();
        });
        
        // Log source selector
        document.getElementById('log-source').addEventListener('change', () => {
            this.loadLogs();
        });
        
        // Logs refresh button
        document.getElementById('logs-refresh-btn').addEventListener('click', () => {
            this.loadLogs();
        });
    }
    
    switchTab(tabName) {
        // Update active tab button
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.toggle('active', button.dataset.tab === tabName);
        });
        
        // Update active tab pane
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === tabName);
        });
        
        this.currentTab = tabName;
        
        // Load data for the active tab
        switch (tabName) {
            case 'logs':
                this.loadLogs();
                break;
            case 'stats':
                this.loadStats();
                break;
            case 'recommendations':
                this.loadRecommendations();
                break;
        }
    }
    
    async loadData() {
        const tasks = [];
        
        switch (this.currentTab) {
            case 'recommendations':
                tasks.push(this.loadRecommendations());
                break;
            case 'logs':
                tasks.push(this.loadLogs());
                break;
            case 'stats':
                tasks.push(this.loadStats());
                break;
        }
        
        await Promise.all(tasks);
        this.updateLastUpdated();
    }
    
    async loadRecommendations() {
        try {
            const showResolved = document.getElementById('show-resolved').checked;
            const url = showResolved ? '/api/recommendations' : '/api/recommendations?resolved=false';
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.recommendations = await response.json();
            this.renderRecommendations();
        } catch (error) {
            console.error('Error loading recommendations:', error);
            this.showToast('Failed to load recommendations', 'error');
        }
    }
    
    async loadLogs() {
        try {
            const lines = document.getElementById('log-lines').value;
            const level = document.getElementById('log-level-filter').value;
            const source = document.getElementById('log-source').value;
            
            // Build query parameters
            const params = new URLSearchParams();
            params.append('lines', lines);
            if (level) params.append('level', level);
            params.append('source', source);
            
            const response = await fetch(`/api/logs/recent?${params.toString()}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.logs = await response.json();
            this.renderLogs();
        } catch (error) {
            console.error('Error loading logs:', error);
            this.showToast('Failed to load logs', 'error');
        }
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.stats = await response.json();
            this.renderStats();
        } catch (error) {
            console.error('Error loading stats:', error);
            this.showToast('Failed to load statistics', 'error');
        }
    }
    
    async updateHealthStatus() {
        try {
            const response = await fetch('/api/health');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const health = await response.json();
            
            const healthValue = document.getElementById('health-value');
            healthValue.textContent = health.status;
            healthValue.className = `status-value ${health.status}`;
            
            const recommendationsCount = document.getElementById('recommendations-count');
            recommendationsCount.textContent = health.recommendations_count;
        } catch (error) {
            console.error('Error checking health:', error);
            const healthValue = document.getElementById('health-value');
            healthValue.textContent = 'error';
            healthValue.className = 'status-value unhealthy';
        }
    }
    
    renderRecommendations() {
        const container = document.getElementById('recommendations-list');
        
        if (this.recommendations.length === 0) {
            container.innerHTML = '<div class="loading">No recommendations found</div>';
            return;
        }
        
        const filteredRecommendations = this.getFilteredRecommendations();
        
        container.innerHTML = filteredRecommendations.map(rec => this.createRecommendationCard(rec)).join('');
        
        // Add event listeners for recommendation actions
        container.querySelectorAll('.resolve-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const recId = e.target.dataset.recId;
                this.resolveRecommendation(recId);
            });
        });
        
        // Add event listeners for card collapse/expand
        container.querySelectorAll('.recommendation-header').forEach(header => {
            header.addEventListener('click', (e) => {
                const card = e.target.closest('.recommendation-card');
                card.classList.toggle('collapsed');
            });
        });
    }
    
    getFilteredRecommendations() {
        let filtered = [...this.recommendations];
        
        const severityFilter = document.getElementById('severity-filter').value;
        if (severityFilter) {
            filtered = filtered.filter(rec => rec.severity === severityFilter);
        }
        
        return filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }
    
    createRecommendationCard(recommendation) {
        const createdAt = new Date(recommendation.created_at).toLocaleString();
        const resolvedClass = recommendation.resolved ? 'resolved' : '';
        
        // Check if recommendation content is markdown (starts with # or contains markdown patterns)
        const isMarkdown = this.isMarkdownContent(recommendation.recommendation);
        let renderedContent;
        
        if (isMarkdown) {
            // Render markdown content using simple renderer
            renderedContent = this.renderMarkdown(recommendation.recommendation);
        } else {
            // Handle legacy plain text content
            renderedContent = `<p>${recommendation.recommendation.replace(/\n/g, '<br>')}</p>`;
        }
        
        return `
            <div class="recommendation-card collapsed ${resolvedClass}">
                <div class="recommendation-header">
                    <div>
                        <strong>${recommendation.issue_summary}</strong>
                        <span class="severity ${recommendation.severity.toLowerCase()}">${recommendation.severity}</span>
                    </div>
                    <small>${createdAt}</small>
                </div>
                <div class="recommendation-content">
                    <div class="recommendation-text markdown-content">${renderedContent}</div>
                    <div class="recommendation-actions">
                        ${!recommendation.resolved ? 
                            `<button class="btn btn-primary resolve-btn" data-rec-id="${recommendation.id}">Mark Resolved</button>` : 
                            '<span class="resolved-badge">✓ Resolved</span>'
                        }
                    </div>
                </div>
            </div>
        `;
    }
    
    isMarkdownContent(content) {
        // Check if content looks like markdown
        const markdownPatterns = [
            /^#\s+/m,           // Headers
            /^\*\*.*?\*\*/m,    // Bold text
            /^-\s+\[.*?\]/m,    // Checkboxes
            /^\*\s+/m,          // Bullet lists
            /^\d+\.\s+/m,       // Numbered lists
            /\[.*?\]\(.*?\)/    // Links
        ];
        
        return markdownPatterns.some(pattern => pattern.test(content));
    }
    
    renderMarkdown(content) {
        // Simple markdown renderer for basic formatting
        let html = content;
        
        // Headers
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        
        // Bold text
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Links
        html = html.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
        
        // Code blocks
        html = html.replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>');
        
        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Checkboxes
        html = html.replace(/^-\s+\[\s*\]\s+(.+)$/gm, '<li><input type="checkbox" disabled> $1</li>');
        html = html.replace(/^-\s+\[x\]\s+(.+)$/gm, '<li><input type="checkbox" checked disabled> $1</li>');
        
        // Regular bullet points (not checkboxes)
        html = html.replace(/^-\s+([^<].+)$/gm, '<li>$1</li>');
        
        // Wrap consecutive list items in ul tags
        html = html.replace(/(<li>.*<\/li>)/gs, (match) => {
            const items = match.split('\n').filter(line => line.trim());
            if (items.length > 0) {
                return '<ul>' + items.join('') + '</ul>';
            }
            return match;
        });
        
        // Paragraphs (split by double newlines)
        const paragraphs = html.split(/\n\s*\n/);
        html = paragraphs.map(p => {
            p = p.trim();
            if (p && !p.startsWith('<')) {
                return `<p>${p}</p>`;
            }
            return p;
        }).join('\n');
        
        // Single line breaks
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }
    
    renderLogs() {
        const container = document.getElementById('logs-list');
        
        if (this.logs.length === 0) {
            container.innerHTML = '<div class="loading">No logs found</div>';
            return;
        }
        
        container.innerHTML = this.logs.map(log => this.createLogEntry(log)).join('');
    }
    
    createLogEntry(log) {
        const timestamp = new Date(log.timestamp).toLocaleString();
        const component = log.component ? `[${log.component}]` : '';
        
        return `
            <div class="log-entry">
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-level ${log.level.toLowerCase()}">${log.level}</span>
                ${component ? `<span class="log-component">${component}</span>` : ''}
                <span class="log-message">${log.message}</span>
            </div>
        `;
    }
    
    renderStats() {
        const container = document.getElementById('stats-content');
        
        if (!this.stats.database) {
            container.innerHTML = '<div class="loading">No statistics available</div>';
            return;
        }
        
        const db = this.stats.database;
        
        container.innerHTML = `
            <div class="stat-card">
                <span class="stat-value">${db.total_recommendations}</span>
                <span class="stat-label">Total Recommendations</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">${db.unresolved_recommendations}</span>
                <span class="stat-label">Unresolved Issues</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">${db.processed_logs}</span>
                <span class="stat-label">Processed Logs</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">${this.stats.log_monitor_active ? 'Active' : 'Inactive'}</span>
                <span class="stat-label">Log Monitor</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">${this.stats.ai_service_available ? 'Available' : 'Unavailable'}</span>
                <span class="stat-label">AI Service</span>
            </div>
        `;
    }
    
    async triggerAnalysis() {
        const button = document.getElementById('analyze-btn');
        const originalText = button.textContent;
        
        try {
            button.disabled = true;
            button.textContent = 'Analyzing...';
            
            const response = await fetch('/api/analyze', { method: 'POST' });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.showToast(result.message, 'success');
            
            // Refresh recommendations if on that tab
            if (this.currentTab === 'recommendations') {
                await this.loadRecommendations();
            }
        } catch (error) {
            console.error('Error triggering analysis:', error);
            this.showToast('Analysis failed: ' + error.message, 'error');
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    }
    
    async resolveRecommendation(recommendationId) {
        try {
            const response = await fetch(`/api/recommendations/${recommendationId}/resolve`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.showToast('Recommendation marked as resolved', 'success');
            await this.loadRecommendations();
        } catch (error) {
            console.error('Error resolving recommendation:', error);
            this.showToast('Failed to resolve recommendation', 'error');
        }
    }
    
    filterRecommendations() {
        this.renderRecommendations();
    }
    
    updateLastUpdated() {
        const now = new Date().toLocaleTimeString();
        document.getElementById('last-updated').textContent = now;
    }
    
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new HALogDebuggerAI();
});
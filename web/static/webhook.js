/**
 * Webhook消息处理模块
 */
class WebhookManager {
    constructor() {
        this.apiBase = "/api";
        this.webhookMessages = [];
        this.filterText = "";
        
        this.initializeElements();
        this.bindEvents();
        this.loadMessages();
        
        // 设置自动刷新
        // this.autoRefreshInterval = setInterval(() => this.loadMessages(), 10000);
    }
    
    initializeElements() {
        // 按钮和容器
        this.clearWebhookBtn = document.getElementById("clear-webhook-btn");
        this.refreshWebhookBtn = document.getElementById("refresh-webhook-btn");
        this.webhookContainer = document.getElementById("webhook-container");
        this.webhookCount = document.getElementById("webhook-count");
        this.lastWebhookTime = document.getElementById("last-webhook-time");
        this.webhookFilterInput = document.getElementById("webhook-filter-input");
    }
    
    bindEvents() {
        this.clearWebhookBtn.addEventListener("click", () => this.clearMessages());
        this.refreshWebhookBtn.addEventListener("click", () => this.loadMessages());
        this.webhookFilterInput.addEventListener("input", () => {
            this.filterText = this.webhookFilterInput.value.toLowerCase();
            this.renderMessages();
        });
    }
    
    async apiCall(endpoint, options = {}) {
        const url = `${this.apiBase}${endpoint}`;
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`API调用失败: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API调用错误: ${error.message}`);
            return { success: false, message: error.message };
        }
    }
    
    async loadMessages() {
        try {
            const result = await this.apiCall("/webhook/messages");
            if (result.success) {
                this.webhookMessages = result.messages;
                this.renderMessages();
                
                // 更新统计信息
                this.webhookCount.textContent = this.webhookMessages.length;
                if (this.webhookMessages.length > 0) {
                    this.lastWebhookTime.textContent = this.webhookMessages[0].timestamp;
                } else {
                    this.lastWebhookTime.textContent = "-";
                }
            }
        } catch (error) {
            console.error("加载webhook消息失败:", error);
        }
    }
    
    async clearMessages() {
        try {
            const result = await this.apiCall("/webhook/clear", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            
            if (result.success) {
                this.webhookMessages = [];
                this.renderMessages();
                this.webhookCount.textContent = "0";
                this.lastWebhookTime.textContent = "-";
            }
        } catch (error) {
            console.error("清空webhook消息失败:", error);
        }
    }
    
    renderMessages() {
        // 清空容器
        this.webhookContainer.innerHTML = "";
        
        // 如果没有消息，显示空状态
        if (this.webhookMessages.length === 0) {
            const emptyState = document.createElement("div");
            emptyState.className = "webhook-empty-state";
            emptyState.innerHTML = `
                <div class="empty-icon">📭</div>
                <p>暂无Webhook消息</p>
                <p class="webhook-endpoint">Webhook接收地址: <code id="webhook-url-empty"></code></p>
            `;
            this.webhookContainer.appendChild(emptyState);
            
            // 设置webhook URL
            const protocol = window.location.protocol;
            const host = window.location.host;
            const webhookUrl = `${protocol}//${host}/api/webhook`;
            document.getElementById("webhook-url-empty").textContent = webhookUrl;
            
            return;
        }
        
        // 过滤消息
        const filteredMessages = this.filterText
            ? this.webhookMessages.filter(msg => 
                JSON.stringify(msg).toLowerCase().includes(this.filterText))
            : this.webhookMessages;
        
        // 渲染消息
        filteredMessages.forEach(msg => {
            const messageEl = document.createElement("div");
            messageEl.className = "webhook-message";
            
            // 创建消息头部
            const header = document.createElement("div");
            header.className = "webhook-message-header";
            
            // 时间戳和IP
            const info = document.createElement("div");
            info.className = "webhook-message-info";
            info.innerHTML = `
                <span class="webhook-time">${msg.timestamp}</span>
                <span class="webhook-ip">${msg.remote_addr}</span>
            `;
            
            // 展开/折叠按钮
            const toggleBtn = document.createElement("button");
            toggleBtn.className = "webhook-toggle-btn";
            toggleBtn.textContent = "展开";
            toggleBtn.addEventListener("click", () => {
                const content = messageEl.querySelector(".webhook-message-content");
                if (content.style.display === "none") {
                    content.style.display = "block";
                    toggleBtn.textContent = "折叠";
                } else {
                    content.style.display = "none";
                    toggleBtn.textContent = "展开";
                }
            });
            
            header.appendChild(info);
            header.appendChild(toggleBtn);
            messageEl.appendChild(header);
            
            // 创建消息内容
            const content = document.createElement("div");
            content.className = "webhook-message-content";
            content.style.display = "none"; // 默认折叠
            
            // 数据部分
            if (Object.keys(msg.data).length > 0) {
                const dataSection = document.createElement("div");
                dataSection.className = "webhook-section";
                dataSection.innerHTML = `
                    <h4>数据内容</h4>
                    <pre>${this.syntaxHighlight(msg.data)}</pre>
                `;
                content.appendChild(dataSection);
            }
            
            // 头部信息
            const headersSection = document.createElement("div");
            headersSection.className = "webhook-section";
            headersSection.innerHTML = `
                <h4>请求头</h4>
                <pre>${this.syntaxHighlight(msg.headers)}</pre>
            `;
            content.appendChild(headersSection);
            
            messageEl.appendChild(content);
            this.webhookContainer.appendChild(messageEl);
        });
        
        // 如果过滤后没有消息
        if (filteredMessages.length === 0 && this.filterText) {
            const noResults = document.createElement("div");
            noResults.className = "webhook-empty-state";
            noResults.innerHTML = `
                <div class="empty-icon">🔍</div>
                <p>没有匹配的消息</p>
            `;
            this.webhookContainer.appendChild(noResults);
        }
    }
    
    // JSON语法高亮
    syntaxHighlight(json) {
        if (typeof json !== 'string') {
            json = JSON.stringify(json, null, 2);
        }
        json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return json.replace(/(""|"(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, function (match) {
            let cls = 'json-number';
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'json-key';
                } else {
                    cls = 'json-string';
                }
            } else if (/true|false/.test(match)) {
                cls = 'json-boolean';
            } else if (/null/.test(match)) {
                cls = 'json-null';
            }
            return '<span class="' + cls + '">' + match + '</span>';
        });
    }
}

// 初始化Webhook管理器
document.addEventListener('DOMContentLoaded', function() {
    window.webhookManager = new WebhookManager();
});
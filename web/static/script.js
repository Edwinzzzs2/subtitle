class SubtitleWatcher {
    constructor() {
        this.apiBase = '/api';
        this.isConnected = false;
        this.isStarting = false;
        this.statusInterval = null;
        this.logInterval = null;
        this.autoRefreshInterval = null;
        this.cronJob = null;
        
        this.initializeElements();
        this.bindEvents();
        this.startStatusPolling();
        this.loadConfig();
        this.loadVersion();
    }

    initializeElements() {
        // 按钮元素
        this.startBtn = document.getElementById('start-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.restartBtn = document.getElementById('restart-btn');
        this.processNowBtn = document.getElementById('process-now-btn');
        this.refreshBtn = document.getElementById('refresh-btn');
        this.clearProcessedBtn = document.getElementById('clear-processed-btn');
        this.saveConfigBtn = document.getElementById('save-config-btn');
        this.loadConfigBtn = document.getElementById('load-config-btn');
        this.clearLogsBtn = document.getElementById('clear-logs-btn');
        this.refreshLogsBtn = document.getElementById('refresh-logs-btn');
        this.createTestBtn = document.getElementById('create-test-btn');
        this.testDanmuBtn = document.getElementById('test-danmu-btn');

        // 状态元素
        this.statusText = document.getElementById('status-text');
        this.statusDot = document.getElementById('status-dot');
        this.processedCountLog = document.getElementById('processed-count-log');
        this.lastUpdateLog = document.getElementById('last-update-log');

        // 配置元素
        this.watchDirsContainer = document.getElementById('watch-dirs-container');
        this.fileExtensions = document.getElementById('file-extensions');
        this.waitTime = document.getElementById('wait-time');
        this.maxRetries = document.getElementById('max-retries');
        this.retryDelay = document.getElementById('retry-delay');
        this.logLevel = document.getElementById('log-level');
        this.maxLogLines = document.getElementById('max-log-lines');
        this.keepLogLines = document.getElementById('keep-log-lines');
        this.enableLogging = document.getElementById('enable-logging');

        // 日志刷新指示器
        this.logRefreshStatus = document.getElementById('log-refresh-status');
        
        // 版本元素
        this.versionTag = document.querySelector('.version-tag');
        this.logRefreshDot = document.getElementById('log-refresh-dot');

        // Cron定时任务元素
        this.cronEnabled = document.getElementById('cron-enabled');
        this.cronSchedule = document.getElementById('cron-schedule');
        this.cronStatus = document.getElementById('cron-status');
        
        // 弹幕API配置元素
        this.danmuApiUrl = document.getElementById('danmu-api-url');
        this.danmuApiToken = document.getElementById('danmu-api-token');

        // 其他元素
        this.logContainer = document.getElementById('log-container');
        this.testResult = document.getElementById('test-result');
        this.logFilterInput = document.getElementById('log-filter-input');
    }

    bindEvents() {
        this.startBtn.addEventListener('click', () => this.startWatching());
        this.stopBtn.addEventListener('click', () => this.stopWatching());
        this.restartBtn.addEventListener('click', () => this.restartWatching());
        this.processNowBtn.addEventListener('click', () => this.processNow());
        this.refreshBtn.addEventListener('click', () => this.refreshStatus());
        this.clearProcessedBtn.addEventListener('click', () => this.clearProcessedFiles());
        this.saveConfigBtn.addEventListener('click', () => this.saveConfig());
        this.loadConfigBtn.addEventListener('click', () => this.loadConfig());
        this.clearLogsBtn.addEventListener('click', () => this.clearLogs());
        this.refreshLogsBtn.addEventListener('click', () => this.refreshLogs());
        this.createTestBtn.addEventListener('click', () => this.createTestFile());
        this.testDanmuBtn.addEventListener('click', () => this.testDanmu());
        
        // Cron定时任务事件
        this.cronEnabled.addEventListener('change', () => this.toggleCron());
        this.cronSchedule.addEventListener('input', () => this.updateCronSchedule());

        // 日志过滤
        this.logFilterInput.addEventListener('input', () => this.refreshLogs());
    }

    async apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API调用失败:', error);
            this.showNotification(`API调用失败: ${error.message}`, 'error');
            throw error;
        }
    }

    async startWatching() {
        if (this.isStarting) return;
        this.isStarting = true;
        try {
            this.setButtonLoading(this.startBtn, true);
            const result = await this.apiCall('/start', { method: 'POST' });
            this.showNotification(result.message, result.success ? 'success' : 'error');
            this.refreshStatus();
        } catch (error) {
            this.showNotification('启动失败', 'error');
        } finally {
            this.setButtonLoading(this.startBtn, false);
            this.isStarting = false;
        }
    }

    async stopWatching() {
        try {
            this.setButtonLoading(this.stopBtn, true);
            const result = await this.apiCall('/stop', { method: 'POST' });
            this.showNotification(result.message, result.success ? 'success' : 'error');
            this.refreshStatus();
        } catch (error) {
            this.showNotification('停止失败', 'error');
        } finally {
            this.setButtonLoading(this.stopBtn, false);
        }
    }

    async restartWatching() {
        try {
            this.setButtonLoading(this.restartBtn, true);
            const result = await this.apiCall('/restart', { method: 'POST' });
            this.showNotification(result.message, result.success ? 'success' : 'error');
            this.refreshStatus();
        } catch (error) {
            this.showNotification('重启失败', 'error');
        } finally {
            this.setButtonLoading(this.restartBtn, false);
        }
    }

    async clearProcessedFiles() {
        try {
            this.setButtonLoading(this.clearProcessedBtn, true);
            const result = await this.apiCall('/clear-processed', { method: 'POST' });
            this.showNotification(result.message, result.success ? 'success' : 'error');
            this.refreshStatus();
        } catch (error) {
            this.showNotification('清空失败', 'error');
        } finally {
            this.setButtonLoading(this.clearProcessedBtn, false);
        }
    }

    async processNow() {
        let processingInterval = null;
        try {
            this.setButtonLoading(this.processNowBtn, true);
            this.updateRefreshIndicator('refreshing');
            
            // 在处理期间更频繁地刷新日志（每500ms一次）
            processingInterval = setInterval(() => {
                this.refreshLogs();
            }, 500);
            
            // 直接调用API，不传递目录参数，后端会自动处理所有监控目录
            const result = await this.apiCall('/process-now', {
                method: 'POST'
            });
            
            // 停止频繁刷新
            if (processingInterval) {
                clearInterval(processingInterval);
                processingInterval = null;
            }
            
            this.showNotification(result.message, result.success ? 'success' : 'error');
            this.updateRefreshIndicator(result.success ? 'success' : 'error');
            this.refreshStatus();
            this.refreshLogs();
        } catch (error) {
            // 停止频繁刷新
            if (processingInterval) {
                clearInterval(processingInterval);
                processingInterval = null;
            }
            this.showNotification('处理失败', 'error');
            this.updateRefreshIndicator('error');
        } finally {
            this.setButtonLoading(this.processNowBtn, false);
        }
    }

    async refreshStatus() {
        try {
            const status = await this.apiCall('/status');
            this.updateStatus(status);
            this.isConnected = true;
            this.updateConnectionStatus(true);
        } catch (error) {
            this.isConnected = false;
            this.updateConnectionStatus(false);
        }
    }

    async loadConfig() {
        try {
            this.setButtonLoading(this.loadConfigBtn, true);
            
            // 保存当前定时任务状态
            const wasCronRunning = this.cronEnabled && this.cronEnabled.checked && this.cronJob;
            
            // 先重新加载配置文件
            const reloadResult = await this.apiCall('/reload-config', {
                method: 'POST'
            });
            
            if (!reloadResult.success) {
                this.showNotification('配置重新加载失败', 'error');
                return;
            }
            
            // 然后获取配置数据
            const result = await this.apiCall('/config');
            if (result.success && result.config) {
                const config = result.config;
                // 处理监听目录（支持新旧格式）
                let watchDirs = config.watch_dirs || [];
                setWatchDirs(watchDirs);
                this.fileExtensions.value = (config.file_extensions || []).join(', ');
                this.waitTime.value = config.wait_time || '';
                this.maxRetries.value = config.max_retries || '';
                this.retryDelay.value = config.retry_delay || '';
                this.logLevel.value = config.log_level || 'INFO';
                this.maxLogLines.value = config.max_log_lines || 3000;
                this.keepLogLines.value = config.keep_log_lines || 1000;
                this.enableLogging.checked = config.enable_logging !== false;
                
                // 加载Cron定时任务配置
                this.cronEnabled.checked = config.cron_enabled || false;
                this.cronSchedule.value = config.cron_schedule || '0 5 * * *';
                
                // 加载弹幕API配置
                this.danmuApiUrl.value = (config.danmu_api && config.danmu_api.base_url) || '';
                this.danmuApiToken.value = (config.danmu_api && config.danmu_api.token) || '';
                
                // 如果之前定时任务在运行或者配置中启用了定时任务，则重新启动
                if ((wasCronRunning || this.cronEnabled.checked) && this.cronSchedule.value.trim()) {
                    this.cronEnabled.checked = true;
                    this.startCron();
                }
                
                this.showNotification('配置重新加载成功', 'success');
            } else {
                this.showNotification('配置加载失败', 'error');
            }
        } catch (error) {
            console.error('加载配置失败:', error);
            this.showNotification('配置加载失败', 'error');
        } finally {
            this.setButtonLoading(this.loadConfigBtn, false);
        }
    }

    async loadVersion() {
        try {
            const response = await this.apiCall('/version');
            if (response.version && this.versionTag) {
                this.versionTag.textContent = `v${response.version}`;
                this.versionTag.title = `版本: ${response.version}\n构建日期: ${response.build_date}\n${response.description}`;
            }
        } catch (error) {
            console.error('加载版本信息时出错:', error);
            // 版本信息加载失败不显示错误通知，保持静默
        }
    }

    async saveConfig() {
        try {
            this.setButtonLoading(this.saveConfigBtn, true);
            
            // 解析文件扩展名
            const extensions = this.fileExtensions.value
                .split(',')
                .map(ext => ext.trim())
                .filter(ext => ext.length > 0)
                .map(ext => ext.startsWith('.') ? ext : '.' + ext);
            
            // 获取监听目录
            const watchDirs = getWatchDirs();
            
            const config = {
                watch_dirs: watchDirs,
                file_extensions: extensions.length > 0 ? extensions : ['.xml'],
                wait_time: parseFloat(this.waitTime.value) || 0.5,
                max_retries: parseInt(this.maxRetries.value) || 3,
                retry_delay: parseFloat(this.retryDelay.value) || 1.0,
                log_level: this.logLevel.value,
                max_log_lines: parseInt(this.maxLogLines.value) || 3000,
                keep_log_lines: parseInt(this.keepLogLines.value) || 1000,
                enable_logging: this.enableLogging.checked,
                cron_enabled: this.cronEnabled.checked,
                cron_schedule: this.cronSchedule.value.trim(),
                danmu_api: {
                    base_url: this.danmuApiUrl.value.trim(),
                    token: this.danmuApiToken.value.trim()
                }
            };
            
            // 验证配置
            if (!config.watch_dirs || config.watch_dirs.length === 0) {
                this.showNotification('至少需要配置一个监听目录', 'error');
                return;
            }
            
            const result = await this.apiCall('/config', {
                method: 'POST',
                body: JSON.stringify(config)
            });
            
            this.showNotification(result.message, result.success ? 'success' : 'error');
            
            if (result.success) {
                this.refreshStatus();
            }
        } catch (error) {
            this.showNotification('保存配置失败', 'error');
        } finally {
            this.setButtonLoading(this.saveConfigBtn, false);
        }
    }

    async refreshLogs() {
        try {
            // 更新刷新指示器状态
            this.updateRefreshIndicator('refreshing');
            
            const result = await this.apiCall('/logs');
            this.updateLogs(result.logs);
            
            // 刷新成功
            this.updateRefreshIndicator('success');
        } catch (error) {
            console.error('获取日志失败:', error);
            // 刷新失败
            this.updateRefreshIndicator('error');
        }
    }
    
    updateRefreshIndicator(status) {
        if (!this.logRefreshStatus || !this.logRefreshDot) return;
        
        switch (status) {
            case 'refreshing':
                this.logRefreshStatus.textContent = '刷新中...';
                this.logRefreshDot.className = 'refresh-dot active';
                break;
            case 'success':
                this.logRefreshStatus.textContent = '自动刷新中';
                this.logRefreshDot.className = 'refresh-dot active';
                break;
            case 'error':
                this.logRefreshStatus.textContent = '刷新失败';
                this.logRefreshDot.className = 'refresh-dot paused';
                break;
            case 'paused':
                this.logRefreshStatus.textContent = '已暂停';
                this.logRefreshDot.className = 'refresh-dot paused';
                break;
        }
    }

    async clearLogs() {
        try {
            this.setButtonLoading(this.clearLogsBtn, true);
            const result = await this.apiCall('/clear-logs', { method: 'POST' });
            
            if (result.success) {
                this.logContainer.innerHTML = '<div class="log-entry"><div class="log-header"><span class="log-time">刚刚</span><span class="log-level">[INFO]</span></div><div class="log-message">日志已清空，等待新的日志条目...</div></div>';
                this.showNotification('日志清空成功', 'success');
                // 刷新状态以更新已处理文件计数
                this.refreshStatus();
            } else {
                this.showNotification(result.message || '清空日志失败', 'error');
            }
        } catch (error) {
            this.showNotification(`清空日志失败: ${error.message}`, 'error');
        } finally {
            this.setButtonLoading(this.clearLogsBtn, false);
        }
    }

    async createTestFile() {
        try {
            this.setButtonLoading(this.createTestBtn, true);
            const result = await this.apiCall('/create-test', { method: 'POST' });
            this.testResult.innerHTML = result.message;
            this.testResult.className = 'test-result success';
            this.refreshLogs();
        } catch (error) {
            this.testResult.innerHTML = `创建测试视频失败: ${error.message}`;
            this.testResult.className = 'test-result error';
        } finally {
            this.setButtonLoading(this.createTestBtn, false);
        }
    }

    async testDanmu() {
        try {
            this.setButtonLoading(this.testDanmuBtn, true);
            const result = await this.apiCall('/test-danmu', { method: 'POST' });
            
            if (result.success) {
                let xmlInfo = '';
                if (result.xml_created && result.xml_file) {
                    xmlInfo = `<p><strong>XML文件:</strong> <span class="success">已创建 ${result.xml_file}</span></p>`;
                } else {
                    xmlInfo = `<p><strong>XML文件:</strong> <span class="warning">未创建</span></p>`;
                }
                
                this.testResult.innerHTML = `
                    <div class="danmu-test-result">
                        <h4>弹幕测试结果</h4>
                        <p><strong>搜索结果:</strong> ${result.search_result}</p>
                        <p><strong>分集数量:</strong> ${result.episode_count}</p>
                        <p><strong>弹幕数量:</strong> ${result.danmu_count}</p>
                        ${xmlInfo}
                        <p><strong>测试状态:</strong> <span class="success">成功</span></p>
                    </div>
                `;
                this.testResult.className = 'test-result success';
            } else {
                this.testResult.innerHTML = `弹幕测试失败: ${result.message}`;
                this.testResult.className = 'test-result error';
            }
        } catch (error) {
            this.testResult.innerHTML = `弹幕测试失败: ${error.message}`;
            this.testResult.className = 'test-result error';
        } finally {
            this.setButtonLoading(this.testDanmuBtn, false);
        }
    }

    updateStatus(status) {
        // 基本状态
        const isRunning = status.running || status.watching; // 兼容新旧字段名
        this.lastUpdateLog.textContent = new Date().toLocaleTimeString();
        this.processedCountLog.textContent = status.processed_count || 0;

        // 更新头部状态指示器
        if (this.statusText && this.statusDot) {
            this.statusText.textContent = isRunning ? '监听中' : '已停止';
            this.statusDot.className = isRunning ? 'status-dot online' : 'status-dot offline';
        }

        // 更新日志区域的统计信息
        const logStatus = document.getElementById('log-status');
        if (logStatus) {
            logStatus.textContent = isRunning ? '监听中' : '已停止';
            logStatus.className = isRunning ? 'log-status running' : 'log-status stopped';
        }

        // 更新按钮状态
        this.startBtn.disabled = isRunning;
        this.stopBtn.disabled = !isRunning;
        this.restartBtn.disabled = false;
        this.clearProcessedBtn.disabled = false;
    }

    updateConnectionStatus(connected) {
        if (connected) {
            this.statusText.textContent = '已连接';
            this.statusDot.className = 'status-dot online';
        } else {
            this.statusText.textContent = '连接失败';
            this.statusDot.className = 'status-dot offline';
        }
    }

    updateLogs(logs) {
        if (!logs) {
            this.logContainer.innerHTML = '<div class="log-entry"><span class="log-time">暂无日志</span><span class="log-message">等待处理日志...</span></div>';
            return;
        }

        const filterValue = this.logFilterInput.value.toLowerCase();
        const filteredLogs = logs.filter(log => {
            const message = log.message || '';
            const timestamp = log.timestamp || '';
            return message.toLowerCase().includes(filterValue) || timestamp.toLowerCase().includes(filterValue);
        });

        if (filteredLogs.length === 0) {
            this.logContainer.innerHTML = '<div class="log-entry"><span class="log-time">没有匹配的日志</span><span class="log-message">请调整过滤器...</span></div>';
            return;
        }


        // 记录当前日志数量，用于检测新日志
        const currentLogCount = this.logContainer.children.length;
        const newLogCount = logs.length;
        
        // 检查是否有新日志
        const hasNewLogs = newLogCount > currentLogCount;
        
        // 记录滚动位置，判断用户是否在底部
        const isAtBottom = this.logContainer.scrollTop >= this.logContainer.scrollHeight - this.logContainer.clientHeight - 10;
        
        this.logContainer.innerHTML = filteredLogs.map((log, index) => {
            const level = log.level || 'INFO';
            const levelClass = level.toLowerCase();
            // 格式化时间戳为月-日 时:分:秒格式
            let formattedTime = '';
            if (log.timestamp) {
                try {
                    const date = new Date(log.timestamp);
                    if (!isNaN(date.getTime())) {
                        const month = String(date.getMonth() + 1).padStart(2, '0');
                        const day = String(date.getDate()).padStart(2, '0');
                        const hours = String(date.getHours()).padStart(2, '0');
                        const minutes = String(date.getMinutes()).padStart(2, '0');
                        const seconds = String(date.getSeconds()).padStart(2, '0');
                        formattedTime = `${month}-${day} ${hours}:${minutes}:${seconds}`;
                    } else {
                        formattedTime = log.timestamp;
                    }
                } catch (e) {
                    formattedTime = log.timestamp;
                }
            }
            
            // 为新日志添加高亮效果
            const isNewLog = hasNewLogs && index >= currentLogCount;
            const newLogClass = isNewLog ? ' new-log' : '';
            
            return `
                <div class="log-entry log-${levelClass}${newLogClass}">
                    <div class="log-header">
                        <span class="log-time">${formattedTime}</span>
                        <span class="log-level">[${level}]</span>
                    </div>
                    <div class="log-message">${log.message}</div>
                </div>
            `;
        }).join('');
        
        // 如果用户在底部或有新日志，自动滚动到底部
        if (isAtBottom || hasNewLogs) {
            setTimeout(() => {
                this.logContainer.scrollTop = this.logContainer.scrollHeight;
            }, 100);
        }
        
        // 移除新日志高亮效果
        if (hasNewLogs) {
            setTimeout(() => {
                const newLogElements = this.logContainer.querySelectorAll('.new-log');
                newLogElements.forEach(element => {
                    element.classList.remove('new-log');
                });
            }, 2000);
        }
    }

    setButtonLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            button.classList.add('loading');
            button.dataset.originalText = button.textContent;
            button.textContent = '处理中...';
        } else {
            button.disabled = false;
            button.classList.remove('loading');
            button.textContent = button.dataset.originalText || button.textContent;
        }
    }

    showNotification(message, type = 'info') {
        // 简单的通知实现
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 5px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            transition: all 0.3s ease;
            ${type === 'success' ? 'background: #48bb78;' : ''}
            ${type === 'error' ? 'background: #f56565;' : ''}
            ${type === 'info' ? 'background: #4299e1;' : ''}
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    startStatusPolling() {
        // 每5秒检查一次状态
        this.statusInterval = setInterval(() => {
            this.refreshStatus();
        }, 5000);
        
        // 每2秒刷新一次日志，实现动态更新效果
        this.logInterval = setInterval(() => {
            if (this.isConnected) {
                this.refreshLogs();
            }
        }, 2000);
        
        // 初始加载
        this.refreshStatus();
        this.refreshLogs();
    }

    destroy() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
        if (this.logInterval) {
            clearInterval(this.logInterval);
        }
        this.stopCron();
    }

    // Cron定时任务功能方法
    toggleCron() {
        if (this.cronEnabled.checked) {
            this.startCron();
        } else {
            this.stopCron();
        }
    }

    startCron() {
        this.stopCron(); // 先停止现有的定时器
        
        const cronExpression = this.cronSchedule.value.trim();
        if (!cronExpression) {
            this.updateCronStatus('未设置Cron表达式', false);
            return;
        }

        try {
            this.scheduleCronJob(cronExpression);
            this.updateCronStatus('已启用', true);
        } catch (error) {
            console.error('启动定时任务失败:', error);
            this.updateCronStatus('Cron表达式错误', false);
            this.cronEnabled.checked = false;
        }
    }

    stopCron() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
        if (this.cronJob) {
            this.cronJob = null;
        }
        this.updateCronStatus('未启用', false);
    }

    scheduleCronJob(cronExpression) {
        // 简单的cron解析实现
        const nextExecution = this.calculateNextExecution(cronExpression);
        if (!nextExecution) {
            throw new Error('无效的Cron表达式');
        }

        const now = new Date();
        const delay = nextExecution.getTime() - now.getTime();
        
        if (delay > 0) {
            this.cronJob = setTimeout(() => {
                this.executeCronTask();
                // 重新调度下一次执行
                this.scheduleCronJob(cronExpression);
            }, delay);
        }
    }

    calculateNextExecution(cronExpression) {
        try {
            const parts = cronExpression.trim().split(/\s+/);
            
            // 只支持5字段格式: 分 时 日 月 星期
            if (parts.length !== 5) {
                throw new Error('Cron表达式必须是5个字段: 分 时 日 月 星期');
            }
            
            const [minute, hour, day, month, weekday] = parts;
            const second = '0'; // 默认在0秒执行

            const now = new Date();
            let next = new Date(now.getTime() + 1000); // 从下一秒开始
            
            // 最多尝试找未来4年内的下一次执行时间
            const maxAttempts = 4 * 365 * 24 * 60; // 4年的分钟数
            let attempts = 0;
            
            while (attempts < maxAttempts) {
                if (this.matchesCronField(next.getSeconds(), second) &&
                    this.matchesCronField(next.getMinutes(), minute) &&
                    this.matchesCronField(next.getHours(), hour) &&
                    this.matchesCronField(next.getDate(), day) &&
                    this.matchesCronField(next.getMonth() + 1, month) &&
                    this.matchesCronField(next.getDay(), weekday)) {
                    return next;
                }
                
                // 递增到下一分钟
                next.setTime(next.getTime() + 60000);
                next.setSeconds(0, 0);
                attempts++;
            }
            
            return null;
        } catch (error) {
            console.error('Cron表达式解析错误:', error);
            return null;
        }
    }

    matchesCronField(value, pattern) {
        // 处理通配符
        if (pattern === '*') {
            return true;
        }
        
        // 处理具体数值
        if (/^\d+$/.test(pattern)) {
            return value === parseInt(pattern);
        }
        
        // 处理范围 (例如: 1-5)
        if (pattern.includes('-')) {
            const [start, end] = pattern.split('-').map(Number);
            return value >= start && value <= end;
        }
        
        // 处理列表 (例如: 1,3,5)
        if (pattern.includes(',')) {
            const values = pattern.split(',').map(Number);
            return values.includes(value);
        }
        
        // 处理步长 (例如: */5, 0-30/5)
        if (pattern.includes('/')) {
            const [range, step] = pattern.split('/');
            const stepValue = parseInt(step);
            
            if (range === '*') {
                return value % stepValue === 0;
            } else if (range.includes('-')) {
                const [start, end] = range.split('-').map(Number);
                return value >= start && value <= end && (value - start) % stepValue === 0;
            } else {
                const start = parseInt(range);
                return value >= start && (value - start) % stepValue === 0;
            }
        }
        
        // 处理特殊字符 (例如: L, W, #)
        // 这里可以根据需要扩展更复杂的cron特性
        
        return false;
    }

    async executeCronTask() {
        try {
            console.log('执行定时任务...');
            await this.processNow();
            this.showNotification('定时任务执行完成', 'success');
        } catch (error) {
            console.error('定时任务执行失败:', error);
            this.showNotification('定时任务执行失败', 'error');
        }
    }

    updateCronStatus(text, enabled) {
        if (this.cronStatus) {
            this.cronStatus.textContent = text;
            this.cronStatus.className = enabled ? 'status-text enabled' : 'status-text disabled';
        }
    }

    updateCronSchedule() {
        if (this.cronEnabled.checked) {
            this.startCron();
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.subtitleWatcher = new SubtitleWatcher();
});

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    if (window.subtitleWatcher) {
        window.subtitleWatcher.destroy();
    }
});

// 多监听目录管理函数
function addWatchDir() {
    const container = document.getElementById('watch-dirs-container');
    const newItem = document.createElement('div');
    newItem.className = 'watch-dir-item';
    newItem.innerHTML = `
        <input type="text" class="watch-dir-input" placeholder="输入监听目录路径">
        <button type="button" class="remove-dir-btn" onclick="removeWatchDir(this)">删除</button>
    `;
    container.appendChild(newItem);
}

function removeWatchDir(button) {
    const container = document.getElementById('watch-dirs-container');
    const items = container.querySelectorAll('.watch-dir-item');
    
    // 至少保留一个目录输入框
    if (items.length > 1) {
        button.parentElement.remove();
    } else {
        // 如果只剩一个，清空内容而不删除
        const input = button.parentElement.querySelector('.watch-dir-input');
        input.value = '';
    }
}

function getWatchDirs() {
    const inputs = document.querySelectorAll('.watch-dir-input');
    const dirs = [];
    inputs.forEach(input => {
        const value = input.value.trim();
        if (value) {
            dirs.push(value);
        }
    });
    return dirs;
}

function setWatchDirs(dirs) {
    const container = document.getElementById('watch-dirs-container');
    container.innerHTML = '';
    
    if (!dirs || dirs.length === 0) {
        dirs = [''];
    }
    
    dirs.forEach((dir, index) => {
        const item = document.createElement('div');
        item.className = 'watch-dir-item';
        item.innerHTML = `
            <input type="text" class="watch-dir-input" value="${dir}" placeholder="输入监听目录路径">
            <button type="button" class="remove-dir-btn" onclick="removeWatchDir(this)">删除</button>
        `;
        container.appendChild(item);
    });
}
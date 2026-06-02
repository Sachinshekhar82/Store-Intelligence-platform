// ==========================================================================
// API Connection and Endpoint Configuration
// ==========================================================================
const BASE_URL = window.location.origin.includes('8000') || window.location.origin.includes('3000') 
    ? window.location.origin 
    : 'http://localhost:8000';

let currentStoreId = 'ST1008';
let currentTab = 'overview';
let currentCameraId = 'CAM1';
let queueChartInstance = null;
let refreshInterval = null;

// ==========================================================================
// DOM Elements Initialization
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    setupEventListeners();
    fetchData();
    
    // Auto-polling refresh every 10 seconds
    refreshInterval = setInterval(fetchData, 10000);
});

function initApp() {
    // Select initial drop downs
    document.getElementById('store-selector').value = currentStoreId;
    document.getElementById('cam-selector').value = currentCameraId;
    
    // Check API connection health
    checkApiHealth();
}

// ==========================================================================
// Navigation & Control Events Setup
// ==========================================================================
function setupEventListeners() {
    // Tab Navigation switching
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = item.getAttribute('data-tab');
            switchTab(tabName);
            
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
        });
    });

    // Quick alerts link navigation
    document.getElementById('goto-alerts-btn').addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('alerts-tab');
        document.querySelectorAll('.nav-item').forEach(i => {
            i.classList.remove('active');
            if (i.getAttribute('data-tab') === 'alerts-tab') i.classList.add('active');
        });
    });

    // Store selector dropdown
    document.getElementById('store-selector').addEventListener('change', (e) => {
        currentStoreId = e.target.value;
        showToast(`Switched to Store: ${currentStoreId}`);
        fetchData();
    });

    // Camera selector for spatial heatmap
    document.getElementById('cam-selector').addEventListener('change', (e) => {
        currentCameraId = e.target.value;
        fetchHeatmapData();
    });

    // Manual refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        showToast('Refreshing dashboard data...');
        fetchData();
    });

    // Mock Live Ingestion simulation button
    document.getElementById('simulate-btn').addEventListener('click', () => {
        triggerMockEventIngest();
    });

    // Toggle heatmap overlay visibility
    document.getElementById('toggle-heatmap').addEventListener('change', (e) => {
        const canvas = document.getElementById('heatmap-canvas');
        if (e.target.checked) {
            canvas.style.opacity = '1';
        } else {
            canvas.style.opacity = '0';
        }
    });

    // Dynamic resize handler for canvas overlay
    window.addEventListener('resize', () => {
        if (currentTab === 'heatmap-tab') {
            resizeHeatmapCanvas();
            drawHeatmap();
        }
    });

    // Ensure canvas is resized when image loads
    const layoutImg = document.getElementById('layout-image');
    layoutImg.onload = () => {
        if (currentTab === 'heatmap-tab') {
            resizeHeatmapCanvas();
            drawHeatmap();
        }
    };
}

function switchTab(tabId) {
    currentTab = tabId;
    
    // Hide all tabs
    document.getElementById('overview-tab').classList.remove('active-tab');
    document.getElementById('heatmap-tab-content').classList.remove('active-tab');
    document.getElementById('funnel-tab-content').classList.remove('active-tab');
    document.getElementById('alerts-tab-content').classList.remove('active-tab');

    // Show selected tab content
    if (tabId === 'overview') {
        document.getElementById('overview-tab').classList.add('active-tab');
        document.getElementById('page-header-title').innerText = "Live Store Analytics";
        document.getElementById('page-header-subtitle').innerText = "Real-time shopper tracking & conversion telemetry";
    } else if (tabId === 'heatmap-tab') {
        document.getElementById('heatmap-tab-content').classList.add('active-tab');
        document.getElementById('page-header-title').innerText = "Spatial Heatmap";
        document.getElementById('page-header-subtitle').innerText = "Shopper coordinate coordinates mapped dynamically over layout";
        // Force refresh canvas layout resize
        setTimeout(() => {
            resizeHeatmapCanvas();
            fetchHeatmapData();
        }, 100);
    } else if (tabId === 'funnel-tab') {
        document.getElementById('funnel-tab-content').classList.add('active-tab');
        document.getElementById('page-header-title').innerText = "Shopper Funnel Analytics";
        document.getElementById('page-header-subtitle').innerText = "Detailed drop-off ratios from entry to checkout completion";
    } else if (tabId === 'alerts-tab') {
        document.getElementById('alerts-tab-content').classList.add('active-tab');
        document.getElementById('page-header-title').innerText = "Operational Anomalies";
        document.getElementById('page-header-subtitle').innerText = "System flagged behavioral alerts & response log";
    }
}

// ==========================================================================
// API Telemetry Collection Layer
// ==========================================================================
async function fetchData() {
    checkApiHealth();
    fetchMetrics();
    fetchFunnelData();
    fetchAnomalies();
    if (currentTab === 'heatmap-tab') {
        fetchHeatmapData();
    }
}

async function checkApiHealth() {
    try {
        const response = await fetch(`${BASE_URL}/health`);
        const data = await response.json();
        
        const dot = document.querySelector('.pulse-dot');
        const textSpan = document.getElementById('conn-text');
        
        if (data.status === 'healthy') {
            dot.className = 'pulse-dot online';
            textSpan.innerText = 'Edge API: Connected';
        } else {
            dot.className = 'pulse-dot';
            textSpan.innerText = 'Edge API: Failed status';
        }
    } catch (e) {
        const dot = document.querySelector('.pulse-dot');
        const textSpan = document.getElementById('conn-text');
        dot.className = 'pulse-dot';
        textSpan.innerText = 'Edge API: Connection offline';
    }
}

async function fetchMetrics() {
    try {
        const response = await fetch(`${BASE_URL}/stores/${currentStoreId}/metrics`);
        if (!response.ok) return;
        const data = await response.json();
        
        // Render metric grid values
        document.getElementById('val-visitors').innerText = data.metrics.total_unique_visitors.toLocaleString();
        document.getElementById('val-buyers').innerText = data.metrics.unique_buyers.toLocaleString();
        document.getElementById('val-conversion').innerText = `${data.metrics.conversion_rate_percentage.toFixed(1)}%`;
        document.getElementById('val-dwell').innerText = `${Math.round(data.metrics.average_dwell_time_minutes)}m`;
        document.getElementById('val-queue-depth').innerText = data.metrics.current_queue_depth;
        document.getElementById('val-abandonment-rate').innerText = `${data.metrics.queue_abandonment_rate_percentage.toFixed(1)}%`;
        
        // Render/update real-time queue depth charts
        updateQueueChart(data.metrics.current_queue_depth);
    } catch (e) {
        console.error("Error fetching metrics", e);
    }
}

async function fetchFunnelData() {
    try {
        const response = await fetch(`${BASE_URL}/stores/${currentStoreId}/funnel`);
        if (!response.ok) return;
        const data = await response.json();
        
        // Render small funnel on overview
        renderOverviewFunnel(data.stages);
        
        // Render detailed funnel on tab 3
        renderDetailedFunnel(data.stages);
    } catch (e) {
        console.error("Error fetching funnel", e);
    }
}

async function fetchAnomalies() {
    try {
        const response = await fetch(`${BASE_URL}/stores/${currentStoreId}/anomalies`);
        if (!response.ok) return;
        const data = await response.json();
        
        // Update navigation counter badge
        const badge = document.getElementById('anomaly-badge');
        badge.innerText = data.anomalies.length;
        badge.style.display = data.anomalies.length > 0 ? 'inline-block' : 'none';

        // Render quick alerts list
        renderQuickAlerts(data.anomalies);
        
        // Render full detail alerts list on tab 4
        renderDetailedAlerts(data.anomalies);
    } catch (e) {
        console.error("Error fetching anomalies", e);
    }
}

let heatmapCoords = [];
async function fetchHeatmapData() {
    try {
        const response = await fetch(`${BASE_URL}/stores/${currentStoreId}/heatmap?camera_id=${currentCameraId}`);
        if (!response.ok) return;
        const data = await response.json();
        heatmapCoords = data.coordinates;
        
        // Render coordinate blobs to canvas
        drawHeatmap();
    } catch (e) {
        console.error("Error fetching heatmap", e);
    }
}

// ==========================================================================
// Chart.js & Visualization Renderers
// ==========================================================================
function updateQueueChart(latestQueueDepth) {
    const ctx = document.getElementById('queueChart').getContext('2d');
    
    // Mocking historical trend logic for visuals
    const defaultLabels = ['10m ago', '8m ago', '6m ago', '4m ago', '2m ago', 'Now'];
    const defaultData = [2, 4, 3, 5, 2, latestQueueDepth];

    if (queueChartInstance) {
        queueChartInstance.data.datasets[0].data = defaultData;
        queueChartInstance.update();
    } else {
        queueChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: defaultLabels,
                datasets: [{
                    label: 'Queue Depth',
                    data: defaultData,
                    borderColor: '#00f2fe',
                    backgroundColor: 'rgba(0, 242, 254, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#00f2fe'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { 
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#747d8c', font: { family: 'Outfit' } }
                    },
                    y: { 
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#747d8c', font: { family: 'Outfit' }, stepSize: 1 },
                        suggestedMin: 0,
                        suggestedMax: 10
                    }
                }
            }
        });
    }
}

function renderOverviewFunnel(stages) {
    const funnelViz = document.getElementById('funnel-viz');
    funnelViz.innerHTML = '';
    
    stages.forEach((stage, idx) => {
        const barOuter = document.createElement('div');
        barOuter.className = 'funnel-bar-wrapper';
        
        const stageNum = stage.stage.split('_')[0];
        const stageLabel = stage.stage.split('_').slice(1).join(' ').replace('Complete', 'Completed');
        
        barOuter.innerHTML = `
            <div class="funnel-bar-header">
                <span>
                    <span class="funnel-dot dot-stage${idx+1}"></span>
                    Step ${stageNum}: ${stageLabel}
                </span>
                <span>${stage.count.toLocaleString()} visitors</span>
            </div>
            <div class="funnel-bar-outer">
                <div class="funnel-bar-inner color-stage${idx+1}" style="width: 0%"></div>
                <span class="funnel-bar-percentage">${stage.conversion_from_previous_percentage.toFixed(1)}%</span>
            </div>
        `;
        funnelViz.appendChild(barOuter);
        
        // Smooth slide animation
        setTimeout(() => {
            const barInner = barOuter.querySelector('.funnel-bar-inner');
            const totalWidth = idx === 0 ? 100 : (stage.count / stages[0].count) * 100;
            barInner.style.width = `${Math.max(totalWidth, 5)}%`;
        }, 100);
    });
}

function renderDetailedFunnel(stages) {
    const detailedVisual = document.getElementById('funnel-detailed-visual');
    detailedVisual.innerHTML = '';
    
    const tableBody = document.getElementById('funnel-table-body');
    tableBody.innerHTML = '';

    stages.forEach((stage, idx) => {
        const stageNum = stage.stage.split('_')[0];
        const stageLabel = stage.stage.split('_').slice(1).join(' ').replace('Complete', 'Completed');
        
        // 1. Render Graphic Bar
        const stepDiv = document.createElement('div');
        stepDiv.className = 'funnel-detail-step';
        stepDiv.innerHTML = `
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px; text-transform:uppercase;">Stage ${stageNum}</div>
            <div style="font-size:16px; font-weight:700; margin-bottom:8px;">${stageLabel}</div>
            <div style="font-size:24px; font-weight:800; color: #fff;">${stage.count.toLocaleString()}</div>
        `;
        // Inject gradient glow border styling depending on stage
        stepDiv.style.borderLeft = `4px solid var(--neon-${getStageColorName(idx)})`;
        detailedVisual.appendChild(stepDiv);

        if (idx < stages.length - 1) {
            const arrow = document.createElement('div');
            arrow.className = 'funnel-connector';
            detailedVisual.appendChild(arrow);
        }

        // 2. Render Table Row
        const prevCount = idx > 0 ? stages[idx-1].count : stage.count;
        const lossCount = prevCount - stage.count;
        const lossPercentage = prevCount > 0 ? (lossCount / prevCount) * 100 : 0.0;
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <span class="funnel-dot dot-stage${idx+1}" style="display:inline-block; margin-right:8px; vertical-align:middle;"></span>
                <strong>Stage ${stageNum}</strong>: ${stageLabel}
            </td>
            <td class="text-right">${stage.count.toLocaleString()}</td>
            <td class="text-right text-green">${stage.conversion_from_previous_percentage.toFixed(1)}%</td>
            <td class="text-right text-magenta">
                ${idx > 0 ? `-${lossCount.toLocaleString()} (${lossPercentage.toFixed(1)}% loss)` : 'Baseline (100%)'}
            </td>
        `;
        tableBody.appendChild(row);
    });
}

function getStageColorName(idx) {
    const colors = ['cyan', 'purple', 'magenta', 'green'];
    return colors[idx] || 'cyan';
}

function renderQuickAlerts(anomalies) {
    const list = document.getElementById('anomalies-list-quick');
    list.innerHTML = '';
    
    if (anomalies.length === 0) {
        list.innerHTML = `
            <div style="text-align:center; padding: 20px; color:var(--text-muted); font-size:14px;">
                <i class="fa-solid fa-circle-check text-green" style="font-size:24px; margin-bottom:8px; display:block;"></i>
                No active operational anomalies detected inside the store.
            </div>
        `;
        return;
    }

    // Limit to 3 on quick view panel
    anomalies.slice(0, 3).forEach(anom => {
        const item = document.createElement('div');
        item.className = 'anomaly-item';
        
        const timeAgo = formatTimeAgo(anom.timestamp);
        const severityClass = `severity-${anom.severity.toLowerCase()}`;
        
        item.innerHTML = `
            <div class="anomaly-severity-badge ${severityClass}"></div>
            <div class="anomaly-info">
                <div class="anomaly-metric">${anom.metric}</div>
                <div class="anomaly-values">Observed: <strong style="color:#fff">${anom.observed_value}</strong> (Limit: ${anom.threshold_limit})</div>
                <div class="anomaly-time">${timeAgo}</div>
            </div>
            <div class="anomaly-action">
                <button class="btn btn-secondary" style="padding:6px 12px; font-size:11px; border-radius:8px;" onclick="resolveAnomaly('${anom.anomaly_id}')">Investigate</button>
            </div>
        `;
        list.appendChild(item);
    });
}

function renderDetailedAlerts(anomalies) {
    const list = document.getElementById('alerts-list-detailed');
    list.innerHTML = '';

    if (anomalies.length === 0) {
        list.innerHTML = `
            <div style="text-align:center; padding:60px 20px; color:var(--text-muted); font-size:16px;">
                <i class="fa-solid fa-shield-halved text-green" style="font-size:48px; margin-bottom:16px; display:block;"></i>
                All operations within baseline thresholds. Store running smoothly.
            </div>
        `;
        return;
    }

    anomalies.forEach(anom => {
        const item = document.createElement('div');
        item.className = 'anomaly-item';
        item.style.marginBottom = '12px';
        
        const severityClass = `severity-${anom.severity.toLowerCase()}`;
        const timeAgo = formatTimeAgo(anom.timestamp);
        
        item.innerHTML = `
            <div class="anomaly-severity-badge ${severityClass}" style="width:16px; height:16px;"></div>
            <div class="anomaly-info" style="grid-template-columns: 1.2fr 1.5fr 1fr;">
                <div>
                    <span style="font-size:10px; font-weight:700; color:var(--text-muted); text-transform:uppercase; display:block; margin-bottom:2px;">Metric Type</span>
                    <strong style="font-size:16px; color:#fff">${anom.metric}</strong>
                </div>
                <div>
                    <span style="font-size:10px; font-weight:700; color:var(--text-muted); text-transform:uppercase; display:block; margin-bottom:2px;">Threshold Deviation</span>
                    <span>Observed: <strong style="color:var(--neon-magenta)">${anom.observed_value}</strong> vs limit of <strong>${anom.threshold_limit}</strong></span>
                </div>
                <div>
                    <span style="font-size:10px; font-weight:700; color:var(--text-muted); text-transform:uppercase; display:block; margin-bottom:2px;">Logged Time</span>
                    <span>${timeAgo} (${new Date(anom.timestamp).toLocaleTimeString()})</span>
                </div>
            </div>
            <div class="anomaly-action" style="flex-shrink:0;">
                <button class="btn btn-primary" style="padding:10px 16px; font-size:12px;" onclick="resolveAnomaly('${anom.anomaly_id}')">
                    <i class="fa-solid fa-check"></i> Acknowledge
                </button>
            </div>
        `;
        list.appendChild(item);
    });
}

function resolveAnomaly(anomId) {
    showToast(`Acknowledged alert: ${anomId}. Incident logged in operations register.`);
}

function formatTimeAgo(isoString) {
    const date = new Date(isoString);
    const seconds = Math.floor((new Date() - date) / 1000);
    
    if (seconds < 60) return 'Just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString();
}

// ==========================================================================
// Spatial Coordinate Overlay Canvas Heatmap Logic
// ==========================================================================
function resizeHeatmapCanvas() {
    const img = document.getElementById('layout-image');
    const canvas = document.getElementById('heatmap-canvas');
    if (!img || !canvas) return;

    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
}

function drawHeatmap() {
    const canvas = document.getElementById('heatmap-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (heatmapCoords.length === 0) return;

    // Detect coordinate limits dynamically to support scaling
    let maxX = 0;
    let maxY = 0;
    heatmapCoords.forEach(c => {
        if (c.x > maxX) maxX = c.x;
        if (c.y > maxY) maxY = c.y;
    });

    // Smart auto-resolution scaling
    let sourceWidth = 640;
    let sourceHeight = 480;
    
    if (maxX > 1920 || maxY > 1080) {
        sourceWidth = 3840;
        sourceHeight = 2160;
    } else if (maxX > 640 || maxY > 480) {
        sourceWidth = 1920;
        sourceHeight = 1080;
    }

    const scaleX = canvas.width / sourceWidth;
    const scaleY = canvas.height / sourceHeight;

    // Render radial glow gradients for coordinates density plotting
    heatmapCoords.forEach(point => {
        const canvasX = point.x * scaleX;
        const canvasY = point.y * scaleY;
        const radius = 35; // Size of glowing hotspot
        
        // Define color gradient (Center: solid color, Outer: transparent)
        const gradient = ctx.createRadialGradient(canvasX, canvasY, 2, canvasX, canvasY, radius);
        
        // Blend coloring depending on camera type / densities
        if (currentCameraId === 'CAM5') {
            // Queue area (magenta/red alert theme)
            gradient.addColorStop(0, 'rgba(255, 8, 68, 0.45)');
            gradient.addColorStop(0.5, 'rgba(155, 81, 224, 0.2)');
            gradient.addColorStop(1, 'rgba(155, 81, 224, 0)');
        } else {
            // Browsing zone area (cyan/blue shopper theme)
            gradient.addColorStop(0, 'rgba(0, 242, 254, 0.5)');
            gradient.addColorStop(0.5, 'rgba(79, 172, 254, 0.2)');
            gradient.addColorStop(1, 'rgba(79, 172, 254, 0)');
        }
        
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(canvasX, canvasY, radius, 0, Math.PI * 2);
        ctx.fill();
    });

    // Mouse hover spatial coordinates checker on canvas
    canvas.onmousemove = (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        let hoveredPoint = null;
        let minDistance = 20; // proximity threshold in px
        
        heatmapCoords.forEach(point => {
            const canvasX = point.x * scaleX;
            const canvasY = point.y * scaleY;
            const dist = Math.hypot(mouseX - canvasX, mouseY - canvasY);
            
            if (dist < minDistance) {
                minDistance = dist;
                hoveredPoint = point;
            }
        });

        const tooltip = document.getElementById('heatmap-tooltip');
        if (hoveredPoint) {
            // Render tooltip at cursor position
            tooltip.style.opacity = '1';
            tooltip.style.left = `${mouseX + 15}px`;
            tooltip.style.top = `${mouseY + 15}px`;
            tooltip.innerHTML = `
                <div style="font-weight:700; color:var(--neon-cyan)">Visitor Hotspot</div>
                <div>Relative Pos: X=${Math.round(hoveredPoint.x)}, Y=${Math.round(hoveredPoint.y)}</div>
                <div>Density Weight: ${(hoveredPoint.weight || 1.0).toFixed(1)}</div>
            `;
        } else {
            tooltip.style.opacity = '0';
        }
    };

    canvas.onmouseleave = () => {
        const tooltip = document.getElementById('heatmap-tooltip');
        tooltip.style.opacity = '0';
    };
}

// ==========================================================================
// Event Ingestion Simulation (Integrates directly with POST /events/ingest)
// ==========================================================================
async function triggerMockEventIngest() {
    showToast('Simulating live shopper crossing tripwire...');
    
    // Choose random event triggers for simulation
    const simulatedEvents = [
        {
            camera_id: 'CAM3',
            event_type: 'ENTRY',
            zone_id: null,
            bounding_box: [1920.0, 1080.0, 1980.0, 1140.0]
        },
        {
            camera_id: 'CAM1',
            event_type: 'ZONE_ENTER',
            zone_id: 'skincare',
            bounding_box: [150.0, 200.0, 220.0, 300.0]
        },
        {
            camera_id: 'CAM2',
            event_type: 'ZONE_ENTER',
            zone_id: 'makeup',
            bounding_box: [320.0, 110.0, 380.0, 210.0]
        },
        {
            camera_id: 'CAM5',
            event_type: 'BILLING_QUEUE_JOIN',
            zone_id: 'billing_queue',
            bounding_box: [410.0, 380.0, 480.0, 450.0]
        }
    ];

    const pick = simulatedEvents[Math.floor(Math.random() * simulatedEvents.length)];
    const payload = {
        store_id: currentStoreId,
        camera_id: pick.camera_id,
        local_tracker_id: Math.floor(Math.random() * 500) + 1,
        event_type: pick.event_type,
        zone_id: pick.zone_id,
        timestamp: new Date().toISOString(),
        dwell_time_seconds: pick.event_type.includes('EXIT') || pick.event_type.includes('DWELL') ? 12.5 : null,
        bounding_box: pick.bounding_box,
        detection_confidence: parseFloat((Math.random() * 0.15 + 0.82).toFixed(2)),
        visual_embedding: Array.from({length: 512}, () => parseFloat((Math.random() * 0.2 - 0.1).toFixed(4)))
    };

    try {
        const response = await fetch(`${BASE_URL}/events/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const data = await response.json();
            showToast(`Event processed! Resolved Visitor ID: ${data.resolved_visitor_id ? data.resolved_visitor_id.substring(0, 8) + '...' : 'New'}`);
            // Instant data refresh
            fetchData();
        } else {
            console.error("Ingestion simulation failed status", response);
            showToast('Ingestion failed: verify API availability.');
        }
    } catch (e) {
        console.error("Simulation error", e);
        showToast('Error: Unable to connect to ingest API.');
    }
}

// ==========================================================================
// Toast Notifications UI Helper
// ==========================================================================
function showToast(message) {
    // Delete any existing toast
    const existing = document.querySelector('.notification-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'notification-toast';
    toast.innerHTML = `
        <i class="fa-solid fa-circle-info text-cyan"></i>
        <span>${message}</span>
    `;
    document.body.appendChild(toast);
    
    // Auto-destruct after 3.5s
    setTimeout(() => {
        toast.style.animation = 'slideInUp 0.3s reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

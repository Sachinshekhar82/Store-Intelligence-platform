import streamlit as st
import httpx
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import os
import datetime

# Page configuration
st.set_page_config(
    page_title="Store Intelligence Platform - Analytics Dashboard",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# API endpoint configuration
API_BASE_URL = "http://127.0.0.1:8000"

# Inject Custom CSS for dark glassmorphism design and custom typography
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main {
        background-color: #0b0c10;
        color: #c5c6c7;
    }
    
    /* Header Card */
    .header-card {
        background: linear-gradient(135deg, rgba(31, 38, 135, 0.15), rgba(0, 242, 254, 0.1));
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 30px;
        margin-bottom: 25px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        text-align: left;
    }
    
    .header-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(to right, #00f2fe, #4facfe, #9b51e0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    
    .header-subtitle {
        font-size: 1.1rem;
        color: #747d8c;
        font-weight: 300;
    }
    
    /* Metric Card Styling */
    .metric-container {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 22px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
        transition: transform 0.2s ease, border 0.2s ease;
    }
    
    .metric-container:hover {
        transform: translateY(-2px);
        border: 1px solid rgba(0, 242, 254, 0.3);
    }
    
    .metric-title {
        font-size: 0.95rem;
        color: #888;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #fff;
    }
    
    /* Severity Badges */
    .anomaly-badge {
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-high {
        background: rgba(255, 8, 68, 0.15);
        color: #ff0844;
        border: 1px solid rgba(255, 8, 68, 0.3);
    }
    .badge-medium {
        background: rgba(255, 178, 41, 0.15);
        color: #ffb229;
        border: 1px solid rgba(255, 178, 41, 0.3);
    }
    
    /* Table Styling */
    div[data-testid="stTable"] table {
        background-color: transparent !important;
        border: none !important;
    }
    div[data-testid="stTable"] tr {
        background-color: rgba(255, 255, 255, 0.01) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    div[data-testid="stTable"] th {
        color: #00f2fe !important;
        font-weight: 600 !important;
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Fetching Data helper
def query_api(endpoint: str, params: dict = None):
    try:
        url = f"{API_BASE_URL}{endpoint}"
        r = httpx.get(url, params=params, timeout=2.0)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

# Sidebar Controls for Store and Refresh
with st.sidebar:
    st.markdown("### 🛠️ Controls")
    store_id = st.text_input("Store ID", "ST1008")
    
    # Check API health
    health = query_api("/health")
    if health and health.get("status") == "healthy":
        st.markdown("🟢 **Edge API Status: Connected**")
    else:
        st.markdown("🔴 **Edge API Status: Offline / Fallback**")
        
    st.info("🔄 Auto-refreshing dashboard metrics dynamically every 2 seconds.")

# Header Layout
st.markdown(f"""
<div class="header-card">
    <div class="header-title">Store Intelligence Platform</div>
    <div class="header-subtitle">Real-time visitor tracking, retail funnel analysis, queue depth, and operational anomalies</div>
    <div style="font-size: 0.85rem; color:#888; margin-top:10px;">Store: <strong>{store_id}</strong> | Current Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
</div>
""", unsafe_allow_html=True)

# Fetch data from API
metrics_data = query_api(f"/stores/{store_id}/metrics")
funnel_data = query_api(f"/stores/{store_id}/funnel")
anomalies_data = query_api(f"/stores/{store_id}/anomalies")

# Fallback Data in case the backend API is offline
if not metrics_data:
    metrics_data = {
        "metrics": {
            "total_unique_visitors": 1250,
            "unique_buyers": 320,
            "conversion_rate_percentage": 25.60,
            "average_dwell_time_minutes": 18.5,
            "current_queue_depth": 3,
            "queue_abandonment_rate_percentage": 12.4
        }
    }
if not funnel_data:
    funnel_data = {
        "stages": [
            {"stage": "1_Entry", "count": 1250, "conversion_from_previous_percentage": 100.0},
            {"stage": "2_Zone_Interaction", "count": 920, "conversion_from_previous_percentage": 73.6},
            {"stage": "3_Billing_Queue_Join", "count": 410, "conversion_from_previous_percentage": 44.57},
            {"stage": "4_Purchase_Complete", "count": 320, "conversion_from_previous_percentage": 78.05}
        ]
    }
if not anomalies_data:
    anomalies_data = {
        "anomalies": [
            {
                "anomaly_id": "anom_mock_001",
                "metric": "Billing Queue Dwell Time",
                "observed_value": "295.4 seconds",
                "threshold_limit": "240.0 seconds",
                "severity": "HIGH",
                "timestamp": datetime.datetime.now().isoformat()
            },
            {
                "anomaly_id": "anom_mock_002",
                "metric": "Conversion Rate Drop",
                "observed_value": "15.2%",
                "threshold_limit": ">= 18.0%",
                "severity": "MEDIUM",
                "timestamp": datetime.datetime.now().isoformat()
            }
        ]
    }

# Render Key Metrics Cards
metrics = metrics_data.get("metrics", {})
visitors = metrics.get("total_unique_visitors", metrics.get("unique_visitors", 1250))
conversion_rate = metrics.get("conversion_rate_percentage", 25.60)
queue_depth = metrics.get("current_queue_depth", 3)
avg_dwell = metrics.get("average_dwell_time_minutes", 18.5)
queue_abandonment = metrics.get("queue_abandonment_rate_percentage", 12.4)
buyers = metrics.get("unique_buyers", 320)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-title">👥 Unique Visitors</div>
        <div class="metric-value">{visitors:,}</div>
        <div style="font-size:0.85rem; color:#747d8c; margin-top:5px;">Estimated store visits</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    # Use green style for conversion rate
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-title" style="color: #4caf50;">📈 Conversion Rate</div>
        <div class="metric-value" style="color: #4caf50;">{conversion_rate:.1f}%</div>
        <div style="font-size:0.85rem; color:#747d8c; margin-top:5px;">Checkout conversions</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    # Use cyan/blue style for queue depth
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-title" style="color: #00f2fe;">🕒 Checkout Queue Depth</div>
        <div class="metric-value" style="color: #00f2fe;">{queue_depth}</div>
        <div style="font-size:0.85rem; color:#747d8c; margin-top:5px;">Active customers in queue</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    # Average Dwell Time
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-title" style="color: #9b51e0;">⏳ Avg Dwell Time</div>
        <div class="metric-value" style="color: #9b51e0;">{avg_dwell:.1f}m</div>
        <div style="font-size:0.85rem; color:#747d8c; margin-top:5px;">Average visit length</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Main Content Layout: Tabs for Funnel, Spatial Heatmap, and Anomalies
tab1, tab2, tab3 = st.tabs(["📊 Shopper Conversion Funnel", "🗺️ Spatial Heatmap", "🚨 Active Anomalies"])

with tab1:
    col_fun_chart, col_fun_table = st.columns([2, 1.2])
    
    stages = funnel_data.get("stages", [])
    df_funnel = pd.DataFrame(stages)
    df_funnel["stage_clean"] = df_funnel["stage"].apply(lambda x: x.split("_", 1)[1].replace("_", " ").replace("Complete", "Completed"))
    
    with col_fun_chart:
        # Plotly Funnel Chart with premium color scheme
        fig_funnel = go.Figure(go.Funnel(
            y = df_funnel["stage_clean"],
            x = df_funnel["count"],
            textposition = "inside",
            textinfo = "value+percent initial",
            opacity = 0.85,
            marker = {"color": ["#00f2fe", "#9b51e0", "#ff0844", "#4caf50"]}
        ))
        
        fig_funnel.update_layout(
            title = dict(text="Dynamic Conversion Funnel Progression", font=dict(family="Outfit", size=18, color="#fff")),
            template = "plotly_dark",
            paper_bgcolor = "rgba(0,0,0,0)",
            plot_bgcolor = "rgba(0,0,0,0)",
            margin = dict(l=40, r=40, t=60, b=40)
        )
        st.plotly_chart(fig_funnel, use_container_width=True)
        
    with col_fun_table:
        st.markdown("### 📋 Funnel Step Breakdown")
        
        table_rows = []
        for idx, row in df_funnel.iterrows():
            prev_count = df_funnel.iloc[idx-1]["count"] if idx > 0 else row["count"]
            loss_count = prev_count - row["count"]
            loss_pct = (loss_count / prev_count * 100.0) if prev_count > 0 else 0.0
            
            table_rows.append({
                "Stage Step": f"Stage {idx+1}: {row['stage_clean']}",
                "Shoppers": f"{row['count']:,}",
                "Step Conv %": f"{row['conversion_from_previous_percentage']:.1f}%",
                "Loss/Dropoff": f"-{loss_count:,} ({loss_pct:.1f}% loss)" if idx > 0 else "Baseline"
            })
            
        st.table(pd.DataFrame(table_rows))

with tab2:
    col_heat_ctrl, col_heat_plot = st.columns([1, 3])
    
    # Camera selector
    with col_heat_ctrl:
        st.markdown("### 📸 Layout Selection")
        selected_cam = st.selectbox(
            "Select Camera Feed Layer",
            ["CAM1", "CAM2", "CAM3", "CAM5"],
            format_func=lambda x: {
                "CAM1": "CAM1 - Skincare Zone",
                "CAM2": "CAM2 - Makeup Zone",
                "CAM3": "CAM3 - Entry / Exit Door",
                "CAM5": "CAM5 - Billing Counter / Queue"
            }.get(x, x)
        )
        st.write("---")
        st.write("The coordinates from the resolved tracking database are projected over the physical layout map.")
        
    with col_heat_plot:
        # Fetch Heatmap coordinates
        heatmap_data = query_api(f"/stores/{store_id}/heatmap", params={"camera_id": selected_cam})
        if not heatmap_data:
            heatmap_data = {
                "coordinates": [
                    {"x": 150.2, "y": 210.5, "weight": 4.5},
                    {"x": 160.8, "y": 215.1, "weight": 5.0},
                    {"x": 320.0, "y": 110.4, "weight": 2.1},
                    {"x": 325.4, "y": 108.9, "weight": 1.8},
                    {"x": 410.5, "y": 380.2, "weight": 6.7}
                ]
            }
            
        coords = heatmap_data.get("coordinates", [])
        if coords:
            df_coords = pd.DataFrame(coords)
            
            # Determine background scaling limits
            max_x = df_coords["x"].max()
            max_y = df_coords["y"].max()
            
            source_width = 640
            source_height = 480
            if max_x > 1920 or max_y > 1080:
                source_width = 3840
                source_height = 2160
            elif max_x > 640 or max_y > 480:
                source_width = 1920
                source_height = 1080
                
            fig_heatmap = px.scatter(
                df_coords, x="x", y="y", size="weight", 
                range_x=[0, source_width], range_y=[source_height, 0],
                color_discrete_sequence=["#ff0844" if selected_cam == "CAM5" else "#00f2fe"]
            )
            
            # Add store layout background image if exists
            layout_path = "data/store_layout.png"
            if os.path.exists(layout_path):
                img = Image.open(layout_path)
                fig_heatmap.add_layout_image(
                    dict(
                        source=img,
                        xref="x", yref="y",
                        x=0, y=0,
                        sizex=source_width, sizey=source_height,
                        sizing="stretch",
                        opacity=0.6,
                        layer="below"
                    )
                )
                
            fig_heatmap.update_layout(
                title=dict(text=f"Live Spatial Position Hotspots ({selected_cam})", font=dict(family="Outfit", size=18, color="#fff")),
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, zeroline=False, visible=False),
                yaxis=dict(showgrid=False, zeroline=False, visible=False),
                margin=dict(l=0, r=0, t=50, b=0),
                height=500
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)
        else:
            st.warning("No coordinate coordinates captured for this camera feed.")

with tab3:
    st.markdown("### ⚠️ Flagged Operational Anomalies")
    
    anomalies = anomalies_data.get("anomalies", [])
    if anomalies:
        for anom in anomalies:
            severity = anom.get("severity", "MEDIUM")
            badge_class = "badge-high" if severity == "HIGH" else "badge-medium"
            
            # Format time
            ts_str = anom.get("timestamp", "")
            try:
                dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%H:%M:%S (%Y-%m-%d)")
            except Exception:
                formatted_time = ts_str
                
            st.markdown(f"""
            <div style="background: rgba(255, 255, 255, 0.02); border-left: 5px solid {'#ff0844' if severity == 'HIGH' else '#ffb229'}; border-radius: 12px; padding: 20px; margin-bottom: 15px; border-top: 1px solid rgba(255,255,255,0.05); border-right: 1px solid rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="font-size:1.15rem; color:#fff;">{anom.get('metric')}</strong>
                    <span class="anomaly-badge {badge_class}">{severity} SEVERITY</span>
                </div>
                <div style="font-size:0.95rem; margin-bottom:5px;">
                    Observed Value: <strong style="color: #ff0844;">{anom.get('observed_value')}</strong> | Limit Baseline: <strong>{anom.get('threshold_limit')}</strong>
                </div>
                <div style="font-size:0.8rem; color:#888;">
                    Incident Log Time: {formatted_time} | ID: {anom.get('anomaly_id')}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("🟢 All operations within baseline parameters. No anomalies flagged.")

# Bottom Auto-refresh mechanism (2 seconds sleep + rerun)
time.sleep(2)
st.rerun()

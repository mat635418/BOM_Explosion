import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import numpy as np

# ==========================================
# 1. PAGE CONFIG & STYLING
# ==========================================
st.set_page_config(page_title="SAP BOM Visualizer", layout="wide", page_icon="🏭")

st.markdown("""
<style>
    .block-container {padding-top: 1rem !important;}
    div[data-testid="stExpander"] details summary p {font-weight: bold;}
    
    /* Legend Styling */
    .legend-box {
        background-color: #f9fafb;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
    }
    .legend-item {
        display: flex;
        align-items: center;
        margin-bottom: 6px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 13px;
    }
    .legend-color {
        width: 16px;
        height: 16px;
        margin-right: 10px;
        border-radius: 3px;
        border: 1px solid rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- STRICT PASTEL COLOR PALETTE ---
STYLE_MAP = {
    "FG":       {"color": "#93C5FD", "shape": "box",      "label": "Finished Good", "desc": "CURT, FERT"}, # Blue
    "ASSM":     {"color": "#5EEAD4", "shape": "diamond",  "label": "Assembly",      "desc": "ASSM, HALB"}, # Teal
    "CMPD":     {"color": "#C084FC", "shape": "hexagon",  "label": "Compound",      "desc": "CMPD"},       # Purple
    "RAW":      {"color": "#86EFAC", "shape": "dot",      "label": "Raw Material",  "desc": "RAW, ROH, LRAW"}, # Green
    "GUM":      {"color": "#F9A8D4", "shape": "star",     "label": "Rubber/Gum",    "desc": "GUM"},        # Pink
    "PACK":     {"color": "#FCD34D", "shape": "square",   "label": "Packaging",     "desc": "VERP"},       # Yellow
    "DEFAULT":  {"color": "#E5E7EB", "shape": "ellipse",  "label": "Other",         "desc": "Unknown"}     # Grey
}

# ==========================================
# 2. DATA LOGIC (ROBUST)
# ==========================================
def find_material_type_column(df):
    target_headers = ["material type", "mat. type", "mat_type", "ptyp", "mtart"]
    for col in df.columns:
        if any(t in str(col).lower() for t in target_headers): return col
    
    # Fallback
    for col in df.columns:
        c_str = str(col).lower()
        if "type" in c_str and not any(x in c_str for x in ["mrp", "item", "doc", "class"]):
            return col
    return None

def normalize_material_type(raw_type):
    t = str(raw_type).upper().strip()
    
    # Logic Priority: Raw -> Compound -> Semi -> FG
    if any(x in t for x in ["RAW", "ROH", "LRAW", "ZROH"]): return "RAW"
    if "CMPD" in t: return "CMPD"
    if "GUM" in t: return "GUM"
    if any(x in t for x in ["ASSM", "HALB", "SEMI"]): return "ASSM"
    if any(x in t for x in ["CURT", "FERT", "FRIP"]): return "FG"
    if "VERP" in t or "PACK" in t: return "PACK"
    
    return "DEFAULT"

def load_data(uploaded_file):
    try:
        uploaded_file.seek(0)
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin1')
        else:
            df = pd.read_excel(uploaded_file)

        if df.empty: return None

        col_level = next((c for c in df.columns if any(x in str(c).lower() for x in ["level", "lvl"])), None)
        col_comp = next((c for c in df.columns if any(x in str(c).lower() for x in ["component", "material", "object"])), None)
        col_type = find_material_type_column(df)
        col_qty = next((c for c in df.columns if any(x in str(c).lower() for x in ["qty", "quantity", "amount"])), None)
        col_unit = next((c for c in df.columns if any(x in str(c).lower() for x in ["unit", "uom", "bun"])), None)
        col_desc = next((c for c in df.columns if any(x in str(c).lower() for x in ["desc", "description", "text"])), None)

        if not col_level or not col_comp:
            st.error(f"Missing Level/Component columns. Found: {list(df.columns)}")
            return None

        clean_df = pd.DataFrame()
        clean_df["Level"] = pd.to_numeric(df[col_level], errors='coerce').fillna(0).astype(int)
        clean_df["Component"] = df[col_comp].astype(str).str.strip()
        clean_df["Description"] = df[col_desc].astype(str) if col_desc else ""
        clean_df["Unit"] = df[col_unit].astype(str) if col_unit else ""
        clean_df["Quantity"] = pd.to_numeric(df[col_qty], errors='coerce').fillna(1.0) if col_qty else 1.0

        if col_type:
            clean_df["Raw_Type"] = df[col_type].astype(str).str.strip().str.upper()
            clean_df["Category"] = clean_df["Raw_Type"].apply(normalize_material_type)
        else:
            clean_df["Raw_Type"] = "Unknown"
            clean_df["Category"] = "DEFAULT"

        return clean_df
    except Exception as e:
        st.error(f"Data Error: {e}")
        return None

# ==========================================
# 3. GRAPH BUILDER (HTML & HIGHLIGHT FIX)
# ==========================================
def build_network(df):
    G = nx.DiGraph()
    stack = {} 

    for _, row in df.iterrows():
        level = row["Level"]
        comp = row["Component"]
        cat = row["Category"]
        
        style = STYLE_MAP.get(cat, STYLE_MAP["DEFAULT"])
        
        # --- HTML TOOLTIP FIX ---
        # 1. Use simple inline CSS
        # 2. Use .replace('\n', '') to strictly remove newlines which break Vis.js
        html_content = (
            f"<div style='font-family: Arial; font-size: 12px; padding: 5px; color: #333;'>"
            f"  <strong style='font-size: 14px;'>{comp}</strong><br>"
            f"  <span style='color: #666; font-style: italic;'>{row['Description']}</span><br>"
            f"  <hr style='border: 0; border-top: 1px solid #ddd; margin: 5px 0;'>"
            f"  Type: <b>{row['Raw_Type']}</b> ({cat})<br>"
            f"  Level: {level}<br>"
            f"  Qty: {row['Quantity']} {row['Unit']}"
            f"</div>"
        )
        # CRITICAL: Flatten the string
        tooltip_safe = html_content.replace("\n", "").replace("\r", "")

        G.add_node(
            comp, 
            label=comp, 
            title=tooltip_safe,   # The safe HTML string
            color=style["color"],
            shape=style["shape"],
            size=25 if level == 1 else 18,
            level=level,
            borderWidth=1,
            borderWidthSelected=3,
        )

        stack[level] = comp
        if level > 1:
            parent_level = level - 1
            while parent_level > 0 and parent_level not in stack:
                parent_level -= 1
            
            if parent_level in stack:
                parent = stack[parent_level]
                w = 1 + np.log1p(row['Quantity']) if row['Quantity'] > 0 else 1
                G.add_edge(parent, comp, width=w, color="#CBD5E1") 
    
    return G

# ==========================================
# 4. MAIN APP
# ==========================================
st.title("🏭 SAP BOM Cockpit")

with st.sidebar:
    st.header("1. Upload Data")
    uploaded_file = st.file_uploader("Upload BOM", type=["csv", "xlsx"])
    
    st.markdown("---")
    st.header("Legend")
    st.markdown('<div class="legend-box">', unsafe_allow_html=True)
    for key, style in STYLE_MAP.items():
        st.markdown(f"""
        <div class="legend-item">
            <div class="legend-color" style="background-color: {style['color']};"></div>
            <div>
                <strong>{style['label']}</strong><br>
                <span style="color:#666; font-size:10px;">{style['desc']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    if df is not None:
        G = build_network(df)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Structure: {df.iloc[0]['Component']}")
        with col2:
            search = st.text_input("🔍 Find Node", "")

        net = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="#333", directed=True)
        
        # --- HIGHLIGHT FIX: Explicit Node Coloring ---
        if search:
            for n in G.nodes:
                if search.lower() in n.lower():
                    # Direct override for found nodes
                    G.nodes[n]['color'] = "#F59E0B"
                    G.nodes[n]['size'] = 30
                    G.nodes[n]['borderWidth'] = 3
        
        net.from_nx(G)
        
        # --- OPTIONS FIX ---
        # No JS functions here. Pure JSON.
        # We set specific "highlight" and "hover" colors in the global options.
        net.set_options("""
        {
          "nodes": {
            "font": { "size": 14, "face": "Segoe UI" },
            "color": {
                "highlight": {
                    "border": "#D97706",
                    "background": "#F59E0B"
                },
                "hover": {
                    "border": "#D97706",
                    "background": "#F59E0B"
                }
            }
          },
          "edges": {
            "color": { 
                "color": "#CBD5E1", 
                "highlight": "#F59E0B",
                "hover": "#F59E0B"
            },
            "smooth": { "type": "cubicBezier", "forceDirection": "horizontal", "roundness": 0.4 }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 50,
            "hideEdgesOnDrag": false
          },
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "LR",
              "sortMethod": "directed",
              "levelSeparation": 250,
              "nodeSpacing": 150
            }
          },
          "physics": {
            "hierarchicalRepulsion": { "nodeDistance": 160 },
            "solver": "hierarchicalRepulsion"
          }
        }
        """)

        try:
            net.save_graph("bom_viz.html")
            with open("bom_viz.html", 'r', encoding='utf-8') as f:
                source_html = f.read()
            components.html(source_html, height=800, scrolling=False)
        except Exception as e:
            st.error(f"Graph Render Error: {e}")

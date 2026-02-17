import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import numpy as np
import os

# ==========================================
# 1. PAGE CONFIG & PASTEL STYLING
# ==========================================
st.set_page_config(page_title="SAP BOM Visualizer", layout="wide", page_icon="🏭")

# Custom CSS for cleaner look
st.markdown("""
<style>
    .block-container {padding-top: 1rem !important;}
    div[data-testid="stExpander"] details summary p {font-weight: bold;}
    .legend-item {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        font-family: sans-serif;
        font-size: 14px;
    }
    .legend-color {
        width: 18px;
        height: 18px;
        margin-right: 12px;
        border-radius: 4px;
        border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# --- PASTEL COLOR PALETTE (Functional Semantics) ---
# Keys are the "Normalized" types we will assign in logic
# Colors are Pastel Hex codes
STYLE_MAP = {
    "FG":       {"color": "#93C5FD", "shape": "box",      "label": "Finished Good", "desc": "CURT, FERT"}, # Pastel Blue
    "ASSM":     {"color": "#5EEAD4", "shape": "diamond",  "label": "Assembly",      "desc": "ASSM, HALB"}, # Pastel Teal
    "CMPD":     {"color": "#C084FC", "shape": "hexagon",  "label": "Compound",      "desc": "CMPD"},       # Pastel Purple
    "RAW":      {"color": "#86EFAC", "shape": "dot",      "label": "Raw Material",  "desc": "RAW, ROH, LRAW"}, # Pastel Green
    "GUM":      {"color": "#F9A8D4", "shape": "star",     "label": "Rubber/Gum",    "desc": "GUM"},        # Pastel Pink
    "PACK":     {"color": "#FCD34D", "shape": "square",   "label": "Packaging",     "desc": "VERP"},       # Pastel Amber
    "DEFAULT":  {"color": "#E5E7EB", "shape": "ellipse",  "label": "Other",         "desc": "Unknown"}     # Pastel Grey
}

# ==========================================
# 2. DATA PROCESSING LOGIC
# ==========================================
def find_material_type_column(df):
    """
    Hunts for the Material Type column, explicitly ignoring 'MRP Type' or 'Item Category'.
    """
    # Priority 1: Specific Headers
    target_headers = ["material type", "mat. type", "mat_type", "ptyp", "mtart"]
    for col in df.columns:
        if any(t in col.lower() for t in target_headers):
            return col
            
    # Priority 2: 'Type' but not 'MRP'/'Item'/'Doc'
    for col in df.columns:
        c_low = col.lower()
        if "type" in c_low and not any(x in c_low for x in ["mrp", "item", "doc", "class"]):
            return col
    return None

def normalize_material_type(raw_type):
    """
    Maps SAP codes (ROH, ZROH, CURT) to our 6 functional categories.
    """
    t = str(raw_type).upper().strip()
    
    if any(x in t for x in ["RAW", "ROH", "LRAW", "ZROH"]): return "RAW"
    if "CMPD" in t: return "CMPD"
    if any(x in t for x in ["ASSM", "HALB", "SEMI"]): return "ASSM"
    if any(x in t for x in ["CURT", "FERT", "FRIP"]): return "FG"
    if "GUM" in t: return "GUM"
    if "VERP" in t or "PACK" in t: return "PACK"
    
    return "DEFAULT"

def load_data(uploaded_file):
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # 1. Identify Columns
        col_level = next((c for c in df.columns if any(x in c.lower() for x in ["level", "lvl"])), None)
        col_comp = next((c for c in df.columns if any(x in c.lower() for x in ["component", "material", "object"])), None)
        col_type = find_material_type_column(df) # Smart search
        col_qty = next((c for c in df.columns if any(x in c.lower() for x in ["qty", "quantity", "amount"])), None)
        col_unit = next((c for c in df.columns if any(x in c.lower() for x in ["unit", "uom", "bun"])), None)
        col_desc = next((c for c in df.columns if any(x in c.lower() for x in ["desc", "description", "text"])), None)

        if not col_level or not col_comp:
            st.error("Missing required columns: 'Level' or 'Component'")
            return None

        # 2. Normalize Data
        clean_df = pd.DataFrame()
        clean_df["Level"] = pd.to_numeric(df[col_level], errors='coerce').fillna(0).astype(int)
        clean_df["Component"] = df[col_comp].astype(str).str.strip()
        clean_df["Description"] = df[col_desc].astype(str) if col_desc else ""
        clean_df["Unit"] = df[col_unit].astype(str) if col_unit else ""
        
        # Quantity Logic
        if col_qty:
            clean_df["Quantity"] = pd.to_numeric(df[col_qty], errors='coerce').fillna(1.0)
        else:
            clean_df["Quantity"] = 1.0

        # Type Logic (Raw SAP Type -> Normalized Functional Category)
        if col_type:
            clean_df["Raw_Type"] = df[col_type].astype(str).str.strip().upper()
            clean_df["Category"] = clean_df["Raw_Type"].apply(normalize_material_type)
        else:
            clean_df["Raw_Type"] = "Unknown"
            clean_df["Category"] = "DEFAULT"

        return clean_df

    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# ==========================================
# 3. GRAPH BUILDER
# ==========================================
def build_network(df):
    G = nx.DiGraph()
    stack = {} 

    for _, row in df.iterrows():
        level = row["Level"]
        comp = row["Component"]
        cat = row["Category"]
        
        # Get Style config
        style = STYLE_MAP.get(cat, STYLE_MAP["DEFAULT"])
        
        # Enhanced Tooltip HTML
        tooltip = f"""
        <div style='font-family: sans-serif; padding: 5px; min-width: 150px;'>
            <strong style='font-size: 14px;'>{comp}</strong><br>
            <span style='color: #666;'>{row['Description']}</span><hr style='margin: 5px 0; border-top: 1px solid #eee;'>
            Type: <b>{row['Raw_Type']}</b> ({cat})<br>
            Level: {level}<br>
            Qty: {row['Quantity']} {row['Unit']}
        </div>
        """
        
        G.add_node(
            comp, 
            label=comp, 
            title=tooltip, # HTML Tooltip
            color=style["color"],
            shape=style["shape"],
            size=25 if level == 1 else 18,
            level=level,
            group=cat # For PyVis grouping
        )

        # Parent-Child Logic
        stack[level] = comp
        if level > 1:
            parent_level = level - 1
            while parent_level > 0 and parent_level not in stack:
                parent_level -= 1
            
            if parent_level in stack:
                parent = stack[parent_level]
                
                # Edge width based on Log Quantity
                w = 1.0
                if row['Quantity'] > 0:
                    w = 1 + np.log1p(row['Quantity'])
                
                G.add_edge(parent, comp, width=w, title=f"Qty: {row['Quantity']}")
    
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
    
    # Dynamic Legend Loop
    for key, style in STYLE_MAP.items():
        st.markdown(f"""
        <div class="legend-item">
            <div class="legend-color" style="background-color: {style['color']};"></div>
            <div>
                <strong>{style['label']}</strong><br>
                <span style="font-size:11px; color:#666;">{style['desc']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.caption("Double-click a node to focus. Drag to move.")

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    if df is not None:
        # Debug Info
        with st.expander("Show Data & Type Mapping Check"):
            st.dataframe(df[["Level", "Component", "Raw_Type", "Category", "Description"]].head(20))

        # Build Graph
        G = build_network(df)
        
        # Search & Filter
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Structure: {df.iloc[0]['Component']}")
        with col2:
            search = st.text_input("🔍 Find Node", "")

        # PyVis Configuration
        net = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="#333", directed=True)
        
        # Apply Search Highlighting
        if search:
            for n in G.nodes:
                if search.lower() in n.lower():
                    G.nodes[n]['color'] = "#EF4444" # Bright Red for search hit
                    G.nodes[n]['size'] = 30
                    G.nodes[n]['borderWidth'] = 3

        net.from_nx(G)
        
        # ADVANCED OPTIONS: Interaction & Physics
        # This defines how the click highlighting works (High contrast orange)
        net.set_options("""
        {
          "nodes": {
            "borderWidth": 1,
            "borderWidthSelected": 3,
            "chosen": {
                "node": true,
                "label": true
            },
            "font": {
                "size": 14,
                "face": "sans-serif"
            }
          },
          "edges": {
            "color": {
              "color": "#CBD5E1",
              "highlight": "#F97316", 
              "hover": "#F97316"
            },
            "smooth": {
              "type": "cubicBezier",
              "forceDirection": "horizontal",
              "roundness": 0.4
            }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "hideEdgesOnDrag": false
          },
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "LR",
              "sortMethod": "directed",
              "levelSeparation": 220,
              "nodeSpacing": 160,
              "treeSpacing": 200
            }
          },
          "physics": {
            "hierarchicalRepulsion": {
              "centralGravity": 0.0,
              "springLength": 100,
              "springConstant": 0.01,
              "nodeDistance": 150,
              "damping": 0.09
            },
            "solver": "hierarchicalRepulsion"
          }
        }
        """)

        # Save & Render
        try:
            net.save_graph("bom_viz.html")
            with open("bom_viz.html", 'r', encoding='utf-8') as f:
                source_html = f.read()
            components.html(source_html, height=800, scrolling=False)
        except Exception as e:
            st.error(f"Graph Render Error: {e}")

else:
    st.info("Please upload a BOM file.")

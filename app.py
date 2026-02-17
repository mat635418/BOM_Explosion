import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import numpy as np
import os

# ==========================================
# 1. PAGE CONFIG & STYLING
# ==========================================
st.set_page_config(page_title="SAP BOM Visualizer", layout="wide", page_icon="🏭")

st.markdown("""
<style>
    .block-container {padding-top: 1rem !important;}
    div[data-testid="stExpander"] details summary p {font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# Color Palette for SAP Material Types
# keys are used for strict matching, but we will also use fuzzy matching in the logic
STYLE_MAP = {
    "CURT": {"color": "#0047AB", "shape": "box", "label": "FG (CURT)"},      # Cobalt Blue
    "FERT": {"color": "#0047AB", "shape": "box", "label": "FG (FERT)"},
    "HALB": {"color": "#008080", "shape": "diamond", "label": "Semi-Finished"}, # Teal
    "ASSM": {"color": "#008080", "shape": "diamond", "label": "Assembly"},
    "GUM":  {"color": "#D946EF", "shape": "star", "label": "Rubber/Gum"},    # Magenta
    "CMPD": {"color": "#800080", "shape": "hexagon", "label": "Compound"},   # Purple
    "RAW":  {"color": "#228B22", "shape": "dot", "label": "Raw Material"},   # Forest Green
    "ROH":  {"color": "#228B22", "shape": "dot", "label": "Raw Material"},
    "LRAW": {"color": "#228B22", "shape": "dot", "label": "Raw Material"},   # Legacy Raw
    "VERP": {"color": "#DAA520", "shape": "square", "label": "Packaging"},   # Goldenrod
    "DEFAULT": {"color": "#708090", "shape": "ellipse", "label": "Other"}   # Slate Grey
}

# ==========================================
# 2. ROBUST DATA LOADING (FIXED)
# ==========================================
def find_material_type_column(df):
    """
    Specifically hunts for the Material Type column with high precision.
    Prioritizes 'Material Type' over generic 'Type' or 'Category' to avoid 
    picking up 'MRP Type' or 'Item Category'.
    """
    # 1. Exact or near-exact matches for standard SAP headers
    # We look for these specific strings in the column headers
    target_headers = ["material type", "mat. type", "mat_type", "ptyp", "mtart"]
    
    for col in df.columns:
        if any(t in col.lower() for t in target_headers):
            return col
            
    # 2. Look for "Type" but exclude "MRP", "Item", "Doc"
    # This prevents picking up 'MRP Type' or 'Item Category'
    for col in df.columns:
        c_low = col.lower()
        if "type" in c_low and "mrp" not in c_low and "item" not in c_low and "doc" not in c_low:
            return col
            
    return None

def load_data(uploaded_file):
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Identify critical columns dynamically
        col_level = next((c for c in df.columns if any(x in c.lower() for x in ["level", "lvl"])), None)
        col_comp = next((c for c in df.columns if any(x in c.lower() for x in ["component", "material", "object"])), None)
        
        # THE FIX: Use the specific function for Material Type
        col_type = find_material_type_column(df)
        
        col_qty = next((c for c in df.columns if any(x in c.lower() for x in ["qty", "quantity", "amount"])), None)
        col_unit = next((c for c in df.columns if any(x in c.lower() for x in ["unit", "uom", "bun"])), None)
        col_desc = next((c for c in df.columns if any(x in c.lower() for x in ["desc", "description", "text"])), None)

        if not col_level or not col_comp:
            st.error(f"Could not find 'Level' or 'Component' columns. Found: {list(df.columns)}")
            return None

        # Standardize DataFrame
        clean_df = pd.DataFrame()
        clean_df["Level"] = pd.to_numeric(df[col_level], errors='coerce').fillna(0).astype(int)
        clean_df["Component"] = df[col_comp].astype(str).str.strip()
        
        # Clean Description
        clean_df["Description"] = df[col_desc].astype(str) if col_desc else ""
        
        # Clean Type (Crucial Step)
        if col_type:
            # Convert to string, strip whitespace, and upper case
            clean_df["Type"] = df[col_type].astype(str).str.strip().str.upper()
        else:
            clean_df["Type"] = "DEFAULT"
            
        clean_df["Unit"] = df[col_unit] if col_unit else ""
        
        # Clean Quantity
        if col_qty:
            clean_df["Quantity"] = pd.to_numeric(df[col_qty], errors='coerce').fillna(1.0)
        else:
            clean_df["Quantity"] = 1.0

        # DEBUG: Show user what we found to verify the fix
        with st.sidebar.expander("🕵️ Debug: Column Mapping"):
            st.write(f"**Level Col:** `{col_level}`")
            st.write(f"**Mat Type Col:** `{col_type}` (Used for Color)")
            st.write("**Unique Types Found:**")
            st.write(clean_df["Type"].unique())

        return clean_df

    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return None

# ==========================================
# 3. GRAPH CONSTRUCTION
# ==========================================
def build_network(df):
    G = nx.DiGraph()
    stack = {} # Stores {level: component_id}

    for _, row in df.iterrows():
        level = row["Level"]
        comp = row["Component"]
        m_type = str(row["Type"]).upper()
        
        # --- COLOR LOGIC (Fuzzy Matching) ---
        # This handles cases where type is "LRAW" or "ZROH" etc.
        if "RAW" in m_type or "ROH" in m_type:
            style = STYLE_MAP["RAW"]
        elif "CMPD" in m_type:
            style = STYLE_MAP["CMPD"]
        elif "ASSM" in m_type or "HALB" in m_type:
            style = STYLE_MAP["ASSM"]
        elif "GUM" in m_type:
             style = STYLE_MAP["GUM"]
        elif "CURT" in m_type or "FERT" in m_type:
             style = STYLE_MAP["CURT"]
        else:
            style = STYLE_MAP.get(m_type, STYLE_MAP["DEFAULT"])
        
        # Generate Tooltip
        title_html = f"<b>{comp}</b><br>Type: {m_type}<br>Level: {level}<br>Qty: {row['Quantity']} {row['Unit']}<br>{row['Description']}"
        
        G.add_node(
            comp, 
            label=comp, 
            title=title_html,
            color=style["color"],
            shape=style["shape"],
            size=25 if level == 1 else 15,
            level=level,  # Required for Hierarchical layout
            group=m_type  # Helpful for internal PyVis grouping
        )

        # Logic: Find Parent
        stack[level] = comp
        
        if level > 1:
            parent_level = level - 1
            # Backtrack stack to find nearest parent (handles skipped levels safely)
            while parent_level > 0 and parent_level not in stack:
                parent_level -= 1
            
            if parent_level in stack:
                parent = stack[parent_level]
                # Logarithmic width for edges based on quantity
                qty_val = row['Quantity']
                width = 1 + np.log1p(qty_val) if qty_val > 0 else 1
                
                G.add_edge(parent, comp, width=width, title=f"Qty: {qty_val}")
    
    return G

# ==========================================
# 4. MAIN APP LAYOUT
# ==========================================
st.title("🏭 SAP BOM Visualization (Robust)")

with st.sidebar:
    st.header("1. Upload Data")
    uploaded_file = st.file_uploader("Upload BOM (CSV/Excel)", type=["csv", "xlsx"])
    
    st.header("2. View Settings")
    layout_type = st.radio("Layout Direction", ["Left-to-Right (Process Flow)", "Top-Down (Org Chart)"], index=0)
    physics = st.checkbox("Enable Physics (Wobbly)", value=False)
    
    st.markdown("---")
    st.markdown("**Legend:**")
    # Custom Legend Display
    legend_items = [
        ("FG (Finished)", "#0047AB"),
        ("Assembly", "#008080"),
        ("Compound", "#800080"),
        ("Rubber/Gum", "#D946EF"),
        ("Raw Material", "#228B22"),
        ("Packaging", "#DAA520")
    ]
    for label, color in legend_items:
        st.markdown(f"<div style='display:flex; align-items:center;'><div style='width:15px;height:15px;background:{color};margin-right:10px;border-radius:50%;'></div>{label}</div>", unsafe_allow_html=True)

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    if df is not None:
        # Show Data Preview
        with st.expander("Show Raw Data Table", expanded=False):
            st.dataframe(df)

        # Build Graph
        G = build_network(df)
        
        # Filtering (Optional)
        col1, col2 = st.columns([3,1])
        with col1:
            st.subheader(f"Explosion for: {df.iloc[0]['Component']}")
        with col2:
             search_term = st.text_input("🔍 Highlight Component", "")
        
        # PyVis Setup
        net = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
        
        # Apply Search Highlighting
        if search_term:
            for node in G.nodes:
                if search_term.lower() in node.lower():
                    G.nodes[node]['color'] = "#FF0000" # Red for match
                    G.nodes[node]['size'] = 35
                    G.nodes[node]['shape'] = "star"
        
        net.from_nx(G)

        # Layout Configuration
        direction = "LR" if "Left" in layout_type else "UD"
        
        net.set_options(f"""
        {{
            "layout": {{
                "hierarchical": {{
                    "enabled": true,
                    "direction": "{direction}",
                    "sortMethod": "directed",
                    "levelSeparation": 200,
                    "nodeSpacing": 150
                }}
            }},
            "physics": {{
                "enabled": {str(physics).lower()},
                "hierarchicalRepulsion": {{
                    "nodeDistance": 150
                }}
            }}
        }}
        """)

        # Save and Display
        try:
            # Save locally to current directory (safer than /tmp on some OS)
            net.save_graph("bom_viz.html")
            
            # Read back and display
            with open("bom_viz.html", 'r', encoding='utf-8') as f:
                source_html = f.read()
            
            components.html(source_html, height=800, scrolling=False)
            
        except Exception as e:
            st.error(f"Error displaying graph: {e}")

else:
    st.info("Please upload your BOM file to begin.")

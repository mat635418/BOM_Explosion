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
st.set_page_config(page_title="SAP BOM Visualizer", layout="wide")

st.markdown("""
<style>
    .block-container {padding-top: 1rem !important;}
    div[data-testid="stExpander"] details summary p {font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# Color Palette for SAP Material Types
STYLE_MAP = {
    "CURT": {"color": "#0047AB", "shape": "box", "label": "FG (CURT)"},      # Cobalt Blue
    "FERT": {"color": "#0047AB", "shape": "box", "label": "FG (FERT)"},
    "HALB": {"color": "#008080", "shape": "diamond", "label": "Semi-Finished"}, # Teal
    "ASSM": {"color": "#008080", "shape": "diamond", "label": "Assembly"},
    "CMPD": {"color": "#800080", "shape": "hexagon", "label": "Compound"},   # Purple
    "RAW":  {"color": "#228B22", "shape": "dot", "label": "Raw Material"},   # Forest Green
    "ROH":  {"color": "#228B22", "shape": "dot", "label": "Raw Material"},
    "VERP": {"color": "#DAA520", "shape": "square", "label": "Packaging"},   # Goldenrod
    "DEFAULT": {"color": "#708090", "shape": "ellipse", "label": "Other"}   # Slate Grey
}

# ==========================================
# 2. ROBUST DATA LOADING
# ==========================================
def find_column(df, keywords):
    """Searches for a column containing any of the keywords (case insensitive)."""
    for col in df.columns:
        for key in keywords:
            if key.lower() in col.lower():
                return col
    return None

def load_data(uploaded_file):
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # 1. Identify critical columns dynamically
        col_level = find_column(df, ["level", "lvl"])
        col_comp = find_column(df, ["component", "material", "object"])
        col_desc = find_column(df, ["desc", "description", "text"])
        col_type = find_column(df, ["type", "cat", "mat"]) # Material Type
        col_qty = find_column(df, ["qty", "quantity", "amount"])
        col_unit = find_column(df, ["unit", "uom", "bun"])

        if not col_level or not col_comp:
            st.error(f"Could not find 'Level' or 'Component' columns. Found: {list(df.columns)}")
            return None

        # 2. Standardize DataFrame
        clean_df = pd.DataFrame()
        clean_df["Level"] = pd.to_numeric(df[col_level], errors='coerce').fillna(0).astype(int)
        clean_df["Component"] = df[col_comp].astype(str).str.strip()
        
        clean_df["Description"] = df[col_desc] if col_desc else ""
        clean_df["Type"] = df[col_type] if col_type else "DEFAULT"
        clean_df["Unit"] = df[col_unit] if col_unit else ""
        
        # Clean Quantity (handle "1 PC" strings if present)
        if col_qty:
            # Force convert to string, remove non-numeric chars except dot, convert to float
            clean_df["Quantity"] = pd.to_numeric(df[col_qty], errors='coerce').fillna(1.0)
        else:
            clean_df["Quantity"] = 1.0

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
        
        # Add Node
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
        # The parent is the active node at (level - 1)
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
    for k, v in STYLE_MAP.items():
        if k not in ["FERT", "ROH"]: # Dedupe
            st.markdown(f"<span style='color:{v['color']}; font-size:20px'>●</span> {v['label']}", unsafe_allow_html=True)

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    if df is not None:
        # Show Data Preview
        with st.expander("Show Raw Data Table", expanded=False):
            st.dataframe(df)

        # Build Graph
        G = build_network(df)
        
        # Filtering (Optional)
        st.subheader(f"Explosion for: {df.iloc[0]['Component']}")
        search_term = st.text_input("Highlight Component (Type to search)", "")
        
        # PyVis Setup
        net = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
        
        # Apply Search Highlighting
        if search_term:
            for node in G.nodes:
                if search_term.lower() in node.lower():
                    G.nodes[node]['color'] = "#FF0000" # Red for match
                    G.nodes[node]['size'] = 30
        
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

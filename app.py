import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import numpy as np
import io

# ==========================================
# CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="SAP BOM Cockpit", layout="wide", page_icon="🏭")

# SAP Material Type Color Palette
MATERIAL_STYLES = {
    "CURT": {"color": "#1E3A8A", "shape": "box", "label": "Finished Good (CURT)"},      # Deep Blue
    "FERT": {"color": "#1E3A8A", "shape": "box", "label": "Finished Good (FERT)"},
    "GRET": {"color": "#0EA5E9", "shape": "box", "label": "Green Tire (GRET)"},          # Sky Blue
    "ASSM": {"color": "#0D9488", "shape": "diamond", "label": "Assembly (ASSM)"},        # Teal
    "HALB": {"color": "#0D9488", "shape": "diamond", "label": "Semi-Finished (HALB)"},
    "GUM":  {"color": "#D946EF", "shape": "star", "label": "Rubber/Gum (GUM)"},          # Magenta
    "CMPD": {"color": "#9333EA", "shape": "hexagon", "label": "Compound (CMPD)"},        # Purple
    "RAW":  {"color": "#16A34A", "shape": "dot", "label": "Raw Material (RAW)"},         # Green
    "ROH":  {"color": "#16A34A", "shape": "dot", "label": "Raw Material (ROH)"},
    "DEFAULT": {"color": "#9CA3AF", "shape": "ellipse", "label": "Other"}               # Grey
}

# Custom CSS for the dashboard feel
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #1E3A8A;
    }
    .stApp header {visibility: hidden;}
    .block-container {padding-top: 1rem !important;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# LOGIC CLASS
# ==========================================
class SAPBOMProcessor:
    def __init__(self, df):
        self.df = df
        self.G = nx.DiGraph()
        self.root = None
        self._build_graph()

    def _clean_columns(self):
        # Normalize column names for flexibility
        cols = {c: c.lower().strip() for c in self.df.columns}
        self.df.rename(columns=cols, inplace=True)
        
        # Map known variations to standard keys
        standard_map = {}
        for c in self.df.columns:
            if 'component' in c and 'number' in c: standard_map[c] = 'component'
            elif 'level' in c: standard_map[c] = 'level'
            elif 'material' in c and 'type' in c: standard_map[c] = 'type'
            elif 'qty' in c: standard_map[c] = 'qty'
            elif 'unit' in c: standard_map[c] = 'unit'
            elif 'description' in c: standard_map[c] = 'desc'
            elif 'mrp' in c: standard_map[c] = 'mrp'
            elif 'production' in c and 'version' in c: standard_map[c] = 'ver'

        self.df.rename(columns=standard_map, inplace=True)
        
        # Fill missing values
        if 'type' not in self.df.columns: self.df['type'] = 'DEFAULT'
        if 'qty' not in self.df.columns: self.df['qty'] = 1.0
        self.df['level'] = pd.to_numeric(self.df['level'], errors='coerce').fillna(0).astype(int)

    def _build_graph(self):
        self._clean_columns()
        
        stack = {} # Stores {level: node_id}
        
        for _, row in self.df.iterrows():
            level = row['level']
            comp = str(row['component']).strip()
            m_type = str(row.get('type', 'DEFAULT')).strip()
            
            # Store node attributes
            attrs = {
                'type': m_type,
                'desc': str(row.get('desc', '')),
                'unit': str(row.get('unit', '')),
                'mrp': str(row.get('mrp', '-')),
                'ver': str(row.get('ver', '-')),
                'level': level
            }
            self.G.add_node(comp, **attrs)
            
            # Identify Root
            if level == 1:
                self.root = comp
                
            # Track hierarchy
            stack[level] = comp
            
            # Create Edge (Parent -> Child)
            if level > 1:
                parent_level = level - 1
                # Find the nearest parent in the stack
                while parent_level > 0 and parent_level not in stack:
                    parent_level -= 1
                
                if parent_level in stack:
                    parent = stack[parent_level]
                    qty = float(row.get('qty', 1.0))
                    self.G.add_edge(parent, comp, weight=qty, unit=row.get('unit', ''))

    def get_filtered_graph(self, focus_node=None, trace_to_root=False):
        """
        Returns a subgraph.
        If trace_to_root is True: Returns the path from focus_node UP to the root.
        If trace_to_root is False: Returns the subtree starting DOWN from focus_node.
        """
        if not focus_node or focus_node == "All":
            return self.G

        if trace_to_root:
            # Upstream Trace
            ancestors = nx.ancestors(self.G, focus_node)
            ancestors.add(focus_node)
            return self.G.subgraph(ancestors)
        else:
            # Downstream Explosion
            descendants = nx.descendants(self.G, focus_node)
            descendants.add(focus_node)
            return self.G.subgraph(descendants)

# ==========================================
# UI COMPONENTS
# ==========================================
def render_legend():
    """Renders a visual legend in the Sidebar"""
    st.sidebar.markdown("### 🎨 Material Legend")
    legend_html = ""
    for k, v in MATERIAL_STYLES.items():
        if k in ["FERT", "HALB", "ROH"]: continue # Skip duplicate standard keys for cleanliness
        legend_html += f"""
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="width: 15px; height: 15px; background-color: {v['color']}; 
                        border-radius: {'50%' if v['shape']=='dot' else '2px'}; margin-right: 10px;"></div>
            <span style="font-size: 12px;">{v['label']}</span>
        </div>
        """
    st.sidebar.markdown(legend_html, unsafe_allow_html=True)

def render_details_panel(graph, selected_node):
    """Side panel for deep dive details"""
    if selected_node and selected_node in graph.nodes:
        data = graph.nodes[selected_node]
        st.sidebar.markdown("---")
        st.sidebar.subheader(f"📦 {selected_node}")
        
        st.sidebar.markdown(f"**Desc:** {data.get('desc', 'N/A')}")
        
        c1, c2 = st.sidebar.columns(2)
        c1.metric("Type", data.get('type', 'N/A'))
        c2.metric("Level", data.get('level', 'N/A'))
        
        c3, c4 = st.sidebar.columns(2)
        c3.markdown(f"**MRP Type:** `{data.get('mrp', '-')}`")
        c4.markdown(f"**Prod Ver:** `{data.get('ver', '-')}`")
        
        # Calculate usage info
        in_degree = graph.in_degree(selected_node)
        out_degree = graph.out_degree(selected_node)
        st.sidebar.info(f"Used in {in_degree} places | Has {out_degree} components")

# ==========================================
# MAIN APP
# ==========================================
st.title("🏭 SAP BOM Planner Cockpit")

# 1. UPLOAD
uploaded_file = st.sidebar.file_uploader("Upload SAP BOM (CSV/Excel)", type=["csv", "xlsx"])

if uploaded_file:
    # Load Data
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        processor = SAPBOMProcessor(df)
        st.sidebar.success(f"Loaded {len(processor.G.nodes)} materials")
        render_legend()
        
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        st.stop()

    # 2. CONTROLS
    col_search, col_layout = st.columns([3, 1])
    
    with col_search:
        all_nodes = ["All"] + sorted(list(processor.G.nodes))
        focus_node = st.selectbox("🔍 Trace Component (Search SKU)", all_nodes, index=0)
        
        if focus_node != "All":
            trace_mode = st.radio("View Mode", ["Explosion (Downstream)", "Traceability (Upstream to Finished Good)"], horizontal=True)
            is_trace_root = True if "Upstream" in trace_mode else False
        else:
            is_trace_root = False

    with col_layout:
        st.write(" ") # spacer
        show_physics = st.checkbox("Enable Physics", value=False, help="Turn on for fun, off for structure")

    # 3. GRAPH PROCESSING
    sub_G = processor.get_filtered_graph(focus_node, is_trace_root)
    
    # 4. PYVIS VISUALIZATION
    net = Network(height="700px", width="100%", directed=True, bgcolor="#ffffff", font_color="black")
    
    # Add Nodes with Styles
    for node in sub_G.nodes:
        attrs = processor.G.nodes[node]
        m_type = attrs.get('type', 'DEFAULT')
        
        # Fallback for unknown types
        style = MATERIAL_STYLES.get(m_type, MATERIAL_STYLES["DEFAULT"])
        
        # Tooltip generation
        tooltip = f"""
        <b>{node}</b><br>
        Type: {m_type}<br>
        Desc: {attrs.get('desc')}<br>
        Level: {attrs.get('level')}
        """
        
        net.add_node(
            node,
            label=node,
            title=tooltip,
            color=style['color'],
            shape=style['shape'],
            size=25 if m_type in ['CURT', 'FERT'] else 15,
            level=attrs.get('level') # Important for hierarchical layout
        )

    # Add Edges with variable thickness (Mass Flow)
    for u, v, data in sub_G.edges(data=True):
        weight = data.get('weight', 1.0)
        # Logarithmic scaling for width so small screws don't disappear and big tires don't cover screen
        width = 1 + np.log1p(weight) * 2 
        
        net.add_edge(
            u, v,
            title=f"Qty: {weight} {data.get('unit', '')}",
            width=width,
            color="#CBD5E1" # Light slate grey for edges
        )

    # 5. LAYOUT ENGINE (The Secret Sauce)
    # Using Hierarchical Repulsion creates the "Lane" view planners love
    net.set_options(f"""
    {{
      "layout": {{
        "hierarchical": {{
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "levelSeparation": 250,
          "nodeSpacing": 150
        }}
      }},
      "physics": {{
        "enabled": {str(show_physics).lower()},
        "hierarchicalRepulsion": {{
          "centralGravity": 0.0,
          "springLength": 100,
          "springConstant": 0.01,
          "nodeDistance": 120,
          "damping": 0.09
        }}
      }},
      "interaction": {{
        "navigationButtons": true,
        "keyboard": true
      }}
    }}
    """)

    # 6. RENDER
    # Trick to handle PyVis in Streamlit efficiently
    path = "/tmp"
    net.save_graph(f"{path}/bom_graph.html")
    HtmlFile = open(f"{path}/bom_graph.html", 'r', encoding='utf-8')
    source_code = HtmlFile.read() 
    components.html(source_code, height=710, scrolling=False)

    # 7. DETAILS PANEL (Rendered after graph selection context)
    render_details_panel(processor.G, focus_node)

    # 8. DATA TABLE TAB
    with st.expander("📊 View Underlying Data"):
        st.dataframe(df)

else:
    st.info("👋 Upload a standard SAP BOM export to begin planning.")
    st.markdown("""
    **Required Columns (Flexible naming):**
    - `Level` (1, 2, 3...)
    - `Component` (Material Number)
    - `Material Type` (FERT, HALB, ROH, CMPD...)
    - `Quantity`
    """)

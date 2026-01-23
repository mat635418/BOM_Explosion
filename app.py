import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components

from BOM_Explosion import BOMExplosionApp

st.set_page_config(page_title="BOM Explosion", layout="wide")

# Keep a single global app instance
if "bom_app" not in st.session_state:
    st.session_state["bom_app"] = BOMExplosionApp()

app = st.session_state["bom_app"]

st.title("BOM Explosion Tool - v.0.05")

st.markdown(
    """
    Upload a BOM file (single SKU for now) with at least these columns:

    - `Level`
    - `Component number`
    - quantity column like `Comp. Qty (BUn)` (optional, but recommended)
    """
)

# --- Upload box ---
uploaded_file = st.file_uploader(
    "Upload BOM file",
    type=["csv", "xlsx"],
    help="Upload a BOM for one SKU. Supported formats: CSV, Excel."
)

df = None

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        app.load_from_dataframe(df)
        st.success("BOM data loaded successfully!")

    except Exception as e:
        st.error(f"Error while reading or parsing the file: {e}")

# --- Tabs: Data / Topology ---
tab_data, tab_topology = st.tabs(["Data", "Topology"])

with tab_data:
    st.subheader("Raw BOM data")
    if app.has_data():
        st.dataframe(app.get_dataframe())
    else:
        st.info("Upload a BOM file to view data.")

with tab_topology:
    st.subheader("Topology")
    if app.has_topology():
        topology = app.get_topology()

        # --- Show nodes / edges as text ---
        with st.expander("Nodes and edges (raw)", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Nodes (all unique parts)**")
                st.write(topology.nodes)
            with col2:
                st.markdown("**Edges (Parent → Child relationships)**")
                st.write(topology.edges)

        # --- Build NetworkX graph ---
        G = nx.DiGraph()
        for node in topology.nodes:
            G.add_node(node, label=node)

        for edge in topology.edges:
            parent = edge["from"]
            child = edge["to"]
            qty = edge.get("quantity", 1)
            G.add_edge(parent, child, quantity=qty)

        # --- Render with PyVis ---
        net = Network(height="700px", width="100%", directed=True)
        net.from_nx(G)

        # Optionally tune physics / layout a bit
        net.toggle_physics(True)
        net.show_buttons(filter_=["physics"])

        # Generate and display HTML
        html_file = "bom_topology.html"
        net.save_graph(html_file)

        # Read the HTML and embed it
        with open(html_file, "r", encoding="utf-8") as f:
            html = f.read()

        st.subheader("Graph view")
        components.html(html, height=750, scrolling=True)

    else:
        st.info("Upload a BOM file to see the topology.")

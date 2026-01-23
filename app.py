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

st.title("BOM Explosion Tool - v0.05")

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

        # --- Parameters / controls above the graph ---
        with st.expander("Graph parameters", expanded=True):
            col_p1, col_p2, col_p3 = st.columns([1, 1, 1])

            with col_p1:
                physics_enabled = st.checkbox(
                    "Enable physics layout",
                    value=True,
                    help=(
                        "When enabled, nodes move under simulated forces to reach a readable layout. "
                        "Turn it off for a static layout once you are happy with the positions."
                    ),
                )

            with col_p2:
                height_px = st.slider(
                    "Graph height (px)",
                    min_value=600,
                    max_value=1500,
                    value=1200,  # was ~700–750; now extended by ~500px
                    step=50,
                    help=(
                        "Increase the height to see more of the network at once. "
                        "Useful for large BOMs with many levels."
                    ),
                )

            with col_p3:
                show_raw_data = st.checkbox(
                    "Show raw nodes/edges table",
                    value=False,
                    help=(
                        "When checked, displays the underlying lists of nodes and edges below. "
                        "Useful for debugging or exporting."
                    ),
                )

        # --- Optional: raw nodes / edges ---
        if show_raw_data:
            with st.expander("Nodes and edges (raw data)", expanded=False):
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
            # Use quantity as edge label
            G.add_edge(parent, child, quantity=qty, title=f"Qty: {qty}")

        # --- Render with PyVis ---
        net = Network(height=f"{height_px}px", width="100%", directed=True)

        # Optional: basic styling / better default appearance
        net.barnes_hut()
        net.from_nx(G)

        # Physics on/off from the checkbox
        net.toggle_physics(physics_enabled)

        # Optionally expose some buttons (layout/physics)
        net.show_buttons(filter_=["physics"])

        html_file = "bom_topology.html"
        net.save_graph(html_file)

        with open(html_file, "r", encoding="utf-8") as f:
            html = f.read()

        st.subheader("Graph view")
        components.html(html, height=height_px + 50, scrolling=True)

    else:
        st.info("Upload a BOM file to see the topology.")

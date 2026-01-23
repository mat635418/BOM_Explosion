import streamlit as st
import pandas as pd

from BOM_Explosion import BOMExplosionApp

st.set_page_config(page_title="BOM Explosion", layout="wide")

# Keep a single global app instance
if "bom_app" not in st.session_state:
    st.session_state["bom_app"] = BOMExplosionApp()

app = st.session_state["bom_app"]

st.title("BOM Explosion Tool")

st.markdown(
    """
    Upload a BOM file (single SKU for now) with at least these columns:

    - `Parent`
    - `Child`
    - optional: `Quantity`
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

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Nodes (all unique parts)**")
            st.write(topology.nodes)

        with col2:
            st.markdown("**Edges (Parent → Child relationships)**")
            st.write(topology.edges)

        # Placeholder for future graph visualization
        st.markdown("_(Graph visualization coming next – for now this shows the topology data.)_")

    else:
        st.info("Upload a BOM file to see the topology.")

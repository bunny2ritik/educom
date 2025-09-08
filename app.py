import streamlit as st
from log_generator import parse_and_generate_excel, extract_summary_tables_from_stream
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Eduroam Dashboard", layout="wide")
st.title("📡 Eduroam Log Dashboard")

uploaded_file = st.file_uploader("📂 Upload your `sampleData.txt` log file", type=["txt"])

if uploaded_file:
    with st.spinner("⏳ Parsing large log file... please wait"):
        df_access, df_fticks = extract_summary_tables_from_stream(uploaded_file)

    def extract_domain(email):
        if pd.notnull(email) and '@' in email:
            return email.split('@')[1].strip().lower()
        return None

    df_access["Domain"] = df_access["Username"].apply(extract_domain)

    # Sidebar Filters for Access Logs
    st.sidebar.header("🔍 Filter Access Logs")
    access_df_filtered = df_access.copy()

    min_date = df_access["Timestamp"].min()
    max_date = df_access["Timestamp"].max()
    date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])

    if len(date_range) == 2:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        access_df_filtered = access_df_filtered[
            (access_df_filtered["Timestamp"] >= start_date) & (access_df_filtered["Timestamp"] <= end_date)
        ]

    selected_events = st.sidebar.multiselect(
        "Access Event Types", access_df_filtered["Event"].dropna().unique(),
        default=access_df_filtered["Event"].dropna().unique()
    )
    access_df_filtered = access_df_filtered[access_df_filtered["Event"].isin(selected_events)]

    selected_domains = st.sidebar.multiselect("Filter by Domain", sorted(access_df_filtered["Domain"].dropna().unique()))
    if selected_domains:
        access_df_filtered = access_df_filtered[access_df_filtered["Domain"].isin(selected_domains)]

    selected_station_ids = st.sidebar.multiselect("Filter by Station ID", sorted(access_df_filtered["StationID"].dropna().unique()))
    if selected_station_ids:
        access_df_filtered = access_df_filtered[access_df_filtered["StationID"].isin(selected_station_ids)]

    access_df_filtered = access_df_filtered.sort_values(by="Timestamp", ascending=False)

    st.subheader("🔐 Access Logs")
    st.dataframe(access_df_filtered.drop(columns=["Domain"]).reset_index(drop=True), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Event Types")
        st.bar_chart(access_df_filtered["Event"].value_counts())

    with col2:
        st.markdown("#### Top Domains")
        st.bar_chart(access_df_filtered["Domain"].value_counts().head(5))

    st.markdown("#### 🍩 Top 10 Domains")
    top_domains = access_df_filtered["Domain"].value_counts().head(10).reset_index()
    top_domains.columns = ["Domain", "Count"]
    fig = px.pie(top_domains, names="Domain", values="Count", title="Top 10 Domains")
    st.plotly_chart(fig, use_container_width=True)

    # --- F-TICKS FILTERS ---
    st.sidebar.header("🔍 Filter F-TICKS Logs")
    fticks_df_filtered = df_fticks.copy()

    selected_results = st.sidebar.multiselect(
        "Authentication Result", fticks_df_filtered["RESULT"].dropna().unique(),
        default=fticks_df_filtered["RESULT"].dropna().unique()
    )
    fticks_df_filtered = fticks_df_filtered[fticks_df_filtered["RESULT"].isin(selected_results)]

    selected_visinst = st.sidebar.multiselect("VISINST (Institution)", fticks_df_filtered["VISINST"].dropna().unique())
    if selected_visinst:
        fticks_df_filtered = fticks_df_filtered[fticks_df_filtered["VISINST"].isin(selected_visinst)]

    selected_country = st.sidebar.multiselect("VISCOUNTRY", fticks_df_filtered["VISCOUNTRY"].dropna().unique())
    if selected_country:
        fticks_df_filtered = fticks_df_filtered[fticks_df_filtered["VISCOUNTRY"].isin(selected_country)]

    selected_csi = st.sidebar.multiselect("CSI (Session IDs)", fticks_df_filtered["CSI"].dropna().unique())
    if selected_csi:
        fticks_df_filtered = fticks_df_filtered[fticks_df_filtered["CSI"].isin(selected_csi)]

    fticks_df_filtered = fticks_df_filtered.sort_values(by="Timestamp", ascending=False)

    st.markdown("---")
    st.subheader("🔵 F-TICKS Overview")
    st.dataframe(fticks_df_filtered.reset_index(drop=True), use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("#### Auth Result Distribution")
        st.bar_chart(fticks_df_filtered["RESULT"].value_counts())

    with col4:
        st.markdown("#### Top VISINST")
        st.bar_chart(fticks_df_filtered["VISINST"].value_counts().head(5))

    # === EXPORT SECTION ===
    st.markdown("---")
    st.subheader("📤 Export Reports")

    col5, col6 = st.columns(2)
    with col5:
        csv_access = access_df_filtered.drop(columns=["Domain"]).to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Access Logs (CSV)", data=csv_access, file_name="access_filtered.csv", mime="text/csv")

    with col6:
        csv_fticks = fticks_df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download F-TICKS Logs (CSV)", data=csv_fticks, file_name="fticks_filtered.csv", mime="text/csv")

    if st.button("Generate Excel Report with Charts"):
        with st.spinner("📊 Generating Excel..."):
            uploaded_file.seek(0)
            raw_text = uploaded_file.read().decode("utf-8", errors="ignore")
            excel_file = parse_and_generate_excel(raw_text)
            st.download_button("⬇️ Download Eduroam Excel File",
                               data=excel_file,
                               file_name="Eduroam_Log_Analyzer.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("Upload a `.txt` log file to start.")
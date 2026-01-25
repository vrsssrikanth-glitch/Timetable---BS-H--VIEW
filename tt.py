import streamlit as st
import pandas as pd
import os

# ===============================
# CONFIG
# ===============================
st.set_page_config(layout="wide")
AUTOSAVE_PATH = "autosave.csv"

DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
PERIODS = [1,2,3,4,5,6,7]

BI_LABS = [
    {"EC LAB","EP LAB"},
    {"EP LAB","NAS LAB"}
]

EXCLUDE_THEORY_ROOM = {"ITWS","EWS","EGP"}

# ===============================
# LOAD DATA (READ ONLY)
# ===============================
if not os.path.exists(AUTOSAVE_PATH):
    st.error("❌ autosave.csv not found")
    st.stop()

df = pd.read_csv(AUTOSAVE_PATH)

# Safety: normalize
for c in df.columns:
    if df[c].dtype == object:
        df[c] = df[c].astype(str).str.strip().str.upper()

# ===============================
# LOOKUPS (OPTIONAL)
# ===============================
faculty = pd.read_csv("Faculty.csv")
faculty["Faculty_ID"] = faculty["Faculty_ID"].str.upper()
faculty["Faculty_Name"] = faculty["Faculty_Name"].str.upper()

FAC_NAME = dict(zip(faculty["Faculty_ID"], faculty["Faculty_Name"]))

# ===============================
# UI HEADER
# ===============================
st.title("📘 Timetable Viewer – READ ONLY")
st.info(
    "🔒 View-only mode. Timetable entries cannot be added, edited, or deleted."
)

# ===============================
# HELPERS
# ===============================
def standard_grid(data, mode="class"):
    cols = [f"P{p}" for p in PERIODS]
    g = pd.DataFrame("", index=DAYS, columns=cols)

    for _, r in data.iterrows():
        cell = ""
        if mode == "class":
            cell = (
                f'{r["Subject"]}\n'
                f'{r["Faculty"]}\n'
                f'{r["Room"]}'
            )
        elif mode == "faculty":
            cell = (
                f'{r["Class"]}\n'
                f'{r["Subject"]}\n'
                f'{r["Room"]}'
            )
        elif mode == "lab":
            cell = (
                f'{r["Class"]}\n'
                f'{r["Faculty"]}'
            )
        elif mode == "room":
            cell = (
                f'{r["Class"]}\n'
                f'{r["Subject"]}\n'
                f'{r["Faculty"]}'
            )

        g.loc[r["Day"], f'P{r["Period"]}'] = cell

    return g

# ===============================
# TABS
# ===============================
tab1, tab2, tab3, tab4 = st.tabs(
    ["📘 Class View", "👨‍🏫 Faculty View", "🧪 Lab View", "🏫 Room View"]
)

# -------------------------------
# CLASS VIEW
# -------------------------------
with tab1:
    cls = st.selectbox("Select Class", sorted(df["Class"].unique()))
    cdf = df[df["Class"] == cls]

    st.dataframe(
        grid(
            cdf,
            lambda r: (
                f'{r["Subject"]} | {FAC_NAME.get(r["Faculty"], r["Faculty"])}'
            )
        ),
        use_container_width=True,
        hide_index=True
    )

# -------------------------------
# FACULTY VIEW
# -------------------------------
with tab2:
    fname = st.selectbox(
        "Select Faculty",
        sorted(faculty["Faculty_Name"].unique())
    )
    fid = faculty.loc[
        faculty["Faculty_Name"] == fname, "Faculty_ID"
    ].iloc[0]

    fdf = df[df["Faculty"] == fid]

    st.dataframe(
        grid(
            fdf,
            lambda r: f'{r["Class"]} | {r["Subject"]}'
        ),
        use_container_width=True,
        hide_index=True
    )

# -------------------------------
# LAB VIEW
# -------------------------------
with tab3:
    labs = sorted(
        set(
            s for s in df["Subject"].unique()
            if s.endswith("LAB")
        )
    )

    lab = st.selectbox("Select Lab", labs)

    related = [lab]
    for pair in BI_LABS:
        if lab in pair:
            related.extend(pair)

    ldf = df[df["Subject"].isin(set(related))]

    st.dataframe(
        grid(
            ldf,
            lambda r: f'{r["Class"]} | {FAC_NAME.get(r["Faculty"], r["Faculty"])}'
        ),
        use_container_width=True,
        hide_index=True
    )

# -------------------------------
# ROOM VIEW
# -------------------------------
with tab4:
    room = st.selectbox("Select Room", sorted(df["Room"].dropna().unique()))
    rdf = df[df["Room"] == room]

    st.dataframe(
        grid(
            rdf,
            lambda r: f'{r["Class"]} | {r["Subject"]}'
        ),
        use_container_width=True,
        hide_index=True
    )

# ===============================
# DOWNLOAD
# ===============================
st.divider()

if st.button("⬇️ Download Timetable (Excel)"):
    with pd.ExcelWriter("Timetable.xlsx", engine="openpyxl") as w:
        df.to_excel(w, "RAW", index=False)

    st.success("✅ Timetable.xlsx downloaded")


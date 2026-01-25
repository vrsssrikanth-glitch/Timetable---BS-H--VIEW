import streamlit as st
import pandas as pd

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(layout="wide")
AUTOSAVE_PATH = "autosave.csv"

DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
PERIODS = [1,2,3,4,5,6,7]

# ONLY ALLOWED CONTINUOUS ROOM BLOCKS
CONTINUOUS_SLOTS = {
    (1, 2),
    (3, 4),
    (1, 4),
    (5, 7)
}

# PHYSICAL ROOMS ONLY
PHYSICAL_ROOMS = [
    "A41","A42","A45","A48",
    "B43","B44","B46","B47",
    "B52","B55","B56","B57"
]

BI_LABS = [
    {"EC LAB","EP LAB"},
    {"EP LAB","NAS LAB"}
]

# ==================================================
# LOAD DATA (READ ONLY)
# ==================================================
df = pd.read_csv(AUTOSAVE_PATH)
faculty = pd.read_csv("Faculty.csv")
labs_df = pd.read_csv("labs.csv")

# Normalize text
for d in [df, faculty, labs_df]:
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].astype(str).str.strip().str.upper()

FAC_NAME = dict(zip(faculty["Faculty_ID"], faculty["Faculty_Name"]))

# ==================================================
# AUTO-FILL PHYSICAL ROOMS (CONTINUOUS BLOCKS ONLY)
# VIEW ONLY – NO SAVE
# ==================================================
df = df.copy()

def room_free(df, room, day, periods):
    return not any(
        (df["Room"] == room) &
        (df["Day"] == day) &
        (df["Period"].isin(periods))
    )

# process subject blocks per class/day
for (cls, sub, day), g in df.groupby(["Class", "Subject", "Day"]):

    if str(sub).endswith("LAB"):
        continue

    periods = sorted(g["Period"].tolist())
    if not periods:
        continue

    start, end = periods[0], periods[-1]

    # only allowed continuous blocks
    if (start, end) not in CONTINUOUS_SLOTS:
        continue

    # already has room → skip
    if g["Room"].notna().all() and not (g["Room"] == "").any():
        continue

    # assign one free physical room
    for room in PHYSICAL_ROOMS:
        if room_free(df, room, day, periods):
            df.loc[g.index, "Room"] = room
            break

# ==================================================
# GRID HELPER (FORMAT UNCHANGED)
# ==================================================
def grid(data, label):
    g = pd.DataFrame("", index=DAYS, columns=PERIODS)
    for _, r in data.iterrows():
        g.loc[r["Day"], r["Period"]] = label(r)
    return g

# ==================================================
# UI
# ==================================================
st.title("📘 Timetable Viewer – VIEW ONLY")
st.info(
    "🔒 View-only mode. "
    "Rooms are auto-allocated only in continuous slots "
    "(1–2, 3–4, 1–4, 5–7) using available physical rooms."
)

tab1, tab2, tab3, tab4 = st.tabs(
    ["📘 Class View", "👨‍🏫 Faculty View", "🧪 Lab View", "🏫 Room View"]
)

# --------------------------------------------------
# CLASS VIEW
# --------------------------------------------------
with tab1:
    cls = st.selectbox("Class", sorted(df["Class"].unique()))
    cdf = df[df["Class"] == cls]

    st.dataframe(
        grid(
            cdf,
            lambda r: (
                f'{r["Subject"]} | CLASS COORDINATOR'
                if r["Faculty"] == "WEEKLY_TEST_FACULTY"
                else f'{r["Subject"]} | {FAC_NAME.get(r["Faculty"], r["Faculty"])}'
            )
        ),
        use_container_width=True
    )

# --------------------------------------------------
# FACULTY VIEW
# --------------------------------------------------
with tab2:
    fname = st.selectbox("Faculty", sorted(FAC_NAME.values()))
    fid = [k for k, v in FAC_NAME.items() if v == fname][0]
    fdf = df[df["Faculty"] == fid]

    st.dataframe(
        grid(
            fdf,
            lambda r: f'{r["Class"]} | {r["Subject"]}'
        ),
        use_container_width=True
    )

# --------------------------------------------------
# LAB VIEW
# --------------------------------------------------
with tab3:
    lab = st.selectbox("Lab", sorted(labs_df["Lab_Subject"].unique()))

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
        use_container_width=True
    )

# --------------------------------------------------
# ROOM VIEW (PHYSICAL ROOMS ONLY)
# --------------------------------------------------
with tab4:
    room = st.selectbox("Room", sorted(df["Room"].dropna().unique()))
    rdf = df[df["Room"] == room]

    st.dataframe(
        grid(
            rdf,
            lambda r: f'{r["Class"]} | {r["Subject"]} | {FAC_NAME.get(r["Faculty"], r["Faculty"])}'
        ),
        use_container_width=True
    )

# ==================================================
# ROOM UTILIZATION REPORT
# ==================================================
st.divider()
st.subheader("🏫 Room Utilization Report")

TOTAL_SLOTS = len(DAYS) * len(PERIODS)

util = (
    df.dropna(subset=["Room"])
      .groupby("Room")
      .agg(
          Used_Slots=("Room", "count"),
          Classes=("Class", lambda x: ", ".join(sorted(set(x))))
      )
      .reset_index()
)

util["Total_Slots"] = TOTAL_SLOTS
util["Utilization_%"] = (util["Used_Slots"] / TOTAL_SLOTS * 100).round(2)

st.dataframe(
    util.sort_values("Utilization_%", ascending=False),
    use_container_width=True
)

# ==================================================
# DOWNLOAD
# ==================================================
st.divider()

if st.button("⬇️ Download Excel"):
    with pd.ExcelWriter("Timetable.xlsx", engine="openpyxl") as w:
        df.to_excel(w, sheet_name="RAW", index=False)
    st.success("Timetable.xlsx downloaded")

import streamlit as st
import pandas as pd

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(layout="wide")
AUTOSAVE_PATH = "autosave.csv"

df = pd.read_csv("autosave.csv")

# -------------------------------
# DAY NORMALIZATION (CRITICAL FIX)
# -------------------------------
DAY_CANON = {
    "MON": "Monday", "MONDAY": "Monday",
    "TUE": "Tuesday", "TUESDAY": "Tuesday",
    "WED": "Wednesday", "WEDNESDAY": "Wednesday",
    "THU": "Thursday", "THURSDAY": "Thursday",
    "FRI": "Friday", "FRIDAY": "Friday",
    "SAT": "Saturday", "SATURDAY": "Saturday"
}

df["Day"] = (
    df["Day"]
    .astype(str)
    .str.strip()
    .str.upper()
    .map(DAY_CANON)
)

DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
PERIODS = [1,2,3,4,5,6,7]

CONTINUOUS_SLOTS = {
    (1, 2),
    (3, 4),
    (1, 4),
    (5, 7)
}

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
# LOAD DATA
# ==================================================
df = pd.read_csv(AUTOSAVE_PATH)
faculty = pd.read_csv("Faculty.csv")
labs_df = pd.read_csv("labs.csv")

for d in [df, faculty, labs_df]:
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].astype(str).str.strip().str.upper()

FAC_NAME = dict(zip(faculty["Faculty_ID"], faculty["Faculty_Name"]))

# ==================================================
# AUTO-FILL PHYSICAL ROOMS (INTERNAL USE)
# ==================================================
df = df.copy()

def room_free(df, room, day, periods):
    return not any(
        (df["Room"] == room) &
        (df["Day"] == day) &
        (df["Period"].isin(periods))
    )

for (cls, sub, day), g in df.groupby(["Class", "Subject", "Day"]):
    if sub.endswith("LAB"):
        continue

    periods = sorted(g["Period"].tolist())
    if not periods:
        continue

    block = (periods[0], periods[-1])
    if block not in CONTINUOUS_SLOTS:
        continue

    if g["Room"].notna().all() and not (g["Room"] == "").any():
        continue

    for room in PHYSICAL_ROOMS:
        if room_free(df, room, day, periods):
            df.loc[g.index, "Room"] = room
            break

# ==================================================
# GRID FORMATTER (NO NONE, CLEAN CELLS)
# ==================================================
def grid(df, label):
    g = pd.DataFrame("", index=DAYS, columns=PERIODS)

    # block invalid / rogue day values
    df = df[df["Day"].isin(DAYS)]

    for _, r in df.iterrows():
        g.loc[r["Day"], r["Period"]] = label(r)

    return g

# ==================================================
# UI
# ==================================================
st.title("📘 Timetable Viewer (View-Only)")
st.caption(
    "Clean academic views | No editing | "
    "Unassigned classes are internally mapped to available rooms"
)

tab1, tab2, tab3 = st.tabs(
    ["📘 Class View", "👨‍🏫 Faculty View", "🧪 Lab View"]
)

# --------------------------------------------------
# CLASS VIEW
# --------------------------------------------------
with tab1:
    cls = st.selectbox("Select Class", sorted(df["Class"].unique()))
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
    fname = st.selectbox("Select Faculty", sorted(FAC_NAME.values()))
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
    lab = st.selectbox("Select Lab", sorted(labs_df["Lab_Subject"].unique()))

    related = {lab}
    for pair in BI_LABS:
        if lab in pair:
            related |= pair

    ldf = df[df["Subject"].isin(related)]

    st.dataframe(
        grid(
            ldf,
            lambda r: f'{r["Class"]} | {FAC_NAME.get(r["Faculty"], r["Faculty"])}'
        ),
        use_container_width=True
    )



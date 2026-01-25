import streamlit as st
import pandas as pd
import os
AUTOSAVE_PATH = "autosave.csv"

st.set_page_config(layout="wide")

# ==================================================
# CONSTANTS
# ==================================================
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
PERIODS = [1,2,3,4,5,6,7]

DAY_MAP = {
    "MON": "Monday",
    "TUE": "Tuesday",
    "WED": "Wednesday",
    "THU": "Thursday",
    "FRI": "Friday",
    "SAT": "Saturday"
}

TWO_PERIOD_SUBS = {"EWS","ITWS","EGT","NSS","HWYS"}
EXCLUDE_THEORY_ROOM = {"ITWS","EWS","EGP"}

# BI-LAB PAIRS (FACULTY MAY BE DIFFERENT)
BI_LABS = [
    {"EC LAB","EP LAB"},
    {"EP LAB","NAS LAB"}
]

CONTINUOUS_SLOTS = {(1,2),(3,4),(1,4),(5,7)}

WEEKLY_TEST_FACULTY = "CLASS COORDINATOR"

# ==================================================
# HELPERS
# ==================================================
def clean(x):
    if pd.isna(x): return "NA"
    return str(x).strip().upper()

def autosave():
    df = pd.DataFrame(st.session_state.TT)
    df.to_csv(AUTOSAVE_PATH, index=False)
    
def subject_progress(cls, sub):
    used = sum(
        1 for r in st.session_state.TT
        if r["Class"] == cls and r["Subject"] == sub
    )
    total = SUB_MAX_HOURS.get((cls, sub), 0)
    return f"{used}/{total}"

def pending_load_row(cls):
    subs = teaching[teaching["Class_ID"] == cls]["Subject_ID"].unique()
    parts = []

    for s in subs:
        used = sum(
            1 for r in st.session_state.TT
            if r["Class"] == cls and r["Subject"] == s
        )
        total = SUB_MAX_HOURS.get((cls, s), 0)

        if used < total:  # ✅ ONLY PENDING
            parts.append(f"{s}: {used}/{total}")

    return " | ".join(parts)
def library_overflow(day, period):
    used = {
        r["Class"]
        for r in st.session_state.TT
        if r.get("Room") == "LIBRARY"
        and r["Day"] == day
        and r["Period"] == period
    }
    return len(used) > 3


# ==================================================
# LOAD CSVs
# ==================================================
faculty = pd.read_csv("Faculty.csv")
subjects = pd.read_csv("subjects.csv")
classes_df = pd.read_csv("classes.csv")
teaching = pd.read_csv("teaching_load.csv")
fac_avail = pd.read_csv("Faculty_Availability.csv")
labs_df = pd.read_csv("labs.csv")
rooms_df = pd.read_csv("rooms.csv")

for df in [faculty, subjects, classes_df, teaching, fac_avail, labs_df, rooms_df]:
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].apply(clean)

# ==================================================
# LOOKUPS
# ==================================================
FAC_NAME = dict(zip(faculty["Faculty_ID"], faculty["Faculty_Name"]))
SUB_FAC = {(r.Class_ID, r.Subject_ID): r.Faculty_ID for _, r in teaching.iterrows()}
SUB_MAX_HOURS = {(r.Class_ID, r.Subject_ID): int(r.Hours) for _, r in teaching.iterrows()}

FAC_BLOCKED = {
    (
        r.Faculty_ID,
        DAY_MAP.get(r.Day.upper(), r.Day),
        int(r.Period)
    )
    for _, r in fac_avail.iterrows()
}

LAB_ROOMS = dict(zip(labs_df["Lab_Subject"], labs_df["Room"]))

ROOM_COL = [c for c in rooms_df.columns if c.upper().startswith("ROOM")][0]
ALL_ROOMS = rooms_df[ROOM_COL].dropna().astype(str).str.upper().unique().tolist()
PRIMARY_ROOMS = ALL_ROOMS[:14]

CLASSES = sorted(classes_df["Class_ID"].unique())
LOCKED_CLASSES = CLASSES[:14]
FLEX_CLASSES = CLASSES[14:]

# ==================================================
# SESSION STATE
# ==================================================
if "TT" not in st.session_state:
    if os.path.exists("autosave.csv"):
        st.session_state.TT = pd.read_csv("autosave.csv").to_dict("records")
    else:
        st.session_state.TT = []

 # 🔒 AUTO-ADD WEEKLY TEST (MONDAY P1)
    for cls in CLASSES:
        st.session_state.TT.append({
            "Class": cls,
            "Subject": "WEEKLY TEST",
            "Faculty": "WEEKLY_TEST_FACULTY",
            "Day": "Monday",
            "Period": 1,
            "Room": ""
        })

if "CLASS_ROOM_LOCK" not in st.session_state:
    st.session_state.CLASS_ROOM_LOCK = {}

# ==================================================
# CORE CHECKS
# ==================================================
def busy(key, val, day, p):
    return any(
        r[key] == val and r["Day"] == day and r["Period"] == p
        for r in st.session_state.TT
    )

def is_bi_lab_pair(sub1, sub2):
    return any({sub1, sub2} == b for b in BI_LABS)

def room_clash(day, start, dur, room):
    return any(
        r["Room"] == room and r["Day"] == day and r["Period"] in range(start, start + dur)
        for r in st.session_state.TT
    )

def is_continuous(start, dur):
    return (start, start + dur - 1) in CONTINUOUS_SLOTS

# ==================================================
# THEORY ROOM ASSIGNMENT
# ==================================================
def get_theory_room(cls, day, start, dur):
    if cls in LOCKED_CLASSES:
        return PRIMARY_ROOMS[LOCKED_CLASSES.index(cls)]

    if not is_continuous(start, dur):
        return None

    for r in PRIMARY_ROOMS:
        if not room_clash(day, start, dur, r):
            return r
    return None

# ==================================================
# THEORY ROOM ALLOCATION (LOCK + AUTOFIT POLICY)
# ==================================================
def get_theory_room(cls, day, start, dur):
    # 1️⃣ Explicit lock from Room View
    if "CLASS_ROOM_LOCK" in st.session_state and cls in st.session_state.CLASS_ROOM_LOCK:
        return st.session_state.CLASS_ROOM_LOCK[cls]

    # 2️⃣ Default locked classes (first 14)
    if cls in LOCKED_CLASSES:
        return PRIMARY_ROOMS[LOCKED_CLASSES.index(cls)]

    # 3️⃣ Excess classes → conditional autofill
    if (start, start + dur - 1) not in CONTINUOUS_SLOTS:
        return None

    for r in PRIMARY_ROOMS:
        if not room_clash(day, start, dur, r):
            return r

    return None

# ==================================================
# ADD ENTRY (HUMAN CONTROLLED)
# ==================================================
def add_entry(cls, sub, day, start):
    fac = SUB_FAC.get((cls, sub), "NA")

    dur = 3 if sub.endswith("LAB") else 2 if sub in TWO_PERIOD_SUBS else 1
    if start + dur - 1 > 7:
       return "Invalid period span"

    # ---------- ROOM ----------
    if sub.endswith("LAB"):
        room = LAB_ROOMS.get(sub)
        if not room:
            return f"No room mapped for {sub}"
        if room_clash(day, start, dur, room):
            return f"Lab room clash: {room}"
    else:
        room = get_theory_room(cls, day, start, dur)
        

    # ---------- PERIOD CHECKS ----------
    for p in range(start, start + dur):
        if (fac, day, p) in FAC_BLOCKED:
            return f"{FAC_NAME.get(fac, fac)} unavailable"

        if busy("Class", cls, day, p):
            return "Class clash"

        if busy("Faculty", fac, day, p):
            # BI-LAB faculty may be different → allow
            existing = [
                r for r in st.session_state.TT
                if r["Day"] == day and r["Period"] == p
            ]
            if not any(is_bi_lab_pair(sub, r["Subject"]) for r in existing):
                return "Faculty clash"
        if room == "LIBRARY" and library_overflow(day, p):
          return "Library already used by 2 classes"

    
    # ---------- HOURS ----------
    used = sum(1 for r in st.session_state.TT if r["Class"] == cls and r["Subject"] == sub)
    maxh = SUB_MAX_HOURS.get((cls, sub))
    if maxh is None or used + dur > maxh:
        return "Weekly hours exceeded"

    # ---------- INSERT ----------
    #for p in range(start, start + dur):
     #   st.session_state.TT.append({
      #      "Class": cls,
       #     "Subject": sub,
        #    "Faculty": fac,
         #   "Day": day,
          #  "Period": p,
           # "Room": room
        #})

    #autosave()
    #return None


# ==================================================
# AI SUPPORT (SUGGESTIONS ONLY)
# ==================================================
def suggest_slots(cls, sub):
    fac = SUB_FAC.get((cls, sub))
    dur = 3 if sub.endswith("LAB") else 2 if sub in TWO_PERIOD_SUBS else 1
    suggestions = []

    for d in DAYS:
        for p in PERIODS:
            if p + dur - 1 > 7:
                continue
            if any(busy("Class", cls, d, x) for x in range(p, p + dur)):
                continue
            if any((fac, d, x) in FAC_BLOCKED for x in range(p, p + dur)):
                continue
            suggestions.append(f"{d} P{p}")
    return suggestions[:3]

# ==================================================
# UI
# ==================================================
st.title("Timetable Generative System – Department of BS&H - VIEW")

#c1, c2 = st.columns(2)

#with c1:
 #   st.subheader("➕ Add Entry")
  #  with st.form("add"):
   #     cls = st.selectbox("Class", CLASSES)
    #    subs = teaching[teaching["Class_ID"] == cls]["Subject_ID"].unique()
     #   sub = st.selectbox("Subject", subs)
      #  day = st.selectbox("Day", DAYS)
       # start = st.selectbox("Start Period", PERIODS)
        #if st.form_submit_button("ADD"):
         # err = add_entry(cls, sub, day, start)
          #if err:
           #  st.warning(err)
          #else:
           #  st.success("Added")

        #sugg = suggest_slots(cls, sub)
        #if sugg:
         #   st.info("Suggested slots: " + ", ".join(sugg))

#with c2:
 #   st.subheader("❌ Delete Entry")
  #  with st.form("del"):
   #     dcls = st.selectbox("Class", CLASSES, key="dcls")
    #    dday = st.selectbox("Day", DAYS)
     #   dper = st.selectbox("Period", PERIODS)
      #  if st.form_submit_button("DELETE"):
       #     st.session_state.TT = [
        #        r for r in st.session_state.TT
         #       if not (r["Class"] == dcls and r["Day"] == dday and r["Period"] == dper)
          #  ]
           # autosave()
            #st.success("Deleted")

#df = pd.DataFrame(st.session_state.TT)

#st.markdown("---")
#st.info(f"📌 Pending load → {pending_load_row(cls)}")

# ==================================================
# GRID
# ==================================================
def grid(df, label):
    g = pd.DataFrame("", index=DAYS, columns=PERIODS)
    for _, r in df.iterrows():
        g.loc[r["Day"], r["Period"]] = label(r)
    return g

def faculty_grid_with_availability(df, faculty_id):
    g = pd.DataFrame("", index=DAYS, columns=PERIODS)
    style = pd.DataFrame("", index=DAYS, columns=PERIODS)

    # Fill timetable data
    for _, r in df.iterrows():
        g.loc[r["Day"], r["Period"]] = r["Class"]

    # Highlight blocked slots
    for day in DAYS:
        for p in PERIODS:
            if (faculty_id, day, p) in FAC_BLOCKED:
                style.loc[day, p] = "background-color: #ffcccc"  # light red

    return g.style.apply(lambda _: style, axis=None)

# ==================================================
# STANDARD FOUR VIEWS
# ==================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ["📘 Class View", "👨‍🏫 Faculty View", "🧪 Lab View", "🏫 Room View"]
)

with tab1:
    cls_v = st.selectbox("Class", CLASSES, key="cv")

    # ✅ DEFINE cdf HERE (THIS WAS MISSING)
    cdf = df[df["Class"] == cls_v]

    st.dataframe(
        grid(
            cdf,
            lambda r: (
                f'{r["Subject"]} | CLASS COORDINATOR'
                if r["Faculty"] == "WEEKLY_TEST_FACULTY"
                else f'{r["Subject"]} | {FAC_NAME.get(r["Faculty"], r["Faculty"])}'
            )
        )
    )

with tab2:
    fname = st.selectbox("Faculty", sorted(FAC_NAME.values()))
    fid = [k for k, v in FAC_NAME.items() if v == fname][0]

    fdf = df[df["Faculty"] == fid]

    st.dataframe(
        faculty_grid_with_availability(fdf, fid),
        use_container_width=True
    )

    st.caption("🔴 Red cells indicate faculty unavailable slots")

with tab3:
    lab = st.selectbox("Lab", sorted(labs_df["Lab_Subject"].unique()))
    ldf = df[df["Subject"].isin([lab] + [b for pair in BI_LABS if lab in pair for b in pair])]
    st.dataframe(
        grid(ldf, lambda r: f'{r["Class"]} | {FAC_NAME.get(r["Faculty"])}')
    )

with tab4:
    st.subheader("Theory Room Planning")

    # ---------- selectors ----------
    mirror_cls = st.radio(
        "Select Class (Theory Only)",
        CLASSES,
        horizontal=True
    )

    room = st.radio(
        "Select Room (Primary Rooms)",
        PRIMARY_ROOMS,
        horizontal=True
    )

    # ---------- show current lock ----------
    if "CLASS_ROOM_LOCK" not in st.session_state:
        st.session_state.CLASS_ROOM_LOCK = {}

    locked_room = st.session_state.CLASS_ROOM_LOCK.get(mirror_cls)

    if locked_room:
        st.info(f"🔒 {mirror_cls} is currently locked to room {locked_room}")
    else:
        st.warning(f"⚠️ {mirror_cls} is not locked to any room")

    # ---------- lock / unlock controls ----------
    c_lock, c_unlock = st.columns(2)

    with c_lock:
        if st.button("🔒 Lock this Class to this Room"):
            st.session_state.CLASS_ROOM_LOCK[mirror_cls] = room
            st.success(f"{mirror_cls} locked to {room}")

    with c_unlock:
        if locked_room and st.button("🔓 Unlock this Class"):
            del st.session_state.CLASS_ROOM_LOCK[mirror_cls]
            st.success(f"{mirror_cls} unlocked from room")

    st.divider()

    # ---------- mirror timetable (theory only) ----------
    mirror = df[
        (df["Class"] == mirror_cls) &
        (~df["Subject"].fillna("").astype(str).str.endswith("LAB")) &
        (~df["Subject"].isin(EXCLUDE_THEORY_ROOM))
    ]

    st.dataframe(
        grid(
            mirror,
            lambda r: f'{r["Class"]} | {r["Subject"]} | {FAC_NAME.get(r["Faculty"])}'
        ),
        use_container_width=True
    )

    # ---------- policy explanation ----------
    st.caption(
        "📌 Policy: Locked classes always use their locked room. "
        "Excess classes may occupy free rooms only in continuous slots "
        "(1–2, 3–4, 1–4, 5–7)."
    )
# ==================================================
# DOWNLOAD
# ==================================================
if st.button("Download Excel"):
    with pd.ExcelWriter("Timetable.xlsx", engine="openpyxl") as w:
        df.to_excel(w, "RAW", index=False)

    st.success("Downloaded Timetable.xlsx")










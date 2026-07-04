import calendar
import datetime as dt
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# st.write("URL:", st.secrets.get("SUPABASE_URL"))
# st.write("Key first 20 chars:", st.secrets.get("SUPABASE_KEY")[:20])

try:
    from supabase import create_client, Client
except Exception:  # keeps local demo working before installing requirements
    create_client = None
    Client = Any

APP_TITLE = "Monthly Productivity Dashboard"
MONTHS = list(calendar.month_name)[1:]
PRIORITIES = ["High", "Medium", "Low"]
CATEGORIES = ["Study", "Health", "Work", "Personal", "Finance", "Habit", "Other"]
FREQUENCIES = ["Daily", "Weekly", "Custom"]
DEFAULT_TASKS = [
    {"task_name": "Exercise", "priority": "High", "category": "Health", "frequency": "Weekly", "target": 25, "notes": "Morning walk or workout", "sort_order": 1},
    {"task_name": "Study", "priority": "High", "category": "Study", "frequency": "Daily", "target": 20, "notes": "Interview practice", "sort_order": 2},
    {"task_name": "Read Book", "priority": "Medium", "category": "Habit", "frequency": "Daily", "target": 15, "notes": "15 pages", "sort_order": 3},
    {"task_name": "Call Family", "priority": "Low", "category": "Personal", "frequency": "Weekly", "target": 6, "notes": "Stay connected", "sort_order": 4},
]
QUOTES = [
    "Small steps every day.",
    "Progress, not perfection.",
    "Your future self is watching.",
    "Consistency beats intensity.",
    "Win the day, one checkbox at a time.",
    "Make today count.",
    "Focus on the next right action.",
]

st.set_page_config(page_title=APP_TITLE, page_icon="🌸", layout="wide")

CSS = """
<style>
:root {
  --bg: #fff8f1;
  --card: #ffffff;
  --lav: #d8c6ff;
  --pink: #ffd1dc;
  --mint: #d8f3dc;
  --sky: #cdeeff;
  --peach: #ffd8b5;
  --yellow: #fff2b8;
  --text: #44394a;
}
.stApp { background: linear-gradient(135deg, #fff8f1 0%, #fff6fb 45%, #f6fbff 100%); color: var(--text); }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
[data-testid="stMetricValue"] { font-size: 1.55rem; color: #44394a; }
[data-testid="stMetricLabel"] { color: #78657e; }
div[data-testid="stMetric"] { background: rgba(255,255,255,0.78); border: 1px solid rgba(216,198,255,0.55); border-radius: 20px; padding: 14px 16px; box-shadow: 0 8px 24px rgba(177, 149, 210, 0.12); }
.soft-card { background: rgba(255,255,255,0.82); border: 1px solid rgba(216,198,255,0.5); border-radius: 22px; padding: 18px 20px; box-shadow: 0 10px 28px rgba(177,149,210,0.12); margin-bottom: 14px; }
.title-card { background: linear-gradient(90deg, #d8c6ff, #ffd1dc, #ffd8b5); border-radius: 24px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 10px 30px rgba(177,149,210,0.18); }
.title-card h1 { margin: 0; font-size: 1.8rem; color: #4b3f54; }
.title-card p { margin: 4px 0 0 0; color: #5d5364; font-weight: 500; }
.section-title { font-size: 1.05rem; font-weight: 800; color: #57445f; margin: 8px 0 10px 0; }
.today-pill { display:inline-block; padding:4px 10px; border-radius:999px; background:#fff2b8; border:1px solid #f6d775; color:#5d4b13; font-weight:700; font-size:0.8rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

@dataclass
class BaseStore:
    def ensure_seed(self, year: int, month: int) -> None: ...
    def list_tasks(self, year: int, month: int) -> pd.DataFrame: ...
    def save_tasks(self, year: int, month: int, tasks: pd.DataFrame) -> None: ...
    def add_task(self, year: int, month: int, task: Dict[str, Any]) -> None: ...
    def delete_task(self, task_id: str) -> None: ...
    def list_completions(self, year: int, month: int) -> pd.DataFrame: ...
    def upsert_completion(self, task_id: str, year: int, month: int, day: int, completed: bool) -> None: ...
    def get_reflection(self, year: int, month: int) -> Dict[str, str]: ...
    def save_reflection(self, year: int, month: int, went_well: str, needs_improvement: str, focus_next_month: str) -> None: ...
    def clone_previous_month(self, year: int, month: int) -> int: ...

class SQLiteStore(BaseStore):
    def __init__(self, db_path: str = "mochu_local.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        create table if not exists mochu_tasks (
          id text primary key, year integer, month integer, task_name text, priority text,
          category text, frequency text, target integer, notes text, sort_order integer,
          active integer default 1, created_at text, updated_at text
        );
        create table if not exists mochu_completions (
          id text primary key, task_id text, year integer, month integer, day integer,
          completed integer default 0, updated_at text,
          unique(task_id, year, month, day)
        );
        create table if not exists mochu_reflections (
          id text primary key, year integer, month integer, went_well text,
          needs_improvement text, focus_next_month text, updated_at text,
          unique(year, month)
        );
        """)
        self.conn.commit()

    def _now(self): return dt.datetime.utcnow().isoformat()

    def ensure_seed(self, year: int, month: int) -> None:
        count = self.conn.execute("select count(*) from mochu_tasks where year=? and month=?", (year, month)).fetchone()[0]
        if count == 0:
            for t in DEFAULT_TASKS:
                self.add_task(year, month, t)

    def list_tasks(self, year: int, month: int) -> pd.DataFrame:
        rows = self.conn.execute("select * from mochu_tasks where year=? and month=? and active=1 order by sort_order, created_at", (year, month)).fetchall()
        return pd.DataFrame([dict(r) for r in rows])

    def save_tasks(self, year: int, month: int, tasks: pd.DataFrame) -> None:
        for i, row in tasks.reset_index(drop=True).iterrows():
            self.conn.execute("""update mochu_tasks set task_name=?, priority=?, category=?, frequency=?, target=?, notes=?, sort_order=?, updated_at=? where id=?""",
                (row["task_name"], row["priority"], row["category"], row["frequency"], int(row["target"] or 0), row.get("notes", ""), i + 1, self._now(), row["id"]))
        self.conn.commit()

    def add_task(self, year: int, month: int, task: Dict[str, Any]) -> None:
        self.conn.execute("""insert into mochu_tasks(id,year,month,task_name,priority,category,frequency,target,notes,sort_order,active,created_at,updated_at)
        values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), year, month, task.get("task_name", "New Task"), task.get("priority", "Medium"), task.get("category", "Other"), task.get("frequency", "Daily"), int(task.get("target", 0) or 0), task.get("notes", ""), int(task.get("sort_order", 999)), 1, self._now(), self._now()))
        self.conn.commit()

    def delete_task(self, task_id: str) -> None:
        self.conn.execute("update mochu_tasks set active=0, updated_at=? where id=?", (self._now(), task_id))
        self.conn.commit()

    def list_completions(self, year: int, month: int) -> pd.DataFrame:
        rows = self.conn.execute("select * from mochu_completions where year=? and month=?", (year, month)).fetchall()
        return pd.DataFrame([dict(r) for r in rows])

    def upsert_completion(self, task_id: str, year: int, month: int, day: int, completed: bool) -> None:
        self.conn.execute("""insert into mochu_completions(id, task_id, year, month, day, completed, updated_at)
        values(?,?,?,?,?,?,?) on conflict(task_id, year, month, day) do update set completed=excluded.completed, updated_at=excluded.updated_at""",
        (str(uuid.uuid4()), task_id, year, month, day, int(completed), self._now()))
        self.conn.commit()

    def get_reflection(self, year: int, month: int) -> Dict[str, str]:
        row = self.conn.execute("select * from mochu_reflections where year=? and month=?", (year, month)).fetchone()
        return dict(row) if row else {"went_well": "", "needs_improvement": "", "focus_next_month": ""}

    def save_reflection(self, year: int, month: int, went_well: str, needs_improvement: str, focus_next_month: str) -> None:
        self.conn.execute("""insert into mochu_reflections(id,year,month,went_well,needs_improvement,focus_next_month,updated_at)
        values(?,?,?,?,?,?,?) on conflict(year,month) do update set went_well=excluded.went_well, needs_improvement=excluded.needs_improvement, focus_next_month=excluded.focus_next_month, updated_at=excluded.updated_at""",
        (str(uuid.uuid4()), year, month, went_well, needs_improvement, focus_next_month, self._now()))
        self.conn.commit()

    def clone_previous_month(self, year: int, month: int) -> int:
        prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
        source = self.list_tasks(prev_year, prev_month)
        if source.empty: return 0
        existing = self.list_tasks(year, month)
        if not existing.empty: return 0
        for _, r in source.iterrows():
            self.add_task(year, month, r.to_dict())
        return len(source)

class SupabaseStore(BaseStore):
    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)

    def ensure_seed(self, year: int, month: int) -> None:
        count_resp = self.client.table("mochu_tasks").select("id", count="exact").eq("year", year).eq("month", month).eq("active", True).execute()
        if count_resp.count == 0:
            for t in DEFAULT_TASKS:
                self.add_task(year, month, t)

    def list_tasks(self, year: int, month: int) -> pd.DataFrame:
        data = self.client.table("mochu_tasks").select("*").eq("year", year).eq("month", month).eq("active", True).order("sort_order").execute().data
        return pd.DataFrame(data)

    def save_tasks(self, year: int, month: int, tasks: pd.DataFrame) -> None:
        for i, row in tasks.reset_index(drop=True).iterrows():
            payload = {k: row[k] for k in ["task_name", "priority", "category", "frequency", "notes"] if k in row}
            payload["target"] = int(row.get("target", 0) or 0)
            payload["sort_order"] = i + 1
            payload["updated_at"] = dt.datetime.utcnow().isoformat()
            self.client.table("mochu_tasks").update(payload).eq("id", row["id"]).execute()

    def add_task(self, year: int, month: int, task: Dict[str, Any]) -> None:
        payload = {
            "year": year, "month": month,
            "task_name": task.get("task_name", "New Task"),
            "priority": task.get("priority", "Medium"),
            "category": task.get("category", "Other"),
            "frequency": task.get("frequency", "Daily"),
            "target": int(task.get("target", 0) or 0),
            "notes": task.get("notes", ""),
            "sort_order": int(task.get("sort_order", 999)),
            "active": True,
        }
        self.client.table("mochu_tasks").insert(payload).execute()

    def delete_task(self, task_id: str) -> None:
        self.client.table("mochu_tasks").update({"active": False, "updated_at": dt.datetime.utcnow().isoformat()}).eq("id", task_id).execute()

    def list_completions(self, year: int, month: int) -> pd.DataFrame:
        data = self.client.table("mochu_completions").select("*").eq("year", year).eq("month", month).execute().data
        return pd.DataFrame(data)

    def upsert_completion(self, task_id: str, year: int, month: int, day: int, completed: bool) -> None:
        payload = {"task_id": task_id, "year": year, "month": month, "day": day, "completed": completed, "updated_at": dt.datetime.utcnow().isoformat()}
        self.client.table("mochu_completions").upsert(payload, on_conflict="task_id,year,month,day").execute()

    def get_reflection(self, year: int, month: int) -> Dict[str, str]:
        data = self.client.table("mochu_reflections").select("*").eq("year", year).eq("month", month).execute().data
        return data[0] if data else {"went_well": "", "needs_improvement": "", "focus_next_month": ""}

    def save_reflection(self, year: int, month: int, went_well: str, needs_improvement: str, focus_next_month: str) -> None:
        payload = {"year": year, "month": month, "went_well": went_well, "needs_improvement": needs_improvement, "focus_next_month": focus_next_month, "updated_at": dt.datetime.utcnow().isoformat()}
        self.client.table("mochu_reflections").upsert(payload, on_conflict="year,month").execute()

    def clone_previous_month(self, year: int, month: int) -> int:
        prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
        source = self.list_tasks(prev_year, prev_month)
        existing = self.list_tasks(year, month)
        if source.empty or not existing.empty: return 0
        for _, r in source.iterrows():
            self.add_task(year, month, r.to_dict())
        return len(source)

@st.cache_resource
def get_store() -> Tuple[BaseStore, str]:
    url = st.secrets.get("SUPABASE_URL", "") if hasattr(st, "secrets") else ""
    key = st.secrets.get("SUPABASE_KEY", "") if hasattr(st, "secrets") else ""
    if url and key and create_client is not None:
        return SupabaseStore(url, key), "Supabase online database"
    return SQLiteStore(), "Local SQLite demo database"

def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]

def month_dates(year: int, month: int) -> List[dt.date]:
    return [dt.date(year, month, d) for d in range(1, days_in_month(year, month) + 1)]

def make_grid(tasks: pd.DataFrame, completions: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    dates = month_dates(year, month)
    rows = []
    completed_lookup = {}
    if not completions.empty:
        completed_lookup = {(str(r["task_id"]), int(r["day"])): bool(r["completed"]) for _, r in completions.iterrows()}
    for _, task in tasks.iterrows():
        row = {"task_id": str(task["id"]), "Task Name": task["task_name"]}
        for d in dates:
            row[str(d.day)] = completed_lookup.get((str(task["id"]), d.day), False)
        rows.append(row)
    return pd.DataFrame(rows)

def current_and_longest_streak(vals: List[bool]) -> Tuple[int, int]:
    current = 0
    for v in reversed(vals):
        if v: current += 1
        else: break
    longest = best = 0
    for v in vals:
        best = best + 1 if v else 0
        longest = max(longest, best)
    return current, longest

def compute_metrics(tasks: pd.DataFrame, grid: pd.DataFrame, year: int, month: int) -> Dict[str, Any]:
    n_tasks = len(tasks)
    dim = days_in_month(year, month)
    total_slots = n_tasks * dim
    if grid.empty:
        bool_cols = []
        daily_done = pd.Series([0] * dim, index=list(range(1, dim + 1)))
    else:
        bool_cols = [str(i) for i in range(1, dim + 1)]
        daily_done = grid[bool_cols].sum(axis=0).rename(lambda x: int(x))
    completed = int(daily_done.sum())
    pending = int(total_slots - completed)
    overall_progress = completed / total_slots if total_slots else 0
    today = dt.date.today()
    today_completion = 0
    if today.year == year and today.month == month and not grid.empty:
        today_completion = int(grid[str(today.day)].sum())
    day_progress = (daily_done / n_tasks).fillna(0) if n_tasks else pd.Series([0] * dim, index=list(range(1, dim + 1)))
    day_done_bool = [x == n_tasks and n_tasks > 0 for x in daily_done.tolist()]
    current_streak, longest_streak = current_and_longest_streak(day_done_bool)
    best_day_idx = int(day_progress.idxmax()) if len(day_progress) else 1
    weak_day_idx = int(day_progress.idxmin()) if len(day_progress) else 1
    return {
        "total_tasks": n_tasks, "total_completed": completed, "total_pending": pending,
        "overall_progress": overall_progress, "today_completion": today_completion,
        "current_streak": current_streak, "longest_streak": longest_streak,
        "best_day": f"{best_day_idx:02d}-{MONTHS[month-1][:3]} ({day_progress.loc[best_day_idx]:.0%})",
        "weak_day": f"{weak_day_idx:02d}-{MONTHS[month-1][:3]} ({day_progress.loc[weak_day_idx]:.0%})",
        "missed_gap": pending, "daily_done": daily_done, "day_progress": day_progress,
    }

def task_progress(tasks: pd.DataFrame, grid: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    dim = days_in_month(year, month)
    if tasks.empty: return pd.DataFrame()
    rows = []
    for _, task in tasks.iterrows():
        g = grid[grid["task_id"] == str(task["id"])]
        vals = [bool(g.iloc[0][str(d)]) for d in range(1, dim + 1)] if not g.empty else [False] * dim
        actual = sum(vals)
        target = int(task.get("target", 0) or 0)
        cur, longest = current_and_longest_streak(vals)
        comp = actual / dim if dim else 0
        priority_weight = {"High": 1.4, "Medium": 1.1, "Low": 0.9}.get(task.get("priority", "Medium"), 1.0)
        score = round((actual * 5 + comp * 100 + cur * 3 + longest * 2) * priority_weight / 5, 1)
        rows.append({
            "Task Name": task["task_name"], "Priority": task["priority"], "Category": task["category"],
            "Actual Done": actual, "Target": target, "Gap": max(target - actual, 0),
            "Completion %": comp, "Current Streak": cur, "Longest Streak": longest, "Score": score,
        })
    return pd.DataFrame(rows).sort_values(["Priority", "Score"], ascending=[True, False])

def plot_daily_trend(metrics: Dict[str, Any], year: int, month: int):
    dates = month_dates(year, month)
    df = pd.DataFrame({"Date": dates, "Completed": metrics["daily_done"].values})
    fig = px.line(df, x="Date", y="Completed", markers=True, title="📈 Daily Completion Trend")
    fig.update_traces(line_width=3)
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=45, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.45)")
    return fig

def plot_completion_pie(metrics: Dict[str, Any]):
    df = pd.DataFrame({"Status": ["Completed", "Pending"], "Count": [metrics["total_completed"], metrics["total_pending"]]})
    fig = px.pie(df, names="Status", values="Count", hole=0.55, title="✅ Completed vs Pending")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=45, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig

def plot_weekly(metrics: Dict[str, Any], year: int, month: int):
    dates = month_dates(year, month)
    daily = pd.DataFrame({"date": dates, "completed": metrics["daily_done"].values})
    daily["week"] = daily["date"].apply(lambda d: f"W{((d.day - 1) // 7) + 1}")
    weekly = daily.groupby("week", as_index=False)["completed"].sum()
    fig = px.bar(weekly, x="week", y="completed", title="📊 Weekly Progress")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=45, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.45)")
    return fig

def render_task_lists(progress: pd.DataFrame, grid: pd.DataFrame, year: int, month: int) -> None:
    today = dt.date.today()
    today_day = today.day if today.year == year and today.month == month else None
    c1, c2, c3 = st.columns(3)
    high_order = {"High": 0, "Medium": 1, "Low": 2}
    p = progress.copy()
    p["priority_rank"] = p["Priority"].map(high_order).fillna(3)
    with c1:
        st.markdown('<div class="soft-card"><div class="section-title">🌸 Focus for Today</div>', unsafe_allow_html=True)
        if today_day is None or grid.empty:
            st.write("Select the current month to see today's focus.")
        else:
            done_today = grid[["Task Name", str(today_day)]].rename(columns={str(today_day): "done"})
            items = done_today[~done_today["done"]]["Task Name"].head(10).tolist()
            st.write("\n".join([f"• {x}" for x in items]) if items else "All clear for today ✨")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="soft-card"><div class="section-title">🏆 Top 3 Priorities</div>', unsafe_allow_html=True)
        top = p.sort_values(["priority_rank", "Gap", "Score"], ascending=[True, False, False]).head(3)
        st.write("\n".join([f"• {r['Task Name']}" for _, r in top.iterrows()]) if not top.empty else "No tasks yet.")
        st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="soft-card"><div class="section-title">⚠️ Tasks Falling Behind</div>', unsafe_allow_html=True)
        behind = p[p["Gap"] > 0].sort_values("Gap", ascending=False).head(8)
        st.write("\n".join([f"• {r['Task Name']} — gap {int(r['Gap'])}" for _, r in behind.iterrows()]) if not behind.empty else "No gap right now 🌱")
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    store, db_mode = get_store()
    today = dt.date.today()
    st.markdown(f"""
    <div class="title-card">
      <h1>🌸 {APP_TITLE}</h1>
      <p>✨ {QUOTES[today.day % len(QUOTES)]}</p>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.header("Select Month and Year")
        month_name = st.selectbox("Month", MONTHS, index=today.month - 1)
        month = MONTHS.index(month_name) + 1
        year = st.selectbox("Year", list(range(2024, 2032)), index=list(range(2024, 2032)).index(today.year) if today.year in range(2024, 2032) else 2)
        st.caption(f"Database: {db_mode}")
        if "SQLite" in db_mode:
            st.warning("Local demo mode. Add Supabase secrets for hosted persistence.")
        if st.button("Clone previous month's tasks", use_container_width=True):
            copied = store.clone_previous_month(year, month)
            if copied:
                st.success(f"Copied {copied} tasks.")
                st.rerun()
            else:
                st.info("Nothing copied. Current month may already have tasks or previous month is empty.")
        if st.button("Reset to sample tasks if empty", use_container_width=True):
            store.ensure_seed(year, month)
            st.rerun()

    store.ensure_seed(year, month)
    tasks = store.list_tasks(year, month)
    completions = store.list_completions(year, month)
    if tasks.empty:
        st.info("No tasks yet. Add one below.")
    grid = make_grid(tasks, completions, year, month)
    metrics = compute_metrics(tasks, grid, year, month)
    progress = task_progress(tasks, grid, year, month)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📌 Total Tasks", metrics["total_tasks"])
    m2.metric("✅ Total Completed", metrics["total_completed"])
    m3.metric("⏳ Total Pending", metrics["total_pending"])
    m4.metric("🎯 Overall Progress", f"{metrics['overall_progress']:.0%}")
    m5.metric("📅 Today Completion", metrics["today_completion"])

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("🔥 Current Streak", metrics["current_streak"])
    s2.metric("🏆 Longest Streak", metrics["longest_streak"])
    s3.metric("⭐ Best Day", metrics["best_day"])
    s4.metric("🌧 Weak Day", metrics["weak_day"])
    s5.metric("⚠️ Missed / Gap", metrics["missed_gap"])

    tab1, tab2, tab3, tab4 = st.tabs(["✅ Daily Tracker", "📝 Task Manager", "📊 Analytics", "🌙 Monthly Reflection"])

    with tab1:
        st.markdown('<div class="section-title">✅ Daily Checkbox Grid</div>', unsafe_allow_html=True)
        if not grid.empty:
            display_grid = grid.drop(columns=["task_id"])
            edited = st.data_editor(
                display_grid,
                key=f"grid_{year}_{month}",
                use_container_width=True,
                hide_index=True,
                disabled=["Task Name"],
                column_config={
                    "Task Name": st.column_config.TextColumn("Task Name", width="medium"),
                    **{str(d): st.column_config.CheckboxColumn(str(d), width="small") for d in range(1, days_in_month(year, month) + 1)}
                },
                height=min(720, 100 + 36 * max(len(display_grid), 4)),
            )
            if st.button("Save checkbox changes", type="primary", use_container_width=True):
                for row_idx, row in edited.iterrows():
                    task_id = grid.iloc[row_idx]["task_id"]
                    for d in range(1, days_in_month(year, month) + 1):
                        old = bool(grid.iloc[row_idx][str(d)])
                        new = bool(row[str(d)])
                        if old != new:
                            store.upsert_completion(task_id, year, month, d, new)
                st.success("Saved daily tracker state.")
                st.rerun()
        else:
            st.info("Add tasks in Task Manager to see the daily grid.")

        if not progress.empty:
            st.markdown('<div class="section-title">📋 Task Progress Summary</div>', unsafe_allow_html=True)
            st.dataframe(
                progress.drop(columns=["priority_rank"], errors="ignore"),
                use_container_width=True,
                hide_index=True,
                column_config={"Completion %": st.column_config.ProgressColumn("Completion %", format="%.0f", min_value=0, max_value=1)},
            )

    with tab2:
        st.markdown('<div class="section-title">📝 Add New Task</div>', unsafe_allow_html=True)
        with st.form("add_task_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            task_name = c1.text_input("Task Name")
            priority = c2.selectbox("Priority", PRIORITIES)
            category = c3.selectbox("Category", CATEGORIES)
            c4, c5 = st.columns([1, 3])
            frequency = c4.selectbox("Frequency", FREQUENCIES)
            target = c4.number_input("Monthly Target", min_value=0, max_value=31, value=10)
            notes = c5.text_area("Notes", height=100)
            submitted = st.form_submit_button("Add Task", type="primary")
            if submitted and task_name.strip():
                store.add_task(year, month, {"task_name": task_name.strip(), "priority": priority, "category": category, "frequency": frequency, "target": int(target), "notes": notes, "sort_order": len(tasks) + 1})
                st.success("Task added.")
                st.rerun()

        st.markdown('<div class="section-title">✏️ Edit Existing Tasks</div>', unsafe_allow_html=True)
        if not tasks.empty:
            editable = tasks[["id", "task_name", "priority", "category", "frequency", "target", "notes"]].copy()
            edited_tasks = st.data_editor(
                editable.drop(columns=["id"]),
                key=f"tasks_{year}_{month}",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "task_name": st.column_config.TextColumn("Task Name", required=True),
                    "priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES),
                    "category": st.column_config.SelectboxColumn("Category", options=CATEGORIES),
                    "frequency": st.column_config.SelectboxColumn("Frequency", options=FREQUENCIES),
                    "target": st.column_config.NumberColumn("Target", min_value=0, max_value=31),
                    "notes": st.column_config.TextColumn("Notes", width="large"),
                },
            )
            csave, cdel = st.columns([2, 1])
            if csave.button("Save task edits", type="primary", use_container_width=True):
                edited_tasks.insert(0, "id", editable["id"].values)
                store.save_tasks(year, month, edited_tasks)
                st.success("Task edits saved.")
                st.rerun()
            task_to_delete = cdel.selectbox("Delete task", [""] + tasks["task_name"].tolist())
            if task_to_delete and cdel.button("Delete selected", use_container_width=True):
                task_id = tasks.loc[tasks["task_name"] == task_to_delete, "id"].iloc[0]
                store.delete_task(str(task_id))
                st.success("Task deleted.")
                st.rerun()

    with tab3:
        left, mid, right = st.columns([2, 1, 1])
        with left: st.plotly_chart(plot_daily_trend(metrics, year, month), use_container_width=True)
        with mid: st.plotly_chart(plot_completion_pie(metrics), use_container_width=True)
        with right: st.plotly_chart(plot_weekly(metrics, year, month), use_container_width=True)
        render_task_lists(progress, grid, year, month)

    with tab4:
        reflection = store.get_reflection(year, month)
        with st.form("reflection_form"):
            c1, c2, c3 = st.columns(3)
            went_well = c1.text_area("🌟 What went well?", value=reflection.get("went_well", ""), height=220)
            needs_improvement = c2.text_area("🛠 What needs improvement?", value=reflection.get("needs_improvement", ""), height=220)
            focus_next_month = c3.text_area("🚀 Focus for next month", value=reflection.get("focus_next_month", ""), height=220)
            if st.form_submit_button("Save monthly reflection", type="primary", use_container_width=True):
                store.save_reflection(year, month, went_well, needs_improvement, focus_next_month)
                st.success("Reflection saved.")

if __name__ == "__main__":
    main()

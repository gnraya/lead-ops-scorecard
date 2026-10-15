"""
Lead Ops - Month-on-Month Scorecard Dashboard
==============================================

A shareable Streamlit dashboard where each team member logs in with their alias
and sees ONLY their own month-on-month scorecard. The manager (alias `gnraya`)
can view everyone.

Run locally:
    streamlit run dashboard.py

Share with the team:
    Deploy to Streamlit Community Cloud (free) from a GitHub repo, or run on an
    internal server. See the README for deployment + auth notes.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

import scorecard_data as sc

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
MANAGER_ALIASES = {"gnraya"}  # can view everybody


def _get_team_password() -> str:
    """Shared team password.

    Resolution order:
      1. Streamlit secrets ([general] team_password) if present.
      2. TEAM_PASSWORD environment variable.
      3. Fallback default (CHANGE THIS before sharing).
    """
    try:
        if "team_password" in st.secrets:  # type: ignore[operator]
            return str(st.secrets["team_password"])
    except Exception:
        pass
    return os.environ.get("TEAM_PASSWORD", "LeadOps2026")

METRIC_COLS = [nice for _, nice in sc.METRIC_KEYS]

st.set_page_config(
    page_title="Lead Ops Scorecard",
    page_icon="📊",
    layout="wide",
)


# --------------------------------------------------------------------------
# Data (cached so the workbook is parsed once per session/refresh)
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading scorecards...")
def get_data():
    df = sc.load_scorecards()
    names = sc.display_name_map()
    return df, names


def _data_available() -> bool:
    """True if the scorecard data (secret or local file) can be loaded."""
    try:
        df, _ = get_data()
        return not df.empty
    except Exception:
        return False


def fmt_pct(x):
    if pd.isna(x):
        return "—"
    return f"{x * 100:.1f}%"


def pretty_name(alias: str, names: dict) -> str:
    full = names.get(alias)
    return f"{full} ({alias})" if full else alias


# --------------------------------------------------------------------------
# Login gate
# --------------------------------------------------------------------------
def login_view():
    st.title("📊 Lead Ops Scorecard")
    st.caption("Sign in with your alias to view your month-on-month scorecard.")

    with st.form("login"):
        alias = st.text_input("Your alias", placeholder="e.g. qrishraj").strip().lower()
        submitted = st.form_submit_button("View my scorecard")

    if submitted:
        df, _ = get_data()
        valid = set(df["alias"].unique()) | MANAGER_ALIASES
        if alias in valid:
            st.session_state["alias"] = alias
            st.rerun()
        else:
            st.error("That alias wasn't found. Check the spelling or contact your manager.")

    st.info(
        "You will only be able to see your own scorecard. "
        "Managers can view the whole team."
    )


# --------------------------------------------------------------------------
# Scorecard rendering
# --------------------------------------------------------------------------
def render_person(df_person: pd.DataFrame, alias: str, names: dict):
    st.subheader(f"Scorecard — {pretty_name(alias, names)}")

    if df_person.empty:
        st.warning("No scorecard data found for this alias yet.")
        return

    df_person = df_person.sort_values("month", key=lambda s: s.map(
        {m: i for i, m in enumerate(sc.MONTH_ORDER)}
    ))

    # Headline metrics (latest month)
    latest = df_person.iloc[-1]
    prev = df_person.iloc[-2] if len(df_person) > 1 else None

    c1, c2, c3 = st.columns(3)
    with c1:
        delta = None
        if prev is not None and not pd.isna(prev["overall"]) and not pd.isna(latest["overall"]):
            delta = f"{(latest['overall'] - prev['overall']) * 100:+.1f} pts"
        st.metric(f"Overall ({latest['month']})", fmt_pct(latest["overall"]), delta)
    with c2:
        st.metric("Level", str(latest.get("level", "—")))
    with c3:
        sr = latest.get("stack_rank")
        st.metric("Stack Rank", "—" if pd.isna(sr) else str(int(sr)))

    st.divider()

    # Overall trend
    st.markdown("#### Overall score — month on month")
    trend = df_person.set_index("month")["overall"]
    st.line_chart(trend, height=260, use_container_width=True)

    # Metric breakdown trend
    st.markdown("#### Metric breakdown — month on month")
    metric_trend = df_person.set_index("month")[METRIC_COLS]
    st.line_chart(metric_trend, height=300, use_container_width=True)

    # Detailed table
    st.markdown("#### Details")
    show = df_person[["month", "level", "overall", "stack_rank"] + METRIC_COLS].copy()
    pct_cols = ["overall"] + METRIC_COLS
    for col in pct_cols:
        show[col] = show[col].map(fmt_pct)
    show["stack_rank"] = show["stack_rank"].map(
        lambda v: "—" if pd.isna(v) else str(int(v))
    )
    show = show.rename(columns={
        "month": "Month", "level": "Level",
        "overall": "Overall", "stack_rank": "Stack Rank",
    })
    st.dataframe(show, hide_index=True, use_container_width=True)


def render_team_overview(df: pd.DataFrame, names: dict):
    st.subheader("Team overview")
    st.caption("Overall score by month across the whole team.")

    pivot = df.pivot_table(
        index="month", columns="alias", values="overall", aggfunc="mean"
    )
    pivot = pivot.reindex([m for m in sc.MONTH_ORDER if m in pivot.index])
    st.line_chart(pivot, height=340, use_container_width=True)

    st.markdown("#### Latest-month leaderboard")
    months_present = [m for m in sc.MONTH_ORDER if m in df["month"].unique()]
    if months_present:
        latest_month = months_present[-1]
        latest = df[df["month"] == latest_month].copy()
        latest["name"] = latest["alias"].map(lambda a: pretty_name(a, names))
        latest = latest.sort_values("overall", ascending=False)
        board = latest[["name", "level", "overall", "stack_rank"]].copy()
        board["overall"] = board["overall"].map(fmt_pct)
        board["stack_rank"] = board["stack_rank"].map(
            lambda v: "—" if pd.isna(v) else str(int(v))
        )
        board = board.rename(columns={
            "name": "Team member", "level": "Level",
            "overall": "Overall", "stack_rank": "Stack Rank",
        })
        st.markdown(f"**{latest_month}**")
        st.dataframe(board, hide_index=True, use_container_width=True)


def dashboard_view():
    df, names = get_data()
    alias = st.session_state["alias"]
    is_manager = alias in MANAGER_ALIASES

    with st.sidebar:
        st.markdown(f"**Signed in as**\n\n`{alias}`" + ("  👑 Manager" if is_manager else ""))
        if st.button("Sign out"):
            st.session_state.pop("alias", None)
            st.session_state.pop("authed", None)
            st.rerun()
        st.divider()

        if is_manager:
            st.markdown("### Manager view")
            all_aliases = sorted(df["alias"].unique())
            options = ["— Team overview —"] + [pretty_name(a, names) for a in all_aliases]
            choice = st.selectbox("View scorecard for", options)
        else:
            choice = None

    st.title("📊 Lead Ops Scorecard")

    if is_manager:
        if choice == "— Team overview —":
            render_team_overview(df, names)
        else:
            # choice looks like "Full Name (alias)" or just "alias"
            target = choice.split("(")[-1].rstrip(")").strip() if "(" in choice else choice
            render_person(df[df["alias"] == target], target, names)
    else:
        render_person(df[df["alias"] == alias], alias, names)


# --------------------------------------------------------------------------
# Password gate (shared team password)
# --------------------------------------------------------------------------
def password_gate() -> bool:
    """Return True once the correct shared team password has been entered."""
    if st.session_state.get("authed"):
        return True

    st.title("📊 Lead Ops Scorecard")
    st.caption("Enter the team password to continue.")

    with st.form("password"):
        pw = st.text_input("Team password", type="password")
        submitted = st.form_submit_button("Continue")

    if submitted:
        if pw == _get_team_password():
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Incorrect password. Contact your manager if you need it.")

    return False


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main():
    # Fail gracefully if the data source isn't configured yet.
    if not _data_available():
        st.title("📊 Lead Ops Scorecard")
        st.error("Scorecard data isn't configured yet.")
        st.markdown(
            "The app is deployed but the data secret hasn't been added. "
            "If you're the admin:\n\n"
            "1. Open **Manage app → Settings → Secrets**\n"
            "2. Paste the contents of `secret_block.txt` "
            "(generated by `py make_secret.py`)\n"
            "3. Save — the app will restart with data loaded."
        )
        return

    if not password_gate():
        return
    if "alias" not in st.session_state:
        login_view()
    else:
        dashboard_view()


if __name__ == "__main__":
    main()

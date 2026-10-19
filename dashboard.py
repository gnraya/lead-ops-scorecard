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
from datetime import date

import pandas as pd
import streamlit as st

import scorecard_data as sc

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
MANAGER_ALIASES = {"gnraya"}  # can view everybody

ALL_MONTHS = "All months"  # sentinel for the month filter


def _get_passwords() -> dict:
    """Return the alias -> password map that proves identity at login.

    Stored privately in Streamlit secrets under a [passwords] table, e.g.:

        [passwords]
        gnraya = "manager-secret"
        harishzz = "some-secret"
        lpunniya = "another-secret"

    Each person can ONLY log in as their own alias because they must supply
    the matching password. This is what prevents one teammate from viewing
    another's scorecard.
    """
    try:
        if "passwords" in st.secrets:  # type: ignore[operator]
            # st.secrets["passwords"] behaves like a dict.
            return {str(k).strip().lower(): str(v)
                    for k, v in dict(st.secrets["passwords"]).items()}
    except Exception:
        pass
    return {}

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


# Metrics whose "Actual" value is a percentage (0-1) vs. a raw point score.
PCT_METRICS = {"Productivity", "Quality", "PKT"}
POINT_METRICS = {"Additional Task", "Process Improvements", "Schedule Adherence"}


def fmt_num(x):
    """Format a raw point value: drop trailing .0 but keep real decimals."""
    if pd.isna(x):
        return "—"
    if float(x) == int(x):
        return str(int(x))
    return f"{float(x):.2f}".rstrip("0").rstrip(".")


def fmt_metric(col, x):
    """Format an Actual metric value by its type (% vs. points)."""
    if col in PCT_METRICS:
        return fmt_pct(x)
    return fmt_num(x)


def pretty_name(alias: str, names: dict) -> str:
    full = names.get(alias)
    return f"{full} ({alias})" if full else alias


@st.cache_data(show_spinner=False)
def get_level_weights():
    """Cached L2-vs-L3 metric weighting box from the Team Details sheet."""
    try:
        return sc.load_level_weights()
    except Exception:
        return pd.DataFrame()


def _fmt_weight(v):
    """Weights are stored as fractions (0.4) -> show as % ; pass text through."""
    if pd.isna(v):
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f * 100:.0f}%"


def render_level_criteria():
    """Show the manager's L2 vs L3 metric-weighting box so the team can see
    how scoring differs by level."""
    weights = get_level_weights()
    if weights is None or weights.empty:
        return

    with st.expander("ℹ️ Scoring criteria — how L2 vs L3 metrics differ", expanded=False):
        st.caption(
            "Weighting of each metric toward the overall score, by level. "
            "Maintained on the Team Details sheet."
        )
        disp = weights.copy()
        # Format every level column (everything except the Metric name) as %.
        for col in disp.columns:
            if col.strip().lower() == "metric":
                continue
            disp[col] = disp[col].map(_fmt_weight)
        st.dataframe(disp, hide_index=True, use_container_width=True)


# --------------------------------------------------------------------------
# Login gate
# --------------------------------------------------------------------------
def login_view():
    st.title("📊 Lead Ops Scorecard")
    st.caption("Sign in with your alias and personal password.")

    passwords = _get_passwords()

    with st.form("login"):
        alias = st.text_input("Your alias", placeholder="e.g. qrishraj")
        password = st.text_input("Your password", type="password")
        submitted = st.form_submit_button("View my scorecard")

    if submitted:
        alias = (alias or "").strip().lower()

        if not passwords:
            st.error(
                "Logins aren't configured yet. Ask the admin to add the "
                "[passwords] section to the app secrets."
            )
            return

        # Identity is proven ONLY if the alias has a password AND it matches.
        # This is what stops someone logging in as a colleague.
        expected = passwords.get(alias)
        if expected is not None and password == expected:
            st.session_state["alias"] = alias
            st.rerun()
        else:
            st.error("Incorrect alias or password.")

    st.info(
        "You will only be able to see your own scorecard. "
        "Managers can view the whole team."
    )


# --------------------------------------------------------------------------
# Scorecard rendering
# --------------------------------------------------------------------------
def render_person(df_person: pd.DataFrame, alias: str, names: dict,
                  month: str | None = None):
    st.subheader(f"Scorecard — {pretty_name(alias, names)}")

    if df_person.empty:
        st.warning("No scorecard data found for this alias yet.")
        return

    df_person = df_person.sort_values("month", key=lambda s: s.map(
        {m: i for i, m in enumerate(sc.MONTH_ORDER)}
    ))

    # Headline metrics. When a specific month is selected, headline that month
    # and compare against the month before it; otherwise headline the latest.
    if month and month != ALL_MONTHS:
        row_match = df_person[df_person["month"] == month]
        if row_match.empty:
            st.warning(f"No scorecard data for **{month}** yet.")
            return
        months_present = list(df_person["month"])
        focus_idx = months_present.index(month)
        focus = df_person.iloc[focus_idx]
        prev = df_person.iloc[focus_idx - 1] if focus_idx > 0 else None
    else:
        focus = df_person.iloc[-1]
        prev = df_person.iloc[-2] if len(df_person) > 1 else None

    c1, c2, c3 = st.columns(3)
    with c1:
        delta = None
        if prev is not None and not pd.isna(prev["overall"]) and not pd.isna(focus["overall"]):
            delta = f"{(focus['overall'] - prev['overall']) * 100:+.1f} pts"
        st.metric(f"Overall ({focus['month']})", fmt_pct(focus["overall"]), delta)
    with c2:
        st.metric("Level", str(focus.get("level", "—")))
    with c3:
        sr = focus.get("stack_rank")
        st.metric("Stack Rank", "—" if pd.isna(sr) else str(int(sr)))

    st.divider()

    # Overall trend
    st.markdown("#### Overall score — month on month")
    trend = df_person.set_index("month")["overall"]
    st.line_chart(trend, height=260, use_container_width=True)

    # Metric breakdown trends. Percentage metrics and point-based metrics use
    # different scales, so plot them on separate charts (showing the ACTUAL
    # values from the scorecard).
    pct_metrics = [c for c in METRIC_COLS if c in PCT_METRICS]
    point_metrics = [c for c in METRIC_COLS if c in POINT_METRICS]

    if pct_metrics:
        st.markdown("#### Actual % metrics — month on month")
        st.line_chart(
            df_person.set_index("month")[pct_metrics],
            height=280, use_container_width=True,
        )
    if point_metrics:
        st.markdown("#### Actual point metrics — month on month")
        st.line_chart(
            df_person.set_index("month")[point_metrics],
            height=280, use_container_width=True,
        )

    # Detailed table — all months, or just the selected month.
    if month and month != ALL_MONTHS:
        st.markdown(f"#### Details — {month} (Actual values)")
        df_table = df_person[df_person["month"] == month]
    else:
        st.markdown("#### Details (Actual values)")
        df_table = df_person
    show = df_table[["month", "level", "overall", "stack_rank"] + METRIC_COLS].copy()
    show["overall"] = show["overall"].map(fmt_pct)
    for col in METRIC_COLS:
        show[col] = show[col].map(lambda v, c=col: fmt_metric(c, v))
    show["stack_rank"] = show["stack_rank"].map(
        lambda v: "—" if pd.isna(v) else str(int(v))
    )
    show = show.rename(columns={
        "month": "Month", "level": "Level",
        "overall": "Overall", "stack_rank": "Stack Rank",
    })
    st.dataframe(show, hide_index=True, use_container_width=True)


def render_team_overview(df: pd.DataFrame, names: dict, month: str | None = None):
    st.subheader("Team overview")
    st.caption("Overall score by month across the whole team.")

    pivot = df.pivot_table(
        index="month", columns="alias", values="overall", aggfunc="mean"
    )
    pivot = pivot.reindex([m for m in sc.MONTH_ORDER if m in pivot.index])
    st.line_chart(pivot, height=340, use_container_width=True)

    # Leaderboard for the selected month (or the latest month by default).
    months_present = [m for m in sc.MONTH_ORDER if m in df["month"].unique()]
    if not months_present:
        return

    if month and month != ALL_MONTHS and month in months_present:
        board_month = month
    else:
        board_month = months_present[-1]

    st.markdown(f"#### Leaderboard — {board_month}")
    latest = df[df["month"] == board_month].copy()
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
    st.dataframe(board, hide_index=True, use_container_width=True)


# --------------------------------------------------------------------------
# Meeting notes (manager only): compose a 1:1 summary and draft it in Outlook
# --------------------------------------------------------------------------
EMAIL_DOMAIN = "amazon.com"  # associate email = <alias>@amazon.com


def associate_email(alias: str) -> str:
    return f"{alias.strip().lower()}@{EMAIL_DOMAIN}"


def _latest_row(df: pd.DataFrame, alias: str):
    """Latest month's scorecard row for an alias (or None)."""
    sub = df[df["alias"] == alias].copy()
    if sub.empty:
        return None
    sub = sub.sort_values("month", key=lambda s: s.map(
        {m: i for i, m in enumerate(sc.MONTH_ORDER)}
    ))
    return sub.iloc[-1]


def build_performance_summary(df: pd.DataFrame, alias: str, names: dict):
    """Return (plain_text, html, auto_blurb) for the latest-month performance.

    The caller shows auto_blurb as an editable default; plain_text/html are the
    metric table rendered for the two email formats.
    """
    row = _latest_row(df, alias)
    if row is None:
        return "", "", ""

    month = row["month"]
    level = str(row.get("level", "—"))
    overall = row["overall"]

    # Metric rows (Actual values), formatted by type.
    metric_lines = []
    html_rows = []
    for col in METRIC_COLS:
        val = fmt_metric(col, row.get(col))
        metric_lines.append(f"  {col}: {val}")
        html_rows.append(
            f"<tr><td style='padding:4px 10px;border:1px solid #ddd'>{col}</td>"
            f"<td style='padding:4px 10px;border:1px solid #ddd'>{val}</td></tr>"
        )

    sr = row.get("stack_rank")
    sr_txt = "—" if pd.isna(sr) else str(int(sr))

    plain = (
        f"Performance summary ({month})\n"
        f"  Level: {level}\n"
        f"  Overall: {fmt_pct(overall)}\n"
        f"  Stack Rank: {sr_txt}\n"
        + "\n".join(metric_lines)
    )

    html = (
        f"<h3 style='margin-bottom:6px'>Performance summary &mdash; {month}</h3>"
        f"<p style='margin:2px 0'><b>Level:</b> {level} &nbsp; "
        f"<b>Overall:</b> {fmt_pct(overall)} &nbsp; "
        f"<b>Stack Rank:</b> {sr_txt}</p>"
        "<table style='border-collapse:collapse;margin-top:6px'>"
        "<tr><th style='padding:4px 10px;border:1px solid #ddd;text-align:left'>Metric</th>"
        "<th style='padding:4px 10px;border:1px solid #ddd;text-align:left'>Actual</th></tr>"
        + "".join(html_rows) +
        "</table>"
    )

    name = pretty_name(alias, names)
    blurb = (
        f"{name} is at level {level} with an overall score of {fmt_pct(overall)} "
        f"for {month} (stack rank {sr_txt}). "
        "Overall performance has been consistent; see the metric breakdown above "
        "and the discussion points below."
    )
    return plain, html, blurb


def _section(title: str, body: str) -> str:
    """Plain-text section (skipped if body is blank)."""
    body = (body or "").strip()
    if not body:
        return ""
    return f"\n\n{title}\n{'-' * len(title)}\n{body}"


def _html_section(title: str, body: str) -> str:
    body = (body or "").strip()
    if not body:
        return ""
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe = safe.replace("\n", "<br>")
    return f"<h3 style='margin-bottom:4px'>{title}</h3><p style='margin-top:0'>{safe}</p>"


def build_email_plain(subject, perf_plain, discussion, strengths, actions, extra):
    parts = [perf_plain] if perf_plain else []
    parts.append(_section("Discussion Points", discussion))
    parts.append(_section("Strengths & Areas to Improve", strengths))
    parts.append(_section("Action Items & Next Steps", actions))
    parts.append(_section("Additional Points", extra))
    return "".join(p for p in parts if p).strip() or subject


def build_email_html(perf_html, discussion, strengths, actions, extra):
    body = [perf_html] if perf_html else []
    body.append(_html_section("Discussion Points", discussion))
    body.append(_html_section("Strengths &amp; Areas to Improve", strengths))
    body.append(_html_section("Action Items &amp; Next Steps", actions))
    body.append(_html_section("Additional Points", extra))
    inner = "".join(b for b in body if b)
    return (
        "<html><body style='font-family:Segoe UI,Arial,sans-serif;"
        "font-size:14px;color:#222'>" + inner + "</body></html>"
    )


def build_eml(to_addr, subject, html_body, text_body):
    """Build a .eml (RFC 822) draft Outlook can open: double-click -> opens as
    an unsent message you review and send."""
    import email.message
    msg = email.message.EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["X-Unsent"] = "1"  # tells Outlook to open as a composable draft
    msg.set_content(text_body or " ")
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    return msg.as_bytes()


def mailto_link(to_addr, subject, body):
    from urllib.parse import quote
    return (f"mailto:{quote(to_addr)}?subject={quote(subject)}"
            f"&body={quote(body)}")


def meeting_notes_view():
    df, names = get_data()

    top = st.columns([1, 6])
    with top[0]:
        if st.button("← Back"):
            st.session_state["page"] = "dashboard"
            st.rerun()
    st.title("📧 Send Meeting Notes")
    st.caption("Compose a 1:1 meeting summary, then draft it in Outlook to review and send.")

    all_aliases = sorted(df["alias"].unique())
    alias_options = [pretty_name(a, names) for a in all_aliases]

    # Selections OUTSIDE the form so the performance summary can auto-update.
    c1, c2 = st.columns(2)
    with c1:
        picked = st.selectbox(
            "Associate ID", alias_options,
            help="Pick an associate, or type their alias.",
        )
    with c2:
        meeting_date = st.date_input("Meeting date", value=date.today())

    target_alias = (picked.split("(")[-1].rstrip(")").strip()
                    if "(" in picked else picked)
    to_addr = associate_email(target_alias)

    default_subject = f"1:1 Meeting Summary - {target_alias}"
    subject = st.text_input("Subject", value=default_subject)

    # Auto-built performance summary (latest month) for this associate.
    perf_plain, perf_html, auto_blurb = build_performance_summary(df, target_alias, names)

    st.markdown("#### Performance summary (auto-added, latest month)")
    if perf_plain:
        st.caption(f"To: {to_addr}")
        row = _latest_row(df, target_alias)
        show = pd.DataFrame({
            "Metric": METRIC_COLS,
            "Actual": [fmt_metric(c, row.get(c)) for c in METRIC_COLS],
        })
        meta = st.columns(3)
        meta[0].metric(f"Overall ({row['month']})", fmt_pct(row["overall"]))
        meta[1].metric("Level", str(row.get("level", "—")))
        sr = row.get("stack_rank")
        meta[2].metric("Stack Rank", "—" if pd.isna(sr) else str(int(sr)))
        st.dataframe(show, hide_index=True, use_container_width=True)
    else:
        st.info("No scorecard data found for this associate yet.")

    perf_blurb = st.text_area(
        "Performance summary notes (auto-drafted — edit as needed)",
        value=auto_blurb, height=90,
    )

    st.divider()
    st.markdown("#### Your notes (all optional)")
    discussion = st.text_area("Discussion Points", height=120,
                              placeholder="What you discussed with the associate...")
    strengths = st.text_area("Strengths & Areas to Improve", height=120)
    actions = st.text_area("Action Items & Next Steps", height=120)
    extra = st.text_area("Additional points", height=90)

    # Combine the auto blurb with the metric table for the email body.
    perf_plain_full = (perf_plain + ("\n\n" + perf_blurb if perf_blurb.strip() else "")) if perf_plain else perf_blurb
    perf_html_full = perf_html + (_html_section("Summary", perf_blurb) if perf_blurb.strip() else "") if perf_html else _html_section("Summary", perf_blurb)

    text_body = build_email_plain(subject, perf_plain_full, discussion,
                                  strengths, actions, extra)
    html_body = build_email_html(perf_html_full, discussion, strengths, actions, extra)

    # Prepend the meeting date to the body.
    date_line = f"Meeting date: {meeting_date:%d %b %Y}\n\n"
    text_body = date_line + text_body
    html_body = html_body.replace(
        "<body style='font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#222'>",
        "<body style='font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#222'>"
        f"<p><b>Meeting date:</b> {meeting_date:%d %b %Y}</p>",
    )

    st.divider()
    st.markdown("#### Draft the email")
    st.caption("Nothing is sent automatically. Both options open a DRAFT in Outlook "
               "for you to review and send.")

    b1, b2 = st.columns(2)
    with b1:
        st.link_button(
            "📧 Open draft in Outlook (mailto)",
            mailto_link(to_addr, subject, text_body),
            use_container_width=True,
        )
        st.caption("Opens your mail client with a plain-text draft pre-filled.")
    with b2:
        eml = build_eml(to_addr, subject, html_body, text_body)
        safe_alias = target_alias or "associate"
        st.download_button(
            "⬇️ Download Outlook draft (.eml)",
            data=eml,
            file_name=f"1-1_summary_{safe_alias}_{meeting_date:%Y%m%d}.eml",
            mime="message/rfc822",
            use_container_width=True,
        )
        st.caption("Downloads a formatted draft (with the metric table). "
                   "Double-click it to open in Outlook as an unsent message.")


def dashboard_view():
    df, names = get_data()
    alias = st.session_state["alias"]
    is_manager = alias in MANAGER_ALIASES

    with st.sidebar:
        st.markdown(f"**Signed in as**\n\n`{alias}`" + ("  👑 Manager" if is_manager else ""))
        if st.button("Sign out"):
            st.session_state.pop("alias", None)
            st.rerun()
        st.divider()

        # Month-on-month filter (available to everyone). "All months" keeps the
        # full history view; picking a month focuses that month's scorecard.
        months_present = [m for m in sc.MONTH_ORDER if m in df["month"].unique()]
        month_options = [ALL_MONTHS] + months_present
        selected_month = st.selectbox(
            "Month", month_options,
            index=len(month_options) - 1 if months_present else 0,
            help="Pick a month to view that month's scorecard, or 'All months' "
                 "for the month-on-month history.",
        )

        if is_manager:
            st.divider()
            st.markdown("### Manager view")
            all_aliases = sorted(df["alias"].unique())
            options = ["— Team overview —"] + [pretty_name(a, names) for a in all_aliases]
            choice = st.selectbox("View scorecard for", options)
        else:
            choice = None

    st.title("📊 Lead Ops Scorecard")

    # Scoring criteria (L2 vs L3) — visible to everyone, collapsed by default.
    render_level_criteria()

    if is_manager:
        if choice == "— Team overview —":
            render_team_overview(df, names, month=selected_month)
        else:
            # choice looks like "Full Name (alias)" or just "alias"
            target = choice.split("(")[-1].rstrip(")").strip() if "(" in choice else choice
            render_person(df[df["alias"] == target], target, names, month=selected_month)
    else:
        render_person(df[df["alias"] == alias], alias, names, month=selected_month)

    # Manager-only: compose and draft a 1:1 meeting summary email.
    if is_manager:
        st.divider()
        if st.button("📧 Send Meeting Notes", use_container_width=True):
            st.session_state["page"] = "meeting_notes"
            st.rerun()


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

    if "alias" not in st.session_state:
        login_view()
        return

    # Simple page routing. The meeting-notes page is manager-only.
    page = st.session_state.get("page", "dashboard")
    is_manager = st.session_state["alias"] in MANAGER_ALIASES
    if page == "meeting_notes" and is_manager:
        meeting_notes_view()
    else:
        st.session_state["page"] = "dashboard"
        dashboard_view()


if __name__ == "__main__":
    main()

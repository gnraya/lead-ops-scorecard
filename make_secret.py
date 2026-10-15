"""
Generate the Streamlit secret for the scorecard dashboard.

Produces a `secrets.toml` block containing:
  - scorecard_xlsx_b64 : the Excel data (base64), so it never lives in the repo
  - [passwords]        : a per-user password map (alias -> password)

The per-user passwords are what enforce "each person sees only their own
scorecard": a teammate cannot log in as someone else without that person's
password.

Run this whenever you:
  - update "Lead Ops Scorecard 2026.xlsx", or
  - add/remove a team member, or
  - want to (re)generate passwords.

Usage:
    py make_secret.py          # auto-generate passwords for everyone
It writes:
    secret_block.txt           # paste into Streamlit -> Settings -> Secrets
    passwords_to_share.csv     # alias,name,password  (hand these out privately)
"""
import base64
import os
import secrets
import string

import scorecard_data as sc

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, "Lead Ops Scorecard 2026.xlsx")
OUT = os.path.join(HERE, "secret_block.txt")
SHARE = os.path.join(HERE, "passwords_to_share.csv")

# The manager alias that can view the whole team.
MANAGER_ALIAS = "gnraya"

# ---------------------------------------------------------------------------
# Set FIXED passwords here if you want specific ones. Any alias not listed
# gets a random password generated for it. Example:
#   FIXED = {"gnraya": "MyManagerPass123", "harishzz": "Harish@2026"}
# ---------------------------------------------------------------------------
FIXED = {
    # "gnraya": "choose-your-manager-password",
}


def _random_password(n: int = 10) -> str:
    # Readable-ish: letters + digits, no ambiguous chars.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def main():
    # 1) Encode the workbook.
    with open(XLSX, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    # 2) Collect every alias that needs a login: all people in the data + manager.
    df = sc.load_scorecards()
    names = sc.display_name_map()
    aliases = sorted(set(df["alias"].unique()) | {MANAGER_ALIAS})

    # 3) Build the password map.
    pw_map = {}
    for a in aliases:
        pw_map[a] = FIXED.get(a, _random_password())

    # 4) Write the Streamlit secret block.
    lines = [f'scorecard_xlsx_b64 = "{b64}"', "", "[passwords]"]
    for a in aliases:
        lines.append(f'{a} = "{pw_map[a]}"')
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # 5) Write a hand-out sheet (alias, name, password) to share privately.
    with open(SHARE, "w", encoding="utf-8") as f:
        f.write("alias,name,password\n")
        for a in aliases:
            nm = "MANAGER" if a == MANAGER_ALIAS else names.get(a, "")
            nm = str(nm).replace(",", " ")
            f.write(f"{a},{nm},{pw_map[a]}\n")

    print(f"Secret written to: {OUT}")
    print(f"Password hand-out written to: {SHARE}")
    print(f"Aliases configured: {len(aliases)}")
    print("\nNext:")
    print("  1. Paste the CONTENTS of secret_block.txt into")
    print("     Streamlit app -> Manage app -> Settings -> Secrets -> Save.")
    print("  2. Share each person's password from passwords_to_share.csv")
    print("     with them privately (DM / email). Do NOT commit these files.")


if __name__ == "__main__":
    main()

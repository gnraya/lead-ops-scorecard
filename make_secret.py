"""
Generate the Streamlit secret for the scorecard data.

Run this whenever you update "Lead Ops Scorecard 2026.xlsx". It prints a
`secrets.toml` block you paste into the Streamlit app's Secrets panel
(App -> Settings -> Secrets). The data then lives privately in Streamlit,
never in the public GitHub repo.

Usage:
    py make_secret.py                 # writes secret_block.txt
"""
import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, "Lead Ops Scorecard 2026.xlsx")
OUT = os.path.join(HERE, "secret_block.txt")

# Change this to whatever you want the team password to be.
TEAM_PASSWORD = "LeadOps2026"


def main():
    with open(XLSX, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    block = (
        f'team_password = "{TEAM_PASSWORD}"\n'
        f'scorecard_xlsx_b64 = "{b64}"\n'
    )

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(block)

    print(f"Secret written to: {OUT}")
    print(f"xlsx size: {os.path.getsize(XLSX)} bytes; base64 chars: {len(b64)}")
    print("\nPaste the CONTENTS of secret_block.txt into:")
    print("  Streamlit app -> Manage app -> Settings -> Secrets")
    print("\nNOTE: secret_block.txt is git-ignored; do NOT commit it.")


if __name__ == "__main__":
    main()

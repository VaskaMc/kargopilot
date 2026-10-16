from pathlib import Path

path = Path("/opt/KargoPilot/app/config.py")
lines = path.read_text(encoding="utf-8").splitlines()
fixed = []
for line in lines:
    if line.startswith('HOST = " 127.0.0.1'):
        fixed.append('HOST = "127.0.0.1"')
        fixed.append('PORT = 48481')
    elif line.startswith("BASE_DIR = Path("):
        fixed.append('BASE_DIR = Path("/opt/KargoPilot/web_panel")')
    else:
        fixed.append(line)

path.write_text("\n".join(fixed) + "\n", encoding="utf-8")
print("SUCCESSFULLY_FIXED_CONFIG_PY")

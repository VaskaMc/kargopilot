import os
import re
import json

patterns = {
    'VPS_IP': re.compile(r'5\.191\.246\.134'),
    'PRIVATE_KEY': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'HARDCODED_JWT_SECRET': re.compile(r'(?i)(jwt_secret|secret_key)\s*=\s*[\'"][^\'"]+[\'"]'),
    'HARDCODED_PASSWORD': re.compile(r'(?i)(?:password|passwd|pwd)\s*[:=]\s*[\'"][^\'"]{6,}[\'"]'),
    'PERSONAL_PHONE': re.compile(r'\+994\s*77\s*634\s*63\s*10'),
    'SSH_PORT_1999': re.compile(r'-p\s+1999\b|port\s*[:=]\s*1999\b'),
    'RAW_SQL_FORMAT': re.compile(r'(?i)execute\s*\(\s*f[\'"]'),
    'UNESCAPED_SAFE_FILTER': re.compile(r'\|\s*safe\b'),
    'PERSONAL_FIN': re.compile(r'\b814CRM4\b'),
}

files = [line.strip() for line in os.popen('git ls-files').readlines() if line.strip()]
findings = []

for fpath in files:
    if not os.path.exists(fpath):
        continue
    try:
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            for idx, line in enumerate(lines):
                line_str = line.strip()
                for p_name, regex in patterns.items():
                    if regex.search(line_str):
                        findings.append({
                            'file': fpath,
                            'line': idx + 1,
                            'type': p_name,
                            'snippet': line_str[:120].encode('ascii', errors='replace').decode('ascii')
                        })
    except Exception as e:
        pass

with open('audit_results.json', 'w', encoding='utf-8') as out:
    json.dump(findings, out, indent=2)

print(f"Total findings: {len(findings)}")
by_type = {}
for item in findings:
    t = item['type']
    by_type[t] = by_type.get(t, 0) + 1

for t, count in by_type.items():
    print(f"  {t}: {count}")

print("\n--- CRITICAL LEAK FINDINGS ---")
for item in findings:
    if item['type'] in ('VPS_IP', 'SSH_PORT_1999', 'PERSONAL_PHONE', 'PERSONAL_FIN', 'PRIVATE_KEY', 'RAW_SQL_FORMAT'):
        print(f"[{item['type']}] {item['file']}:{item['line']} -> {item['snippet']}")

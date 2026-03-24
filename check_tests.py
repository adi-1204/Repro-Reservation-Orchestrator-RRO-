import sqlite3
conn = sqlite3.connect('rro_local.db')
c = conn.cursor()

print('=== BugTest rows for bug 402152 ===')
c.execute(
    'SELECT bt.test_name, bt.station_name, bt.build_version, bt.configuration, COUNT(*) as cnt '
    'FROM bug_tests bt JOIN bugs b ON bt.bug_id = b.id '
    "WHERE b.bug_code = '402152' "
    'GROUP BY bt.test_name, bt.station_name, bt.build_version, bt.configuration '
    'ORDER BY cnt DESC, bt.test_name'
)
rows = c.fetchall()
print(f'Total unique (name, station, build, config) combos: {len(rows)}')
for r in rows:
    dup_marker = ' *** DUPLICATE ***' if r[4] > 1 else ''
    print(f'  [{r[4]}x] {r[0][:60]!r} | station={r[1]} | build={r[2]} | config={r[3]}{dup_marker}')

print()
print('=== Total raw BugTest rows for 402152 ===')
c.execute(
    'SELECT COUNT(*) FROM bug_tests bt JOIN bugs b ON bt.bug_id = b.id '
    "WHERE b.bug_code = '402152'"
)
print(f'Raw count: {c.fetchone()[0]}')

# Check if same test_name appears with different params (same base name)
import re
print()
print('=== Base test names (params stripped) ===')
c.execute(
    'SELECT bt.test_name FROM bug_tests bt JOIN bugs b ON bt.bug_id = b.id '
    "WHERE b.bug_code = '402152'"
)
base_counts = {}
for (name,) in c.fetchall():
    base = re.split(r'\s+--', name)[0].strip()
    base_counts[base] = base_counts.get(base, 0) + 1
for base, cnt in sorted(base_counts.items(), key=lambda x: -x[1]):
    marker = ' <<< REPEATED' if cnt > 1 else ''
    print(f'  {cnt}x  {base}{marker}')

conn.close()

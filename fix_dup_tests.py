import sqlite3, re

conn = sqlite3.connect('rro_local.db')
c = conn.cursor()

c.execute("SELECT id FROM bugs WHERE bug_code='402152'")
row = c.fetchone()
if not row:
    print('Bug 402152 not found')
    exit()
bug_id = row[0]

c.execute('SELECT id, test_name, station_name, build_version FROM bug_tests WHERE bug_id=?', (bug_id,))
tests = c.fetchall()
print(f'Before: {len(tests)} rows')

seen = set()
to_delete = []
for row_id, test_name, station, build in tests:
    # Strip CLI args after .py
    base = re.split(r'(?<=\.py)\s+', test_name, maxsplit=1)[0].strip()
    key = (base, station or '', build or '')
    if key in seen:
        to_delete.append(row_id)
        print(f'  DELETE duplicate: {test_name!r}')
    else:
        seen.add(key)
        if base != test_name:
            c.execute('UPDATE bug_tests SET test_name=? WHERE id=?', (base, row_id))
            print(f'  RENAME: {test_name!r} -> {base!r}')

for row_id in to_delete:
    c.execute('DELETE FROM bug_tests WHERE id=?', (row_id,))

conn.commit()
c.execute('SELECT COUNT(*) FROM bug_tests WHERE bug_id=?', (bug_id,))
print(f'After: {c.fetchone()[0]} rows')
conn.close()

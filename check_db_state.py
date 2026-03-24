import sqlite3
conn = sqlite3.connect('rro_local.db')
c = conn.cursor()

print('=== Workgroups ===')
c.execute('SELECT id, Name, Release_Version, Status FROM "Workgroup_Schema"')
for r in c.fetchall():
    print(f'  id={r[0]} name={r[1]!r} release_version={r[2]!r} status={r[3]}')

print()
print('=== Bugs (resource_group) ===')
c.execute('SELECT id, bug_code, resource_group, bug_type FROM bugs')
for r in c.fetchall():
    print(f'  id={r[0]} code={r[1]} resource_group={r[2]!r} type={r[3]}')

print()
print('=== All tables ===')
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in c.fetchall():
    c2 = conn.cursor()
    c2.execute(f'SELECT COUNT(*) FROM "{r[0]}"')
    cnt = c2.fetchone()[0]
    print(f'  {r[0]}: {cnt} rows')

conn.close()

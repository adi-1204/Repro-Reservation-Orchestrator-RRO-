import sqlite3
conn = sqlite3.connect('rro_local.db')
c = conn.cursor()

print('=== REPRO BUGS + MLAnalysis ===')
c.execute(
    'SELECT b.id, b.bug_code, b.bug_type, m.repro_actions, m.generated_at '
    'FROM bugs b LEFT JOIN ml_analysis m ON b.id = m.bug_id '
    "WHERE b.bug_type = 'repro'"
)
for row in c.fetchall():
    ra = (row[3] or '')[:80] if row[3] else 'NULL'
    print(f'  Bug {row[1]} (id={row[0]}): repro_actions={repr(ra)}, generated={row[4]}')

print()
print('=== BugComment counts per repro bug ===')
c.execute(
    'SELECT b.bug_code, COUNT(bc.id) '
    'FROM bugs b LEFT JOIN bug_comments bc ON b.id = bc.bug_id '
    "WHERE b.bug_type = 'repro' "
    'GROUP BY b.id'
)
for row in c.fetchall():
    print(f'  Bug {row[0]}: {row[1]} comments in DB')

conn.close()

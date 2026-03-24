"""
Fix any bugs whose resource_group doesn't match any workgroup's release_version.
This can happen if bugs were ingested before the cf_build_id fix.
"""
import sqlite3
conn = sqlite3.connect('rro_local.db')
c = conn.cursor()

# Check for orphaned bugs (resource_group doesn't match any workgroup)
c.execute('''
    SELECT b.id, b.bug_code, b.resource_group
    FROM Bugs b
    WHERE b.resource_group NOT IN (SELECT Release_Version FROM Workgroup_Schema)
''')
orphans = c.fetchall()
if orphans:
    print(f'Found {len(orphans)} orphaned bug(s) with no matching workgroup:')
    for r in orphans:
        print(f'  Bug {r[1]} (id={r[0]}): resource_group={r[2]!r}')
    ids = [r[0] for r in orphans]
    # Delete child rows first
    for table, col in [('ML_Analysis', 'bug_id'), ('Bug_Comments', 'bug_id'),
                        ('Bug_Tests', 'bug_id'), ('Bug_stations', 'bug_id')]:
        c.execute(f'DELETE FROM "{table}" WHERE {col} IN ({",".join("?" * len(ids))})', ids)
        print(f'  Deleted {c.rowcount} rows from {table}')
    c.execute(f'DELETE FROM Bugs WHERE id IN ({",".join("?" * len(ids))})', ids)
    print(f'  Deleted {c.rowcount} bugs')
    conn.commit()
    print('Done.')
else:
    print('No orphaned bugs found — DB is clean.')

conn.close()

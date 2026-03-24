import sqlite3
conn = sqlite3.connect('rro_local.db')
c = conn.cursor()

c.execute(
    "UPDATE bug_tests SET number_of_nodes=2, configuration='N2' "
    "WHERE test_name='BasicIO.py' AND (number_of_nodes IS NULL OR configuration IS NULL)"
)
print('Updated rows:', c.rowcount)
conn.commit()

c.execute("SELECT test_name, station_name, build_version, configuration FROM bug_tests WHERE test_name='BasicIO.py'")
for r in c.fetchall():
    print(r)
conn.close()

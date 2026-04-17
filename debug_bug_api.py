from app import create_app
from app.models.bug import Bug
import traceback

app = create_app()
with app.app_context():
    user_id = 2  # Akshay
    try:
        query = Bug.query.filter(Bug.engineer_id == user_id)
        bugs = query.all()
        print(f'Query OK, got {len(bugs)} bugs')
        for b in bugs:
            data = {
                'id': b.bug_id,
                'bug_name': b.bug_name,
                'engineer_name': (
                    (b.engineer.first_name + ' ' + (b.engineer.last_name or '')).strip()
                    if b.engineer else 'Unassigned'
                ),
                'priority': b.priority,
                'status': b.status,
                'engineer': {
                    'name': b.engineer.full_name if b.engineer else 'Unassigned',
                    'initials': (
                        (b.engineer.first_name[0] + b.engineer.last_name[0]).upper()
                        if b.engineer else '--'
                    ),
                    'color': '#7c3aed'
                },
                'component': b.component or '',
                'tests': [t.test_name for t in b.tests],
                'stations': [s.station_name for s in b.stations],
                'build': b.build_id
            }
            print(f'Bug {b.bug_id}: OK - type={b.bug_type}')
    except Exception as e:
        traceback.print_exc()

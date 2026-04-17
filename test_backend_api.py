"""Test backend API endpoints"""
from app import create_app
import json

app = create_app()

with app.test_client() as client:
    print("═" * 70)
    print("  BACKEND API ENDPOINT TEST")
    print("═" * 70)
    
    # 1. Test /api/bugs/stats
    print("\n1. GET /api/bugs/stats:")
    response = client.get('/api/bugs/stats')
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print("   Expected: Need authentication")
    elif response.status_code == 200:
        data = response.get_json()
        print(f"   Total Bugs: {data.get('totalBugs')}")
        print(f"   Repro: {data.get('reproBugs')}")
        print(f"   Test: {data.get('testBugs')}")
        print(f"   Pending Actions: {data.get('pendingActions')}")
        print(f"   Running: {data.get('runningBugs')}")
        print(f"   Completed: {data.get('completedBugs')}")
    
    # 2. Test /api/bugs
    print("\n2. GET /api/bugs:")
    response = client.get('/api/bugs')
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print("   Expected: Need authentication")
    elif response.status_code == 200:
        data = response.get_json()
        print(f"   Repro bugs: {len(data.get('repro', []))}")
        print(f"   Test bugs: {len(data.get('test', []))}")
    
    # 3. Test /api/auth/me
    print("\n3. GET /api/auth/me:")
    response = client.get('/api/auth/me')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.get_json()
        print(f"   User: {data}")
    else:
        print("   Expected: 401 without auth")
    
    # 4. Test database query directly
    print("\n4. DIRECT DATABASE QUERY:")
    from app.models.bug import Bug
    from app.extensions import db
    
    with app.app_context():
        bugs = Bug.query.all()
        print(f"   Total bugs in DB: {len(bugs)}")
        
        repro_bugs = Bug.query.filter_by(bug_type='repro').count()
        test_bugs = Bug.query.filter_by(bug_type='test').count()
        print(f"   Repro type: {repro_bugs}")
        print(f"   Test type: {test_bugs}")
        
        from sqlalchemy import or_
        pending_actions = Bug.query.filter(
            or_(Bug.bug_type == 'repro', Bug.status == 'pending')
        ).count()
        print(f"   Pending Actions (repro OR open): {pending_actions}")
        
        # Check null values
        null_component = Bug.query.filter(Bug.component.is_(None)).count()
        print(f"   NULL components: {null_component}")

print("\n" + "═" * 70)
print("  API TEST COMPLETE")
print("═" * 70)

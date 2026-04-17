from app import create_app, db
from app.models.bug import Bug
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from app.models.user import User
from app.models.bug_tests import BugTest
from app.models.bug_comments import BugComment
from app.models.ml_analysis import MLAnalysis

app = create_app()
with app.app_context():
    print('=== Workgroups ===')
    for wg in Workgroup.query.all():
        print(f'  id={wg.id} name={wg.name!r} release_version={wg.release_version!r} status={wg.status}')

    print()
    print('=== Bugs → Workgroup link ===')
    bugs = Bug.query.all()
    null_wg = [b for b in bugs if b.workgroup_id is None]
    print(f'  Total bugs: {len(bugs)}')
    print(f'  Bugs WITH workgroup_id: {len(bugs) - len(null_wg)}')
    print(f'  Bugs missing workgroup_id: {len(null_wg)}')

    print()
    print('=== Bugs → Engineer link ===')
    null_eng = [b for b in bugs if b.engineer_id is None]
    print(f'  Bugs WITH engineer_id: {len(bugs) - len(null_eng)}')
    print(f'  Bugs missing engineer_id: {len(null_eng)}')

    print()
    print('=== Workgroup Assignments ===')
    for wa in WorkgroupAssignment.query.all():
        print(f'  assignment_id={wa.id} engineer={wa.employee.email!r} workgroup={wa.workgroup.name!r}')

    print()
    print('=== Row counts ===')
    print(f'  Bugs: {Bug.query.count()}')
    print(f'  Bug_Tests: {BugTest.query.count()}')
    print(f'  Bug_Comments: {BugComment.query.count()}')
    print(f'  ML_Analysis: {MLAnalysis.query.count()}')
    print(f'  Users: {User.query.count()}')
    print(f'  Workgroups: {Workgroup.query.count()}')
    print(f'  Workgroup_Assignments: {WorkgroupAssignment.query.count()}')

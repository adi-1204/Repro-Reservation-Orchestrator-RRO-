# Engineer Assignment & Bug Management Guide

## Overview
This document explains how engineers are assigned to bugs in the RRO (Reliability and Release Operations) Management System.

## Database Schema
- **Users Table**: Stores user accounts with `ID` (auto-increment), `email`, `role` (Manager/Engineer), `first_name`, `last_name`
- **Bugs Table**: Each bug has an `engineer_id` foreign key that references `Users.ID`
- **Workgroup_Schema**: Links managers to workgroups; `workgroup_assignments` links engineers to workgroups
- **Bug Status**: Enum field with values: `pending`, `running`, `completed`

## Engineer Assignment Workflow

### 1. **User Registration**
When a new engineer registers:
```python
# app/routes/auth.py - register() function
new_user = User(
    first_name=first_name,
    last_name=last_name,
    email=email,
    password=hashed_password,
    role=role  # "Engineer" or "Manager"
)
db.session.add(new_user)
db.session.commit()
# Result: User ID is auto-generated (INT auto-increment)
```
- The system automatically creates a User record with a unique `ID`
- **No bugs are assigned yet** - bugs must be explicitly assigned or linked through workgroup assignments

### 2. **Assigning Engineers to Workgroups**
Managers can assign engineers to workgroups:
```python
# workgroup_assignments table
WorkgroupAssignment(
    workgroup_id=<workgroup_id>,
    employee_id=<engineer_user_id>  # FK to Users.ID
)
```
- This links an engineer to a specific workgroup
- Bugs with `build_id` matching the workgroup's `release_version` are scoped to this workgroup's engineers

### 3. **Assigning Bugs to Engineers**
Bugs can be assigned through:

#### **Option A: Direct Assignment** (via UI or manual update)
```python
bug.engineer_id = <user_id>  # FK to Users.ID
db.session.commit()
```

#### **Option B: Workgroup-Based Assignment**
- Bugs with `build_id == workgroup.release_version`
- AND `engineer_id` matching a workgroup member
- Are automatically displayed in that engineer's workgroup view

### 4. **Current Mock Data State**
All 23 ingested bugs currently have:
- `engineer_id = NULL` (unassigned)
- `workgroup_id = NULL` (not scoped to a workgroup)
- `build_id = "3.3.1.648"` (all same build)
- `status = "pending" | "running" | "completed"` (mapped from Bugzilla)

**To use the system:**
```
Step 1: Create Manager account
Step 2: Create Workgroup (Manager → Release Version = "3.3.1.648")
Step 3: Register Engineers and assign to Workgroup
Step 4: Assign bugs to engineers (engineer_id = <user_id>)
Step 5: Engineers see their assigned bugs in their dashboard/engineer_dashboard
```

## Status Filtering (Backend)

### Database Status Field
- `pending`: Originally OPEN in Bugzilla - bugs waiting for action
- `running`: Originally REPRODUCE in Bugzilla - bugs being investigated
- `completed`: Originally CLOSED/VERIFIED in Bugzilla - bugs resolved

### UI Display
The backend filters bugs by:
1. **Role-based access** (Engineer sees only their bugs, Manager sees workgroup bugs)
2. **Status filtering** (pending/running/completed counts in statistics)
3. **Workgroup filtering** (build version matching, engineer workspace membership)

### Pending Actions Display
Pending actions show bugs where `status = 'pending'`:
```python
# app/routes/bugDashboard.py - bug_stats()
pending = query.filter(Bug.status == "pending").count()
```

## Schema Cleanup Completed ✓

### Removed Redundant Columns
- **station_config**: Config stored in BugTest table, not needed on Bug
- **resource_group**: Mapped from build_id, duplicate metadata
- **summary**: Same as component field; consolidated

### Enhanced Columns (New)
- **product**: Bugzilla product category
- **component**: Component/sub-system
- **reporter**: Original bug reporter from Bugzilla
- **severity**: Bug severity level (trivial/normal/major/critical/enhancement)
- **whiteboard**: Bugzilla whiteboard metadata
- **developer_progress**: Development progress notes

### Data Status
```
✓ 23 bugs ingested
✓ 67 comments linked
✓ 79 tests extracted
✓ Status mapping applied
✓ All indexes created
✓ Schema validated
```

## Next Steps (For Using the System)

### To Assign Your 23 Bugs to Engineers:

**Option 1: Via Direct Database Update**
```sql
UPDATE Bugs 
SET engineer_id = <user_id> 
WHERE bug_code IN ('100001', '100002', ...);
```

**Option 2: Via Workgroup Assignment** (Recommended)
1. Create a Manager account
2. Create a workgroup with `release_version = "3.3.1.648"`
3. Create Engineer accounts and register them
4. Assign engineers to the workgroup
5. Manually assign bugs to engineers via UI

### Verification
Engineer assignment is confirmed when:
1. User registers with role = "Engineer"
2. User ID appears in Users table
3. Bug `engineer_id` FK points to that User ID
4. Bug is visible in Engineer's dashboard (with role-based filtering)
5. Status counts show in UI statistics

## Key Questions Answered

### Q: Will engineer_id be assigned properly when I register?
**A:** Yes. When you register a new user:
- A User record is created with auto-generated ID
- That ID can be used as `engineer_id` for bug assignments
- The system handles the foreign key relationship automatically
- Validation ensures `engineer_id` always references a valid User.ID

### Q: How do bugs show pending actions?
**A:** When `status = 'pending'` in the database:
- Backend counts them as `pendingActions` in statistics
- UI displays them as "Pending Actions" in the dashboard
- This reflects bugs marked as OPEN in the original Bugzilla data

### Q: Can I filter by status in the UI?
**A:** Currently, the backend returns all bugs for a user/workgroup and stats show:
- Total bugs
- Repro/Test split
- Pending/Running/Completed counts

**Enhancement:** Add `?status=pending` parameter to `/api/bugs` endpoint to filter server-side (optional).

## Summary
- ✓ Schema cleaned (redundant columns removed)
- ✓ Engineer assignment ready (foreign key relationships verified)
- ✓ Status tracking enabled (pending/running/completed)
- ✓ 23 bugs ready for assignment to engineers
- ✓ Workgroup scoping available for team-based management

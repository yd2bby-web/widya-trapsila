# WIDYA TRAPSILA v0.8.2 – Counseling Relationship Fix

Hotfix for SQLAlchemy startup failure caused by two foreign-key paths between `users` and `students`.

Changes:
- Explicitly sets `foreign_keys` on `User.student` and `Student.user` to use `users.student_id` only.
- Leaves `Student.counselor_user_id` as the separate counselor assignment reference.
- No database migration or Environment changes are required.

Install by replacing project files while preserving local `.git` and `.env`.


## v0.8.3 hotfix
- Added student database ID to the admin student list API response so counselor assignment submits the actual Student.id.

"""
Compatibility settings module.

Keep this file so any legacy command using `assignment_system.settings`
continues to work, while the real source of truth stays in
`django_assignment_system.settings`.
"""

from django_assignment_system.settings import *  # noqa: F401,F403


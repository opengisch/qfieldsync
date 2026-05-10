from qfieldsync.core.cloud_project import CloudProject


def can_delete_project(project: CloudProject) -> bool:
    return project.user_role == "admin"


def can_update_project(project: CloudProject) -> bool:
    return project.user_role in {"admin", "manager"}

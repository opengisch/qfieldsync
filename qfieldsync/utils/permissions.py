from qfieldsync.core.cloud_project import CloudProject


def can_change_project_owner(project: CloudProject) -> bool:
    if project.user_role == "admin":
        return True

    return False


def can_delete_project(project: CloudProject) -> bool:
    if project.user_role == "admin":
        return True

    return False

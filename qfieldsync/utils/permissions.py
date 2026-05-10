from qfieldsync.core.cloud_project import CloudProject


def can_delete_project(project: CloudProject) -> bool:
    return project.user_role == "admin"

import os

PROJECT_ROOT_ENV = "MOGRID_PROJECT_ROOT"


class PathEscapesProjectRoot(Exception):
    def __init__(self, path: str, root: str):
        self.path = path
        self.root = root
        super().__init__(f"프로젝트 폴더({root}) 밖의 경로는 사용할 수 없습니다: {path}")


def project_root() -> str:
    root = os.environ.get(PROJECT_ROOT_ENV) or os.getcwd()
    return os.path.realpath(root)


def resolve_path(path: str) -> str:
    root = project_root()
    target = os.path.realpath(os.path.join(root, path))
    try:
        outside = os.path.commonpath([target, root]) != root
    except ValueError:
        outside = True
    if outside:
        raise PathEscapesProjectRoot(path, root)
    return target

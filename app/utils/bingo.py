from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user_team import UserTeam
from app.models.bingo_config import BingoConfig
from app.models.user import User
from app import db

def get_completed_problem_ids_by_team(team_id):
    """
    获取某个团队所有成员（包括间谍）通过的题目 ID 列表。
    """
    # 获取该团队所有成员 ID（包括间谍）
    user_ids = db.session.query(UserTeam.user_id).filter_by(team_id=team_id).all()
    user_ids = [u[0] for u in user_ids]

    # 获取他们提交通过的所有 problem_id（只要 archived）
    problem_ids = db.session.query(Submission.problem_id)\
        .filter(Submission.user_id.in_(user_ids), Submission.status == "archived")\
        .distinct().all()

    return {pid[0] for pid in problem_ids}


def calc_bingo_for_team(team_id):
    """
    根据团队通过的题目 ID，判断该团队的 BINGO 数量。
    """
    config = BingoConfig.query.get(1)
    if not config:
        return 0
    matrix_size = config.matrix_size

    completed_ids = get_completed_problem_ids_by_team(team_id)
    all_problems = Problem.query.all()

    # 构造题目矩阵
    matrix = [[None for _ in range(matrix_size)] for _ in range(matrix_size)]
    for p in all_problems:
        matrix[p.row_index][p.col_index] = p.id

    bingo = 0

    # 横行
    for i in range(matrix_size):
        if all(matrix[i][j] in completed_ids for j in range(matrix_size)):
            bingo += 1

    # 纵列
    for j in range(matrix_size):
        if all(matrix[i][j] in completed_ids for i in range(matrix_size)):
            bingo += 1

    # 对角线
    if all(matrix[i][i] in completed_ids for i in range(matrix_size)):
        bingo += 1
    if all(matrix[i][matrix_size - 1 - i] in completed_ids for i in range(matrix_size)):
        bingo += 1

    return bingo

import numpy as np
import pandas as pd

from django.utils import timezone

from ..models import Assignment, Submission, Scores, CustomUser


def build_learning_df():
    """
    输出：
      df_student: 每个学生一行（student_id, submit_rate, avg_score, score_std, avg_early_hours）
      summary: 全局概览
    """
    students = CustomUser.objects.filter(is_teacher=False)
    assignments = Assignment.objects.all()
    total_students = students.count()
    total_assignments = assignments.count()

    # submissions
    subs = Submission.objects.values(
        "student_id",
        "assignment_id",
        "creat_at",
        "assignment__due_date",
    )
    df_sub = pd.DataFrame(list(subs))
    if not df_sub.empty:
        df_sub["creat_at"] = pd.to_datetime(df_sub["creat_at"])
        df_sub["assignment__due_date"] = pd.to_datetime(df_sub["assignment__due_date"])
        df_sub["hours_before_due"] = (
            df_sub["assignment__due_date"] - df_sub["creat_at"]
        ).dt.total_seconds() / 3600.0
        df_sub["hours_before_due"] = df_sub["hours_before_due"].clip(lower=-24, upper=24 * 365)

    # scores
    sc = Scores.objects.values("student_id", "assignment_id", "score")
    df_sc = pd.DataFrame(list(sc))
    if not df_sc.empty:
        df_sc["score"] = pd.to_numeric(df_sc["score"], errors="coerce")

    # overall submit rate
    if total_students > 0 and total_assignments > 0 and not df_sub.empty:
        submitted_pairs = df_sub[["student_id", "assignment_id"]].drop_duplicates().shape[0]
        overall_submit_rate = submitted_pairs / (total_students * total_assignments)
    else:
        overall_submit_rate = 0.0

    overall_avg_score = float(df_sc["score"].mean()) if not df_sc.empty else 0.0

    # per-student features
    if not df_sub.empty:
        sub_cnt = (
            df_sub.drop_duplicates(subset=["student_id", "assignment_id"])
            .groupby("student_id")
            .size()
        )
        avg_early = df_sub.groupby("student_id")["hours_before_due"].mean()
    else:
        sub_cnt = pd.Series(dtype=float)
        avg_early = pd.Series(dtype=float)

    if not df_sc.empty:
        avg_score = df_sc.groupby("student_id")["score"].mean()
        score_std = df_sc.groupby("student_id")["score"].std()
    else:
        avg_score = pd.Series(dtype=float)
        score_std = pd.Series(dtype=float)

    student_ids = list(students.values_list("id", flat=True))
    df_student = pd.DataFrame({"student_id": student_ids})
    df_student["submit_cnt"] = df_student["student_id"].map(sub_cnt).fillna(0.0)
    df_student["submit_rate"] = df_student["submit_cnt"] / (total_assignments if total_assignments else 1)
    df_student["avg_score"] = df_student["student_id"].map(avg_score).fillna(0.0)
    df_student["score_std"] = df_student["student_id"].map(score_std).fillna(0.0)
    df_student["avg_early_hours"] = df_student["student_id"].map(avg_early).fillna(0.0)

    summary = {
        "total_students": total_students,
        "total_assignments": total_assignments,
        "overall_submit_rate": overall_submit_rate,
        "overall_avg_score": overall_avg_score,
        "generated_at": timezone.now(),
    }
    return df_student, summary


def cluster_students(df_student, k=3):
    """
    输出：
      df_student: 添加 cluster, cluster_label, x, y
      cluster_summary: list[dict]
    """
    feats = df_student[["submit_rate", "avg_score", "score_std", "avg_early_hours"]].copy()

    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA

        X = feats.to_numpy(dtype=float)
        Xs = StandardScaler().fit_transform(X)

        km = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = km.fit_predict(Xs)

        pca = PCA(n_components=2, random_state=42)
        XY = pca.fit_transform(Xs)

        df_student = df_student.copy()
        df_student["cluster"] = labels
        df_student["x"] = XY[:, 0]
        df_student["y"] = XY[:, 1]

    except Exception:
        # 没装 sklearn 时降级
        df_student = df_student.copy()
        cond_a = (df_student["submit_rate"] >= 0.8) & (df_student["avg_score"] >= 85)
        cond_c = (df_student["submit_rate"] < 0.5) | (df_student["avg_score"] < 60)
        df_student["cluster"] = np.select([cond_a, cond_c], [0, 2], default=1)
        df_student["x"] = df_student["avg_score"]
        df_student["y"] = df_student["submit_rate"] * 100.0

    g = df_student.groupby("cluster").agg(
        n=("student_id", "count"),
        avg_score=("avg_score", "mean"),
        submit_rate=("submit_rate", "mean"),
        avg_early=("avg_early_hours", "mean"),
        score_std=("score_std", "mean"),
    ).reset_index()

    g["rank_score"] = g["avg_score"] * 0.7 + g["submit_rate"] * 100 * 0.3
    g = g.sort_values("rank_score", ascending=False).reset_index(drop=True)

    mapping = {}
    labels_text = ["A（稳定优秀）", "B（中等需关注）", "C（风险预警）"]
    for i, row in g.iterrows():
        mapping[int(row["cluster"])] = labels_text[i]

    df_student["cluster_label"] = df_student["cluster"].map(mapping)

    cluster_summary = (
        df_student.groupby("cluster_label")
        .agg(
            n=("student_id", "count"),
            avg_score=("avg_score", "mean"),
            submit_rate=("submit_rate", "mean"),
            avg_early=("avg_early_hours", "mean"),
            score_std=("score_std", "mean"),
        )
        .reset_index()
        .sort_values("n", ascending=False)
        .to_dict(orient="records")
    )

    return df_student, cluster_summary
import io

import numpy as np

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ..services.report_service import build_learning_df, cluster_students


@login_required
def learning_report_page(request):
    if not getattr(request.user, "is_teacher", False):
        return HttpResponse("Forbidden", status=403)

    df_student, summary = build_learning_df()
    return render(request, "teacher/learning_report.html", {"summary": summary})


@login_required
def learning_report_data(request):
    if not getattr(request.user, "is_teacher", False):
        return JsonResponse({"error": "Forbidden"}, status=403)

    df_student, summary = build_learning_df()
    df_student, cluster_summary = cluster_students(df_student, k=3)

    scatter_series = []
    for label in sorted(df_student["cluster_label"].unique()):
        part = df_student[df_student["cluster_label"] == label]
        points = part[["x", "y"]].to_numpy().tolist()
        scatter_series.append({
            "name": label,
            "type": "scatter",
            "data": points,
            "symbolSize": 10,
        })

    scores = df_student["avg_score"].astype(float).to_numpy()
    bins_score = [0, 60, 70, 80, 90, 100]
    hist_score, _ = np.histogram(scores, bins=bins_score)
    score_labels = ["0-60", "60-70", "70-80", "80-90", "90-100"]

    sr = (df_student["submit_rate"].astype(float) * 100.0).to_numpy()
    bins_sr = [0, 20, 40, 60, 80, 100]
    hist_sr, _ = np.histogram(sr, bins=bins_sr)
    sr_labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]

    return JsonResponse({
        "summary": {
            "total_students": summary["total_students"],
            "total_assignments": summary["total_assignments"],
            "overall_submit_rate": summary["overall_submit_rate"],
            "overall_avg_score": summary["overall_avg_score"],
            "generated_at": summary["generated_at"].strftime("%Y-%m-%d %H:%M:%S"),
        },
        "cluster_summary": cluster_summary,
        "scatter": {
            "x_name": "PCA-1",
            "y_name": "PCA-2",
            "series": scatter_series,
        },
        "histograms": {
            "score": {"labels": score_labels, "counts": hist_score.tolist()},
            "submit_rate": {"labels": sr_labels, "counts": hist_sr.tolist()},
        }
    })


@login_required
def learning_report_pdf(request):
    if not getattr(request.user, "is_teacher", False):
        return HttpResponse("Forbidden", status=403)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]

    font_candidates = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]

    pdf_font_name = None
    for p in font_candidates:
        try:
            pdfmetrics.registerFont(TTFont("CNFont", p))
            pdf_font_name = "CNFont"
            break
        except Exception:
            continue

    if pdf_font_name is None:
        pdf_font_name = "Helvetica"

    df_student, summary = build_learning_df()
    df_student, cluster_summary = cluster_students(df_student, k=3)

    img_buffers = []

    plt.figure()
    for label in sorted(df_student["cluster_label"].unique()):
        part = df_student[df_student["cluster_label"] == label]
        plt.scatter(part["x"], part["y"], label=label, s=25)
    plt.title("学生聚类（3类）")
    plt.legend()
    plt.tight_layout()
    buf_cluster = io.BytesIO()
    plt.savefig(buf_cluster, format="png", dpi=160)
    plt.close()
    buf_cluster.seek(0)
    img_buffers.append(("1. 学生聚类（3类）", buf_cluster, 260))

    plt.figure()
    score_vals = df_student["avg_score"].astype(float)
    plt.hist(score_vals, bins=10)
    plt.title("学生平均分分布")
    plt.xlabel("平均分")
    plt.ylabel("人数")
    plt.tight_layout()
    buf_score = io.BytesIO()
    plt.savefig(buf_score, format="png", dpi=160)
    plt.close()
    buf_score.seek(0)
    img_buffers.append(("2. 平均分分布", buf_score, 220))

    plt.figure()
    submit_rate = df_student["submit_rate"].astype(float) * 100.0
    plt.hist(submit_rate, bins=10)
    plt.title("提交率分布")
    plt.xlabel("提交率（%）")
    plt.ylabel("人数")
    plt.tight_layout()
    buf_submit = io.BytesIO()
    plt.savefig(buf_submit, format="png", dpi=160)
    plt.close()
    buf_submit.seek(0)
    img_buffers.append(("3. 提交率分布", buf_submit, 220))

    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    width, height = A4
    left = 50
    y = height - 50

    c.setFont(pdf_font_name, 16)
    c.drawString(left, y, "学情分析报告（全作业）")
    y -= 24

    c.setFont(pdf_font_name, 11)
    c.drawString(left, y, f"生成时间：{summary['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 18
    c.drawString(left, y, f"学生数：{summary['total_students']}    作业数：{summary['total_assignments']}")
    y -= 18
    c.drawString(left, y, f"总体提交率：{summary['overall_submit_rate']:.1%}    平均分：{summary['overall_avg_score']:.2f}")
    y -= 20

    for title, buf, img_h in img_buffers:
        if y < (img_h + 80):
            c.showPage()
            y = height - 50

        c.setFont(pdf_font_name, 12)
        c.drawString(left, y, title)
        y -= 10

        img = ImageReader(buf)
        c.drawImage(img, left, y - img_h, width=500, height=img_h, preserveAspectRatio=True, mask="auto")
        y -= (img_h + 20)

    if y < 160:
        c.showPage()
        y = height - 50

    c.setFont(pdf_font_name, 12)
    c.drawString(left, y, "4. 各类特征概览")
    y -= 18

    c.setFont(pdf_font_name, 10)
    c.drawString(left, y, "类别 | 人数 | 平均分 | 提交率 | 平均提前(h) | 波动(Std)")
    y -= 12
    c.drawString(left, y, "-" * 90)
    y -= 14

    for row in cluster_summary:
        line = (
            f"{row['cluster_label']} | "
            f"{int(row['n'])} | "
            f"{row['avg_score']:.1f} | "
            f"{row['submit_rate']:.1%} | "
            f"{row['avg_early']:.1f} | "
            f"{row['score_std']:.1f}"
        )
        c.drawString(left, y, line[:120])
        y -= 14
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont(pdf_font_name, 10)

    c.showPage()
    c.save()
    out.seek(0)

    resp = HttpResponse(out.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="learning_report.pdf"'
    return resp
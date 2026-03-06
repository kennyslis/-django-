import json
import re
import requests

from django.db.models import Avg, Count, Max, Min

from ..models import Assignment, Submission, Scores, CustomUser


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2:7b"


def call_ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 30) -> str:
    """
    调用本地 Ollama 模型
    """
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return (response.json().get("response") or "").strip()


def clean_json_response(raw: str) -> str:
    """
    清理 LLM 可能返回的 ```json ... ``` 包裹
    """
    s = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in s and "}" in s:
        s = s[s.find("{"): s.rfind("}") + 1]
    return s


# =========================================================
# 一、动态表单配置生成
# =========================================================
def generate_form_config(user_prompt: str):
    """
    AI 生成动态表单 JSON 配置
    """
    system_prompt = (
        "你是一个极其死板且精准的 Django 表单 JSON 生成器。请严格根据用户需求生成 JSON 数组。\n"
        "【字段识别规则】：\n"
        "1. 如果用户提到‘姓名’、‘学号’、‘心得’等，type 必须设为 'text' 或 'textarea'。\n"
        "2. 只要用户提到文件后缀（如 ipynb, zip），type 必须设为 'file'，并包含 'accept' 字段。\n"
        "3. 所有 label 必须使用中文。\n"
        "4. 用户没提到的字段绝对不要生成。\n"
        "5. 所有字段 name 统一固定为 'task'。\n"
        "只返回纯 JSON 数组，严禁 markdown 或解释。"
    )

    raw = call_ollama(f"{system_prompt}\n用户当前需求：{user_prompt}", timeout=30)
    clean = raw.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(clean)
    return parsed if isinstance(parsed, list) else [parsed]


# =========================================================
# 二、老师问答助手
# =========================================================
def student_name(u):
    return (
        getattr(u, "name", None)
        or getattr(u, "username", None)
        or getattr(u, "email", None)
        or f"用户{u.id}"
    )


def get_assignment_by_n(n: int):
    """
    第 n 次作业，默认按 id 升序
    """
    qs = Assignment.objects.all().order_by("id")
    items = list(qs[:n])
    return items[n - 1] if len(items) >= n else None


def rule_detect_intent(user_prompt: str):
    """
    规则优先识别数据库查询意图
    """
    q = (user_prompt or "").strip()

    # 问候/普通聊天，不走数据库
    chat_keywords = ["你好", "您好", "下午好", "早上好", "晚上好", "你是谁", "你能做什么", "介绍一下你自己"]
    if any(k in q for k in chat_keywords):
        return {"intent": "chat"}

    # 最难作业
    if ("哪个作业最难" in q) or ("作业最难" in q) or ("平均分最低" in q and "作业" in q):
        return {"intent": "hardest_assignment", "assignment_n": None, "top_n": None, "metric": "avg"}

    # 成绩最好
    if ("谁成绩最好" in q) or ("成绩最好" in q) or ("平均分最高" in q) or ("谁分数最高" in q):
        return {"intent": "top_scores", "assignment_n": None, "top_n": 10, "metric": "avg"}

    # 提交最多
    if ("谁交作业最多" in q) or ("谁提交最多" in q) or ("提交最多" in q):
        return {"intent": "top_submitters", "assignment_n": None, "top_n": 10, "metric": None}

    # 第N次作业...
    m = re.search(r"第\s*(\d+)\s*次", q)
    if m:
        n = int(m.group(1))

        if ("谁没交" in q) or ("没交" in q) or ("未交" in q) or ("没有交" in q):
            return {"intent": "missing_submission", "assignment_n": n, "top_n": None, "metric": None}

        if ("谁交了" in q) or ("谁提交了" in q) or ("交了" in q) or ("提交了" in q):
            return {"intent": "submitted_students", "assignment_n": n, "top_n": None, "metric": None}

        if ("平均分" in q) or ("最高分" in q) or ("最低分" in q) or ("成绩统计" in q) or ("统计" in q):
            return {"intent": "assignment_stats", "assignment_n": n, "top_n": None, "metric": "avg"}

    return None


def parse_teacher_query_with_llm(user_prompt: str):
    """
    先规则匹配，规则不命中再调用 LLM 做意图解析
    """
    intent_obj = rule_detect_intent(user_prompt)
    if intent_obj is not None:
        return intent_obj

    system_prompt = (
        "你是教学平台的“查询意图解析器”。把老师问题转换成严格 JSON，只输出 JSON。\n"
        "intent 只允许：\n"
        "missing_submission / submitted_students / top_submitters / top_scores / assignment_stats / hardest_assignment / chat\n"
        "JSON Schema：\n"
        "{\n"
        '  "intent": "<intent>",\n'
        '  "assignment_n": <int_or_null>,\n'
        '  "top_n": <int_or_null>,\n'
        '  "metric": "<avg|max|min|null>"\n'
        "}\n"
        "规则：\n"
        "- “第N次作业...” 必须给 assignment_n\n"
        "- “Top/前N/最多” 给 top_n，否则 null\n"
        "- hardest_assignment 表示“哪个作业最难/平均分最低”\n"
        "- top_scores 表示“谁成绩最好/平均分最高”\n"
        "- 如果是普通寒暄、介绍自己、能力说明，intent 输出 chat\n"
        "只输出 JSON，严禁解释。"
    )

    raw = call_ollama(f"{system_prompt}\n老师问题：{user_prompt}", timeout=30)
    return json.loads(clean_json_response(raw))


def chat_fallback_reply(user_prompt: str):
    """
    普通聊天兜底
    """
    prompt = (
        "你是一个高校课程作业管理系统的 AI 助教。\n"
        "你的语气要友好、简洁、自然。\n"
        "你主要帮助老师查询学生作业提交情况、成绩情况、学情分析。\n"
        "如果用户是在寒暄，就自然回应；如果用户问你能做什么，就简要介绍你的能力。\n"
        f"老师的问题：{user_prompt}\n"
        "请直接用中文回答："
    )

    try:
        answer = call_ollama(prompt, timeout=30)
        return answer
    except Exception:
        return "你好，我是作业管理系统的 AI 助教，可以帮你查询作业提交、成绩统计和学情分析。"


def execute_teacher_query(intent_obj, user_prompt=None):
    """
    执行老师查询，返回：
    {
      "reply": str,
      "table": dict | None,
      "chart": dict | None
    }
    """
    intent = intent_obj.get("intent")
    assignment_n = intent_obj.get("assignment_n")
    top_n = intent_obj.get("top_n") or 10

    students = CustomUser.objects.filter(is_teacher=False)

    table = None
    chart = None
    reply = ""

    # ------------------------
    # 普通聊天
    # ------------------------
    if intent == "chat":
        reply = chat_fallback_reply(user_prompt or "")
        return {"reply": reply, "table": None, "chart": None}

    # ------------------------
    # 第N次作业未提交
    # ------------------------
    if intent == "missing_submission":
        if not isinstance(assignment_n, int) or assignment_n <= 0:
            return {
                "reply": "我没识别出你问的是第几次作业。比如：第1次作业谁没交？",
                "table": None,
                "chart": None,
            }

        a = get_assignment_by_n(assignment_n)
        if not a:
            total = Assignment.objects.count()
            return {
                "reply": f"目前系统里只有 {total} 次作业，没有第 {assignment_n} 次。",
                "table": None,
                "chart": None,
            }

        submitted_ids = Submission.objects.filter(assignment=a).values_list("student_id", flat=True).distinct()
        missing = students.exclude(id__in=submitted_ids)
        names = [student_name(u) for u in missing]

        reply = f"第 {assignment_n} 次作业《{a.title}》未提交人数：{len(names)}"
        if names:
            rows = [[i + 1, n] for i, n in enumerate(names[:30])]
            table = {"columns": ["序号", "未提交学生"], "rows": rows}
            if len(names) > 30:
                reply += f"\n（仅展示前 30 人，剩余 {len(names) - 30} 人未展示）"

    # ------------------------
    # 第N次作业已提交
    # ------------------------
    elif intent == "submitted_students":
        if not isinstance(assignment_n, int) or assignment_n <= 0:
            return {
                "reply": "我没识别出你问的是第几次作业。比如：第2次作业谁交了？",
                "table": None,
                "chart": None,
            }

        a = get_assignment_by_n(assignment_n)
        if not a:
            total = Assignment.objects.count()
            return {
                "reply": f"目前系统里只有 {total} 次作业，没有第 {assignment_n} 次。",
                "table": None,
                "chart": None,
            }

        submitted = students.filter(submission__assignment=a).distinct()
        names = [student_name(u) for u in submitted]

        reply = f"第 {assignment_n} 次作业《{a.title}》已提交人数：{len(names)}"
        if names:
            rows = [[i + 1, n] for i, n in enumerate(names[:30])]
            table = {"columns": ["序号", "已提交学生"], "rows": rows}
            if len(names) > 30:
                reply += f"\n（仅展示前 30 人，剩余 {len(names) - 30} 人未展示）"

    # ------------------------
    # 谁提交最多
    # ------------------------
    elif intent == "top_submitters":
        agg = Submission.objects.values("student_id").annotate(cnt=Count("id")).order_by("-cnt")[:top_n]
        agg = list(agg)

        if not agg:
            reply = "系统里还没有任何提交记录。"
        else:
            ids = [x["student_id"] for x in agg]
            id2u = {u.id: u for u in students.filter(id__in=ids)}

            rows = []
            for i, x in enumerate(agg, 1):
                u = id2u.get(x["student_id"])
                rows.append([
                    i,
                    student_name(u) if u else f"用户{x['student_id']}",
                    int(x["cnt"])
                ])

            table = {"columns": ["排名", "学生", "提交次数"], "rows": rows}
            reply = f"这是按提交次数排序的 Top{len(rows)}："

    # ------------------------
    # 谁成绩最好
    # ------------------------
    elif intent == "top_scores":
        agg = Scores.objects.values("student_id").annotate(avg_score=Avg("score")).order_by("-avg_score")[:top_n]
        agg = list(agg)

        if not agg:
            reply = "系统里还没有成绩数据。"
        else:
            ids = [x["student_id"] for x in agg]
            id2u = {u.id: u for u in students.filter(id__in=ids)}

            rows = []
            for i, x in enumerate(agg, 1):
                u = id2u.get(x["student_id"])
                rows.append([
                    i,
                    student_name(u) if u else f"用户{x['student_id']}",
                    round(float(x["avg_score"]), 2)
                ])

            table = {"columns": ["排名", "学生", "平均分"], "rows": rows}
            reply = f"这是按平均分排序的 Top{len(rows)}："

    # ------------------------
    # 第N次作业成绩统计
    # ------------------------
    elif intent == "assignment_stats":
        if not isinstance(assignment_n, int) or assignment_n <= 0:
            return {
                "reply": "我没识别出你问的是第几次作业。比如：第3次作业平均分/最高分/最低分？",
                "table": None,
                "chart": None,
            }

        a = get_assignment_by_n(assignment_n)
        if not a:
            total = Assignment.objects.count()
            return {
                "reply": f"目前系统里只有 {total} 次作业，没有第 {assignment_n} 次。",
                "table": None,
                "chart": None,
            }

        st = Scores.objects.filter(assignment=a).aggregate(
            avg=Avg("score"),
            mx=Max("score"),
            mn=Min("score"),
        )

        avg = st["avg"]
        mx = st["mx"]
        mn = st["mn"]

        if avg is None and mx is None and mn is None:
            reply = f"第 {assignment_n} 次作业《{a.title}》还没有任何成绩记录。"
        else:
            reply = (
                f"第 {assignment_n} 次作业《{a.title}》成绩统计：\n"
                f"平均分：{(float(avg) if avg is not None else '无')}\n"
                f"最高分：{(float(mx) if mx is not None else '无')}\n"
                f"最低分：{(float(mn) if mn is not None else '无')}"
            )

    # ------------------------
    # 哪个作业最难
    # ------------------------
    elif intent == "hardest_assignment":
        agg = (
            Scores.objects.values("assignment_id", "assignment__title")
            .annotate(avg_score=Avg("score"))
            .order_by("avg_score")
        )
        agg = list(agg)

        if not agg:
            reply = "系统里还没有成绩数据，无法判断哪个作业最难。"
        else:
            hardest = agg[0]
            x = [a["assignment__title"] for a in agg]
            y = [round(float(a["avg_score"]), 2) for a in agg]

            chart = {
                "type": "bar",
                "title": "各作业平均分（越低越难）",
                "x": x,
                "y": y,
                "y_name": "平均分",
            }

            reply = f"从平均分来看，最难的是：《{hardest['assignment__title']}》（平均分 {float(hardest['avg_score']):.2f}）。图表如下："

    else:
        reply = (
            "我现在支持这些问法：\n"
            "• 第N次作业谁没交？\n"
            "• 第N次作业谁交了？\n"
            "• 谁交作业最多？\n"
            "• 谁成绩最好（Top10）？\n"
            "• 第N次作业平均分/最高分/最低分？\n"
            "• 哪个作业最难（平均分最低）？"
        )

    return {"reply": reply, "table": table, "chart": chart}
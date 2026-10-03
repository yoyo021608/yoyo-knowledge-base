"""将依赖历史的口语问题整理成可检索问题。"""

from server.agent.errors import InvalidAgentInput
from server.agent.rag.text import tokens
from server.agent.types import RewriteInput, RewrittenQuestion


class QuestionRewriter:
    def rewrite(self, input_value: RewriteInput) -> RewrittenQuestion:
        question = " ".join(input_value.question.split())
        if not question:
            raise InvalidAgentInput("问题不能为空")
        # 对明显指代补入最近一轮上下文，原问题仍完整保留。
        referential = any(word in question for word in ("它", "这个", "上述", "前面"))
        if referential and input_value.history:
            previous = input_value.history[-1].content.strip()
            if previous:
                question = f"{previous}；当前问题：{question}"
        keywords = tuple(dict.fromkeys(tokens(question)))[:20]
        return RewrittenQuestion(text=question, keywords=keywords)

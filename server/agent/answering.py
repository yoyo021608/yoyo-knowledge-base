"""根据已选证据生成回答并构造可验证的引用快照。"""

import re

from server.agent.errors import AnswerValidationError
from server.agent.rag.context import render_evidence
from server.agent.types import AnswerCitation, AnswerResult, ContextPacket
from server.infra.chat import ChatClient, ChatInput

_CITATION_MARKER = re.compile(r"【证据\s*([^】]*)】")
_CITATION_INDEX = re.compile(r"(\d+)(?:｜.*)?")


class AnswerGenerator:
    def __init__(self, chat: ChatClient, max_output_tokens: int) -> None:
        self._chat = chat
        self._max_output_tokens = max_output_tokens

    def generate(self, context: ContextPacket) -> AnswerResult:
        messages = tuple(
            ChatInput(item.role, item.content) for item in context.messages
        )
        messages += tuple(
            ChatInput("user", render_evidence(source, index))
            for index, source in enumerate(context.sources, start=1)
        )
        text = self._chat.complete(
            context.system_prompt, messages, self._max_output_tokens
        ).strip()
        labels = _CITATION_MARKER.findall(text)
        parsed = tuple(_CITATION_INDEX.fullmatch(label.strip()) for label in labels)
        if (
            not _CITATION_MARKER.sub("", text).strip()
            or not parsed
            or any(
                match is None or not 1 <= int(match.group(1)) <= len(context.sources)
                for match in parsed
            )
        ):
            raise AnswerValidationError("模型回答缺少有效内容或证据引用")
        referenced = {int(match.group(1)) for match in parsed if match is not None}
        citations = tuple(
            AnswerCitation(
                document_id=source.document_id,
                document_version_id=source.version_id,
                chunk_id=source.chunk_id,
                title_snapshot=source.title,
                source_url=source.source_url,
                quote=source.content_snippet,
            )
            for index, source in enumerate(context.sources, start=1)
            if index in referenced
        )
        return AnswerResult(
            text=text, citations=citations, evidence_status="sufficient"
        )

    @staticmethod
    def insufficient() -> AnswerResult:
        return AnswerResult(
            text="当前知识库证据不足，无法给出可靠结论。请补充资料或缩小问题范围。",
            citations=(),
            evidence_status="insufficient",
        )

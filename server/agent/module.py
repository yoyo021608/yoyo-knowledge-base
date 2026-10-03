"""Agent 内部装配；对外只暴露明确的领域能力。"""

from dataclasses import dataclass

from server.agent.answering import AnswerGenerator
from server.agent.evaluation import RunEvaluator
from server.agent.ports import DocumentSearchPort
from server.agent.rag import (
    ContextAssembler,
    EvidenceAssessor,
    QuestionRewriter,
    RetrievalOrchestrator,
)
from server.agent.run_control import RunControl
from server.agent.tools import DocumentToolAdapter
from server.agent.types import ContextBudget
from server.agent.workflows import AgentWorkflows
from server.config import Settings
from server.infra.chat import ChatClient
from server.infra.database import Database


@dataclass(frozen=True, slots=True)
class AgentModule:
    runs: RunControl
    workflows: AgentWorkflows
    tools: DocumentToolAdapter
    default_budget: ContextBudget

    @classmethod
    def create(
        cls,
        database: Database,
        settings: Settings,
        chat: ChatClient,
        documents: DocumentSearchPort,
    ) -> "AgentModule":
        runs = RunControl(database, settings.chat_model)
        retrieval = RetrievalOrchestrator(documents, settings.agent_retrieval_limit)
        return cls(
            runs=runs,
            workflows=AgentWorkflows(
                runs,
                QuestionRewriter(),
                retrieval,
                EvidenceAssessor(),
                ContextAssembler(),
                AnswerGenerator(chat, settings.agent_reserved_output_tokens),
                RunEvaluator(),
                documents,
                max_retries=settings.agent_max_retrieval_retries,
                retrieval_timeout_seconds=settings.agent_retrieval_timeout_seconds,
            ),
            tools=DocumentToolAdapter(documents),
            default_budget=ContextBudget(
                model_window=settings.agent_model_window,
                reserved_output_tokens=settings.agent_reserved_output_tokens,
                safety_margin=settings.agent_safety_margin,
                history_budget=settings.agent_history_budget,
                evidence_budget=settings.agent_evidence_budget,
            ),
        )

from __future__ import annotations

from time import perf_counter

from langgraph.graph import END, START, StateGraph

from agent.issue_fusion import fuse_issues
from agent.state.inspection import (
    InspectionState,
    RuleLoader,
    SemanticInspectionSkill,
    WorkflowResult,
)
from contracts.models import (
    InspectionReport,
    Issue,
    ProductInput,
    RiskLevel,
    Rule,
    TaskStatus,
    TraceEvent,
)
from llm.models import SemanticSkillResult
from skills.food.quality import FoodQualitySkill
from tools.food.risk import aggregate_risk


class _NoopSemanticInspectionSkill:
    """Keep the fixed graph offline when no semantic dependencies are injected."""

    def inspect(
        self,
        product: ProductInput,
        rules: list[Rule],
        deterministic_issues: list[Issue],
    ) -> SemanticSkillResult:
        del product, rules, deterministic_issues
        return SemanticSkillResult()


class FoodInspectionWorkflow:
    """Run the fixed deterministic food-inspection graph without persistence access."""

    def __init__(
        self,
        rule_loader: RuleLoader,
        food_quality_skill: FoodQualitySkill,
        *,
        semantic_inspection_skill: SemanticInspectionSkill | None = None,
    ) -> None:
        self._rule_loader = rule_loader
        self._food_quality_skill = food_quality_skill
        self._semantic_inspection_skill = (
            semantic_inspection_skill or _NoopSemanticInspectionSkill()
        )
        graph = StateGraph(InspectionState)
        graph.add_node("load_rules", self._load_rules)
        graph.add_node("food_quality_skill", self._run_food_quality_skill)
        graph.add_node("semantic_risk_skill", self._run_semantic_risk_skill)
        graph.add_node("issue_fusion", self._fuse_issues)
        graph.add_node("risk_aggregator", self._aggregate_risk)
        graph.add_node("report_builder", self._build_report)
        graph.add_edge(START, "load_rules")
        graph.add_edge("load_rules", "food_quality_skill")
        graph.add_edge("food_quality_skill", "semantic_risk_skill")
        graph.add_edge("semantic_risk_skill", "issue_fusion")
        graph.add_edge("issue_fusion", "risk_aggregator")
        graph.add_edge("risk_aggregator", "report_builder")
        graph.add_edge("report_builder", END)
        self._graph = graph.compile()

    def invoke(self, *, task_id: str, product: ProductInput) -> WorkflowResult:
        """Execute the fixed graph and return only in-memory inspection artifacts."""
        state = self._graph.invoke({"task_id": task_id, "product": product, "trace_events": []})
        return WorkflowResult(
            report=state["report"],
            rule_version=",".join(sorted({rule.version for rule in state["rules"]})),
            rules=state["rules"],
            trace_events=state["trace_events"],
        )

    def _load_rules(self, state: InspectionState) -> dict[str, object]:
        started_at = perf_counter()
        rules = self._rule_loader()
        return {
            "rules": rules,
            "trace_events": [
                self._trace(
                    state,
                    step_name="load_rules",
                    tool_or_skill_name="rule_loader",
                    rule_ids=sorted(rule.rule_id for rule in rules),
                    decision=f"加载 {len(rules)} 条已启用食品规则",
                    started_at=started_at,
                )
            ],
        }

    def _run_food_quality_skill(self, state: InspectionState) -> dict[str, object]:
        started_at = perf_counter()
        skill_result = self._food_quality_skill.inspect(state["product"], state["rules"])
        return {
            "skill_result": skill_result,
            "trace_events": [
                self._trace(
                    state,
                    step_name="food_quality_skill",
                    tool_or_skill_name=skill_result.name,
                    rule_ids=sorted(
                        {rule_id for issue in skill_result.issues for rule_id in issue.rule_ids}
                    ),
                    decision=f"生成 {len(skill_result.issues)} 个确定性 Issue",
                    started_at=started_at,
                )
            ],
        }

    def _run_semantic_risk_skill(self, state: InspectionState) -> dict[str, object]:
        started_at = perf_counter()
        semantic_result = self._semantic_inspection_skill.inspect(
            state["product"], state["rules"], state["skill_result"].issues
        )
        candidate_rule_ids = semantic_result.trace_metadata.get("candidate_rule_ids", [])
        return {
            "semantic_result": semantic_result,
            "trace_events": [
                self._trace(
                    state,
                    step_name="semantic_risk_skill",
                    tool_or_skill_name="semantic_risk_skill",
                    rule_ids=list(candidate_rule_ids)
                    if isinstance(candidate_rule_ids, list)
                    and all(isinstance(rule_id, str) for rule_id in candidate_rule_ids)
                    else [],
                    decision=(
                        "语义质检降级"
                        if semantic_result.degradation_flags
                        else f"生成 {len(semantic_result.issues)} 个语义 Issue"
                    ),
                    started_at=started_at,
                    metadata=semantic_result.trace_metadata,
                )
            ],
        }

    def _fuse_issues(self, state: InspectionState) -> dict[str, object]:
        started_at = perf_counter()
        fusion = fuse_issues(state["skill_result"].issues, state["semantic_result"])
        return {
            "issues": fusion.issues,
            "degradation_flags": fusion.degradation_flags,
            "review_required": fusion.review_required,
            "review_reasons": fusion.review_reasons,
            "trace_events": [
                self._trace(
                    state,
                    step_name="issue_fusion",
                    tool_or_skill_name="deterministic_first_issue_fusion",
                    rule_ids=sorted(
                        {rule_id for issue in fusion.issues for rule_id in issue.rule_ids}
                    ),
                    decision=f"融合后保留 {len(fusion.issues)} 个 Issue",
                    started_at=started_at,
                )
            ],
        }

    def _aggregate_risk(self, state: InspectionState) -> dict[str, object]:
        started_at = perf_counter()
        automated_risk_level = aggregate_risk(state["issues"])
        review_required = state["review_required"] or automated_risk_level is RiskLevel.HIGH
        review_reasons = list(state["review_reasons"])
        if automated_risk_level is RiskLevel.HIGH:
            review_reasons.append("命中 high 风险")
        return {
            "automated_risk_level": automated_risk_level,
            "review_required": review_required,
            "review_reasons": list(dict.fromkeys(review_reasons)),
            "trace_events": [
                self._trace(
                    state,
                    step_name="risk_aggregator",
                    tool_or_skill_name="aggregate_risk",
                    rule_ids=[],
                    decision=f"自动风险等级为 {automated_risk_level.value}",
                    started_at=started_at,
                )
            ],
        }

    def _build_report(self, state: InspectionState) -> dict[str, object]:
        started_at = perf_counter()
        report = InspectionReport(
            task_id=state["task_id"],
            status=TaskStatus.SUCCESS,
            automated_risk_level=state["automated_risk_level"],
            review_required=state["review_required"],
            review_reasons=state["review_reasons"],
            issues=state["issues"],
            degradation_flags=state["degradation_flags"],
            trace_id=state["task_id"],
        )
        return {
            "report": report,
            "trace_events": [
                self._trace(
                    state,
                    step_name="report_builder",
                    tool_or_skill_name="inspection_report_builder",
                    rule_ids=sorted(
                        {rule_id for issue in report.issues for rule_id in issue.rule_ids}
                    ),
                    decision="生成同步质检报告",
                    started_at=started_at,
                )
            ],
        }

    @staticmethod
    def _trace(
        state: InspectionState,
        *,
        step_name: str,
        tool_or_skill_name: str,
        rule_ids: list[str],
        decision: str,
        started_at: float,
        metadata: dict[str, object] | None = None,
    ) -> TraceEvent:
        return TraceEvent(
            task_id=state["task_id"],
            step_name=step_name,
            tool_or_skill_name=tool_or_skill_name,
            rule_ids=rule_ids,
            decision=decision,
            status="success",
            latency_ms=int((perf_counter() - started_at) * 1000),
            metadata=metadata or {},
        )

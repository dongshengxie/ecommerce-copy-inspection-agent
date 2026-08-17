from contracts.models import Issue, RiskLevel

RISK_ORDER = {
    RiskLevel.PASS: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
}


def aggregate_risk(issues: list[Issue]) -> RiskLevel:
    """Return the maximum deterministic risk, or pass when there are no Issues."""
    if not issues:
        return RiskLevel.PASS
    return max((issue.risk_level for issue in issues), key=RISK_ORDER.__getitem__)

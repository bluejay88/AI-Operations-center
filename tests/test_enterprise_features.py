from ai_ops_center.enterprise_features import enterprise_feature_catalog


def test_enterprise_feature_catalog_represents_500_feature_roadmap():
    catalog = enterprise_feature_catalog()

    assert catalog["project_id"] == "ai-operations-center-2"
    assert catalog["total_features"] == 500
    assert catalog["domain_count"] == 20
    assert catalog["features_per_domain"] == 25
    assert len(catalog["domains"]) == 20
    assert sum(len(domain["features"]) for domain in catalog["domains"]) == 500


def test_enterprise_feature_catalog_has_security_and_approval_gates():
    catalog = enterprise_feature_catalog()
    domains = {domain["id"]: domain for domain in catalog["domains"]}

    assert "security" in domains
    assert domains["security"]["agent_id"] == "security-monitor"
    assert all(
        feature["approval_policy"] == "high_risk_requires_jayla_approval"
        for feature in domains["security"]["features"]
    )
    assert any(
        feature["approval_policy"] == "low_risk_worker_allowed_with_audit"
        for domain in catalog["domains"]
        for feature in domain["features"]
    )

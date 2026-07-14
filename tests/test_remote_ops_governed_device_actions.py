from ai_ops_center.remote_ops import GOVERNED_DEVICE_OPERATIONS, ROLE_ALLOWED_OPERATIONS, SENSITIVE_OPERATIONS


def test_governed_device_operations_are_allowed_but_sensitive_for_every_node_role():
    for operation in GOVERNED_DEVICE_OPERATIONS:
        assert operation in SENSITIVE_OPERATIONS
        assert operation in ROLE_ALLOWED_OPERATIONS["brain"]
        assert operation in ROLE_ALLOWED_OPERATIONS["development"]
        assert operation in ROLE_ALLOWED_OPERATIONS["research"]
        assert operation in ROLE_ALLOWED_OPERATIONS["business"]

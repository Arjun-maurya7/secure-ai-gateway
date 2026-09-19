from schemas.policy import PolicyAction


DEFAULT_POLICIES = {
    "EMAIL": PolicyAction.REDACT,
    "PHONE": PolicyAction.REDACT,
    "PAN": PolicyAction.REDACT,
    "CARD": PolicyAction.REDACT,
    "NAME": PolicyAction.REDACT,
    "ACCOUNT": PolicyAction.REDACT,
    "IP": PolicyAction.REDACT,
    "URL": PolicyAction.ALLOW,
    "API_KEY": PolicyAction.BLOCK,
    "JWT": PolicyAction.BLOCK,
}


class PolicyEngine:

    def __init__(self, policies=None):
        self.policies = policies or DEFAULT_POLICIES.copy()

    def get_action(self, entity_type: str) -> PolicyAction:
        return self.policies.get(
            entity_type,
            PolicyAction.REDACT
        )
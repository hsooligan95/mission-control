"""The simulated incident world: deterministic, queryable ground truth.

Agents never see this object. Each agent works from a partial, sometimes
stale *view* baked into its scenario (see scenarios.py). The arbiter is
the only component allowed to query the world at decision time -- that
asymmetry is the design. Arbitration acquires NEW evidence that neither
proposer submitted, instead of re-weighing the proposals themselves.

Every query is appended to ``query_log`` so a decision record can cite
exactly what was gathered, and a test can prove the cited values are
the world's actual values.
"""
from __future__ import annotations

import copy


class World:
    def __init__(self, state: dict, effects: dict | None = None):
        self._state = copy.deepcopy(state)
        self._effects = copy.deepcopy(effects or {})
        self.query_log: list[dict] = []

    # -- arbiter evidence tools (every call is logged) -------------------

    def _log(self, tool: str, args: dict, result) -> object:
        self.query_log.append(
            {"tool": tool, "args": args, "result": copy.deepcopy(result)})
        return copy.deepcopy(result)

    def service_state(self, service: str) -> dict:
        return self._log("service_state", {"service": service},
                         self._state["services"][service])

    def deploy_recency(self, service: str) -> dict | None:
        deploys = [d for d in self._state.get("deploys", [])
                   if d["service"] == service]
        latest = min(deploys, key=lambda d: d["minutes_ago"], default=None)
        return self._log("deploy_recency", {"service": service}, latest)

    def error_onset(self, service: str) -> dict:
        return self._log("error_onset", {"service": service},
                         self._state["error_onset"][service])

    def dependency_health(self, service: str) -> dict:
        return self._log("dependency_health", {"service": service},
                         self._state["dependencies"][service])

    def error_budget(self, service: str) -> dict:
        return self._log("error_budget", {"service": service},
                         self._state["error_budgets"][service])

    def replica_state(self, cluster: str) -> dict:
        return self._log("replica_state", {"cluster": cluster},
                         self._state["clusters"][cluster])

    # -- execution --------------------------------------------------------

    def apply_action(self, action: str) -> None:
        """Apply the scenario's scripted effect of an executed action."""
        patch = self._effects.get(action)
        if patch is None:
            raise KeyError(f"no effect defined for action {action!r}")
        _deep_merge(self._state, copy.deepcopy(patch))

    def check(self, check: dict) -> bool:
        """One post-action verification check against live state."""
        value = self._state["services"][check["service"]][check["field"]]
        op, want = check["op"], check["value"]
        return {"<=": value <= want, ">=": value >= want,
                "==": value == want}[op]


def _deep_merge(dst: dict, src: dict) -> None:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value

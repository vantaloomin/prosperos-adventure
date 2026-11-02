"""The outcome ladder every ruleset lands on, worst first (docs/requirements.md "Rulesets"), so the narrator, the
record and the screen read a result the same way whatever rolled it."""

BANDS = ('critical_failure', 'failure', 'failure_upside', 'success_cost', 'success', 'critical_success')
LABELS = {'critical_failure': 'Critical failure', 'failure': 'Fail', 'failure_upside': 'Fail with an upside',
          'success_cost': 'Success at a cost', 'success': 'Success', 'critical_success': 'Critical success'}


def succeeded(band: str) -> bool:
    return BANDS.index(band) >= BANDS.index('success_cost')

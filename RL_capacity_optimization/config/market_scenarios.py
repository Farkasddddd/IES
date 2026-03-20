from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class MethanolPriceScenario:
    name: str
    methanol_price_yuan_per_kg: float
    note: str = ""


GREY_METHANOL_LOW = MethanolPriceScenario(
    name="grey_low",
    methanol_price_yuan_per_kg=2.0,
    note="Traditional grey methanol lower-bound reference.",
)

GREY_METHANOL_HIGH = MethanolPriceScenario(
    name="grey_high",
    methanol_price_yuan_per_kg=3.0,
    note="Traditional grey methanol upper-bound reference.",
)

GREEN_METHANOL_CONSERVATIVE = MethanolPriceScenario(
    name="green_conservative",
    methanol_price_yuan_per_kg=4.0,
    note="Conservative sensitivity case suggested for paper discussion.",
)

GREEN_METHANOL_BASE = MethanolPriceScenario(
    name="green_base",
    methanol_price_yuan_per_kg=6.0,
    note="Baseline green methanol scenario.",
)

GREEN_METHANOL_AGGRESSIVE = MethanolPriceScenario(
    name="green_aggressive",
    methanol_price_yuan_per_kg=8.0,
    note="Aggressive green methanol premium case.",
)

DEFAULT_PAPER_SCENARIOS = (
    GREEN_METHANOL_CONSERVATIVE,
    GREEN_METHANOL_BASE,
    GREEN_METHANOL_AGGRESSIVE,
)


def to_dict(scenario: MethanolPriceScenario) -> dict:
    return asdict(scenario)

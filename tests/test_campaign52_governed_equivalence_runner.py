from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.run_campaign52_governed_equivalence import (
    Campaign52EquivalenceError,
    RecordedIntentStrategy,
)


def test_recorded_intent_strategy_replays_exact_sequence() -> None:
    intents = [SimpleNamespace(value="a"), SimpleNamespace(value="b")]
    strategy = RecordedIntentStrategy(intents)
    df = pd.DataFrame({"close": [1.0, 2.0]})

    assert strategy.generate_intent(df.iloc[:1], None) is intents[0]
    assert strategy.generate_intent(df.iloc[:2], None) is intents[1]
    strategy.assert_consumed()


def test_recorded_intent_strategy_fails_closed_on_prefix_mismatch() -> None:
    strategy = RecordedIntentStrategy([SimpleNamespace(value="a")])
    df = pd.DataFrame({"close": [1.0, 2.0]})

    with pytest.raises(Campaign52EquivalenceError, match="RECORDED_INTENT_SEQUENCE_MISMATCH"):
        strategy.generate_intent(df.iloc[:2], None)

from app.demo import demo_settings
from app.engine import calculate
from app.engine_demo import engine_demo


def test_public_observations_use_actual_engine():
    output = calculate(engine_demo(), demo_settings())
    assert [r.quantity for r in output.recommendations] == [144, 0, None]
    assert output.recommendations[0].components.stockout_lost_demand == 60
    assert any(a.decision == 'excluded' for a in output.explanations[0].anomalies)
    changed = calculate(engine_demo(), demo_settings().model_copy(update={'buffer_days':14}))
    assert changed.recommendations[0].quantity > 144

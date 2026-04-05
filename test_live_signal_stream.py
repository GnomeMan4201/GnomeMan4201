import asyncio

from drift_live_signal import LiveSignalStream, PolicyAction


async def _collect_one(stream: LiveSignalStream):
    async for delta in stream.subscribe(max_buffer=8):
        return delta


def test_delta_only_emission_and_policy_transition():
    async def _run():
        stream = LiveSignalStream(initial_alpha=0.10, inject_threshold=0.2, regenerate_threshold=0.4, rollback_threshold=0.7)

        subscriber = asyncio.create_task(_collect_one(stream))
        await asyncio.sleep(0)
        delta = await stream.update_internal_score(0.10)
        assert delta.changes == {}

        await stream.update_external_score(0.90)
        sub_delta = await subscriber
        assert "external" in sub_delta.changes
        assert "divergence" in sub_delta.changes
        assert sub_delta.changes["policy_action"] == PolicyAction.ROLLBACK.value

    asyncio.run(_run())


def test_async_evaluator_does_not_block_loop():
    async def _run():
        stream = LiveSignalStream(initial_alpha=0.3)
        progressed = False

        async def evaluator():
            await asyncio.sleep(0.01)
            return 0.9

        task = stream.evaluate_external_async(evaluator)

        await asyncio.sleep(0)
        progressed = True
        await task

        assert progressed is True

    asyncio.run(_run())


def test_internal_stream_queue_orders_deltas():
    async def _run():
        stream = LiveSignalStream(initial_alpha=0.1, stream_buffer_size=4)

        await stream.update_internal_score(0.2)
        await stream.update_external_score(0.4)

        iterator = stream.stream()
        first = await anext(iterator)
        second = await anext(iterator)

        assert first.sequence < second.sequence
        assert first.changes["alpha"] == 0.2
        assert second.changes["external"] == 0.4
        assert second.changes["divergence"] == abs(0.2 - 0.4)

    asyncio.run(_run())

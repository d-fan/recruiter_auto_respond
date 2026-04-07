import asyncio
import os
import tempfile

from hypothesis import given
from hypothesis import strategies as st

from recruiter_auto_respond.state_manager import AppState, StateManager

# Strategy for ISO timestamps
iso_timestamps = st.datetimes().map(lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ"))

# Strategy for results: list of (timestamp, success)
results_strategy = st.lists(st.tuples(iso_timestamps, st.booleans()))


@given(initial_ts=iso_timestamps, results=results_strategy)
def test_watermark_properties(initial_ts, results):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_state_file = tmp.name

    async def run_test():
        manager = StateManager(temp_state_file)
        await manager.save_state(AppState(last_run_timestamp=initial_ts))

        # Sort results by timestamp as the actual pipeline would
        sorted_results = sorted(results, key=lambda x: x[0])

        new_ts = await manager.update_watermark(sorted_results)

        # Properties to check:
        # 1. new_ts must be one of the timestamps in the successful results
        #    OR the initial_ts
        possible_timestamps = {initial_ts} | {
            ts for ts, success in sorted_results if success
        }
        assert new_ts in possible_timestamps

        # 2. If there are no failures, new_ts should be the last success
        #    OR initial_ts if no results
        all_success = all(success for ts, success in sorted_results)
        if sorted_results and all_success:
            assert new_ts == sorted_results[-1][0]
        elif not sorted_results:
            assert new_ts == initial_ts

        # 3. If there is a failure, new_ts should be the last success
        #    before the first failure, or initial_ts if the first one failed.
        first_failure_idx = next(
            (i for i, (ts, success) in enumerate(sorted_results) if not success),
            None,
        )
        if first_failure_idx is not None:
            if first_failure_idx == 0:
                assert new_ts == initial_ts
            else:
                assert new_ts == sorted_results[first_failure_idx - 1][0]

    try:
        asyncio.run(run_test())
    finally:
        if os.path.exists(temp_state_file):
            os.remove(temp_state_file)

import queue

import pytest

from adg.execution_messages import ReplaceDestinationsMessage


class TestBaseMessage:
    """Test that the PriorityQueue maintains order"""

    message_queue = queue.PriorityQueue()  # Lowest priority first

    @pytest.mark.parametrize("execution_number", range(10))
    def test_repeated_key(self, execution_number):
        expected = []
        for x in range(50):
            self.message_queue.put(
                ReplaceDestinationsMessage(content="job" + str(x)), block=False
            )
            expected.append("job" + str(x))
        results = []
        for y in range(50):
            results.append(self.message_queue.get().content)
        assert results == expected

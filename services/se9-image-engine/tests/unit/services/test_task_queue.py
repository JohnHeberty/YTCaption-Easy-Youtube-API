import pytest
from unittest.mock import patch, MagicMock
from app.services.task_queue import TaskQueue
from app.domain.task_models import TaskType, GenerationFinishReason


class TestTaskQueue:
    def test_add_task(self, task_queue, sample_task_params):
        result = task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        assert result is not None
        assert result.job_id is not None
        assert len(task_queue.queue) == 1

    def test_add_task_queue_full(self, sample_task_params):
        tq = TaskQueue(queue_size=2)
        tq.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        tq.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        result = tq.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        assert result is None

    def test_get_task(self, task_queue, sample_task_params):
        added = task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        found = task_queue.get_task(added.job_id)
        assert found is not None
        assert found.job_id == added.job_id

    def test_get_task_not_found(self, task_queue):
        found = task_queue.get_task("nonexistent-id")
        assert found is None

    def test_get_task_includes_history(self, task_queue, sample_task_params):
        added = task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        task_queue.start_task(added.job_id)
        task_queue.finish_task(added.job_id)
        found = task_queue.get_task(added.job_id, include_history=True)
        assert found is not None
        assert found.is_finished

    def test_is_task_ready_to_start(self, task_queue, sample_task_params):
        added = task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        assert task_queue.is_task_ready_to_start(added.job_id) is True

    def test_is_task_finished(self, task_queue, sample_task_params):
        added = task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        assert task_queue.is_task_finished(added.job_id) is False
        task_queue.start_task(added.job_id)
        task_queue.finish_task(added.job_id)
        assert task_queue.is_task_finished(added.job_id) is True

    def test_get_queue_info(self, task_queue, sample_task_params):
        task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        info = task_queue.get_queue_info()
        assert info["running_size"] == 1
        assert info["finished_size"] == 0
        assert info["last_job_id"] is not None

    def test_finish_task_moves_to_history(self, task_queue, sample_task_params):
        added = task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        task_queue.start_task(added.job_id)
        task_queue.finish_task(added.job_id)
        assert len(task_queue.queue) == 0
        assert len(task_queue.history) == 1

    def test_history_trim(self, sample_task_params):
        tq = TaskQueue(queue_size=10, history_size=2)
        for _ in range(3):
            t = tq.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
            tq.start_task(t.job_id)
            tq.finish_task(t.job_id)
        assert len(tq.history) == 2

    def test_get_history(self, task_queue, sample_task_params):
        added = task_queue.add_task(TaskType.TEXT_TO_IMAGE, sample_task_params)
        task_queue.start_task(added.job_id)
        task_queue.finish_task(added.job_id)
        result = task_queue.get_history()
        assert len(result["history"]) == 1

    def test_webhook_called(self, task_queue, sample_task_params):
        with patch("app.services.task_queue.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            added = task_queue.add_task(
                TaskType.TEXT_TO_IMAGE, sample_task_params, webhook_url="http://hook.test"
            )
            added.set_result(
                [MagicMock(im="test.png", seed="42", finish_reason=GenerationFinishReason.SUCCESS)],
                False,
            )
            task_queue.start_task(added.job_id)
            task_queue.finish_task(added.job_id)
            assert mock_httpx.post.called

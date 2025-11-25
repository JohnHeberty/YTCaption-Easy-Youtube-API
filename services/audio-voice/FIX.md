john@ollama:~/YTCaption-Easy-Youtube-API/services/audio-voice$ docker compose logs -f
audio-voice-celery  | CUDA not available, falling back to CPU
audio-voice-celery  |
audio-voice-celery  |  -------------- celery@24c084d33b55 v5.3.4 (emerald-rush)
audio-voice-celery  | --- ***** -----
audio-voice-celery  | -- ******* ---- Linux-6.8.0-87-generic-x86_64-with-glibc2.41 2025-11-25 03:31:50
audio-voice-celery  | - *** --- * ---
audio-voice-celery  | - ** ---------- [config]
audio-voice-celery  | - ** ---------- .> app:         audio_voice_worker:0x725180506f80
audio-voice-celery  | - ** ---------- .> transport:   redis://192.168.18.110:6379/5
audio-voice-celery  | - ** ---------- .> results:     redis://192.168.18.110:6379/5
audio-voice-celery  | - *** --- * --- .> concurrency: 1 (solo)
audio-voice-celery  | -- ******* ---- .> task events: OFF (enable -E to monitor tasks in this worker)
audio-voice-celery  | --- ***** -----
audio-voice-celery  |  -------------- [queues]
audio-voice-celery  |                 .> audio_voice_queue exchange=audio_voice_queue(direct) key=audio_voice_queue
audio-voice-api     | 03:31:44 - INFO - ✅ Logging system started for audio-voice
audio-voice-api     | 03:31:44 - INFO - 📁 Files: error.log | warning.log | info.log | debug.log
audio-voice-api     | 03:31:44 - WARNING - CUDA not available, falling back to CPU
audio-voice-api     | 03:31:44 - INFO - Initializing OpenVoice client on device: cpu
audio-voice-api     | INFO:     Started server process [1]
audio-voice-api     | INFO:     Waiting for application startup.
audio-voice-celery  |
audio-voice-celery  |
audio-voice-celery  | [tasks]
audio-voice-celery  |   . app.celery_tasks.clone_voice_task
audio-voice-celery  |   . app.celery_tasks.dubbing_task
audio-voice-celery  |
audio-voice-api     | 03:31:44 - INFO - Cleanup task started
audio-voice-api     | 03:31:44 - INFO - ✅ Audio Voice Service started
audio-voice-api     | INFO:     Application startup complete.
audio-voice-api     | INFO:     Uvicorn running on http://0.0.0.0:8005 (Press CTRL+C to quit)
audio-voice-api     | INFO:     127.0.0.1:60004 - "GET / HTTP/1.1" 200 OK
audio-voice-api     | INFO:     127.0.0.1:47062 - "GET / HTTP/1.1" 200 OK
audio-voice-api     | INFO:     127.0.0.1:50810 - "GET / HTTP/1.1" 200 OK
audio-voice-api     | INFO:     127.0.0.1:38332 - "GET / HTTP/1.1" 200 OK
audio-voice-celery  | [2025-11-25 03:31:50,974: INFO/MainProcess] Connected to redis://192.168.18.110:6379/5
audio-voice-celery  | [2025-11-25 03:31:50,977: INFO/MainProcess] mingle: searching for neighbors
audio-voice-celery  | [2025-11-25 03:31:51,984: INFO/MainProcess] mingle: all alone
audio-voice-celery  | [2025-11-25 03:31:51,993: INFO/MainProcess] celery@24c084d33b55 ready.
audio-voice-celery  | [2025-11-25 03:42:18,857: INFO/MainProcess] Task app.celery_tasks.dubbing_task[job_5eb08a961664] received
audio-voice-celery  | [2025-11-25 03:42:18,861: ERROR/MainProcess] Task app.celery_tasks.dubbing_task[job_5eb08a961664] raised unexpected: NotImplementedError()
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/usr/local/lib/python3.10/site-packages/celery/app/trace.py", line 477, in trace_task
audio-voice-celery  |     R = retval = fun(*args, **kwargs)
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 33, in __call__
audio-voice-api     | INFO:     127.0.0.1:38528 - "GET / HTTP/1.1" 200 OK
audio-voice-celery  |     return loop.run_until_complete(self.run_async(*args, **kwargs))
audio-voice-api     | INFO:     127.0.0.1:56740 - "GET / HTTP/1.1" 200 OK
audio-voice-celery  |   File "/usr/local/lib/python3.10/asyncio/base_events.py", line 649, in run_until_complete
audio-voice-celery  |     return future.result()
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 36, in run_async
audio-voice-celery  |     raise NotImplementedError
audio-voice-api     | INFO:     127.0.0.1:40040 - "GET / HTTP/1.1" 200 OK
audio-voice-celery  | NotImplementedError
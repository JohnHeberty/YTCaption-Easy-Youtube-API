audio-voice-api     | 03:02:54 - INFO - 📤 Job job_15fa055788da sent to Celery: job_15fa055788da
audio-voice-api     | 03:02:54 - INFO - Job created: job_15fa055788da
audio-voice-api     | INFO:     192.168.18.4:49811 - "POST /jobs HTTP/1.1" 200 OK
audio-voice-api     | INFO:     192.168.18.4:53366 - "GET /jobs/job_15fa055788da HTTP/1.1" 200 OK
audio-voice-api     | INFO:     192.168.18.4:56313 - "GET /jobs/job_15fa055788da HTTP/1.1" 200 OK
audio-voice-api     | INFO:     127.0.0.1:49666 - "GET / HTTP/1.1" 200 OK
audio-voice-api     | INFO:     192.168.18.4:51097 - "GET /jobs/job_15fa055788da HTTP/1.1" 200 OK
audio-voice-api     | INFO:     127.0.0.1:45216 - "GET / HTTP/1.1" 200 OK
audio-voice-celery  | for more information.
audio-voice-celery  |
audio-voice-celery  | The full contents of the message body was:
audio-voice-celery  | b'[[{"id": "job_577b84a8c34a", "mode": "clone_voice", "status": "queued", "input_file": "uploads/clone_20251125030033958151.ogg", "output_file": null, "text": null, "source_language": "pt", "target_language": null, "voice_preset": null, "voice_id": null, "voice_name": "Robert", "voice_description": "CLONE", "audio_url": null, "duration": null, "file_size_input": null, "file_size_output": null, "created_at": {"__type__": "datetime", "__value__": "2025-11-25T03:00:33.958334"}, "completed_at": null, "error_message": null, "expires_at": {"__type__": "datetime", "__value__": "2025-11-26T03:00:33.958334"}, "progress": 0.0, "openvoice_model": null, "openvoice_params": null}], {}, {"callbacks": null, "errbacks": null, "chain": null, "chord": null}]' (748b)
audio-voice-celery  |
audio-voice-celery  | The full contents of the message headers:
audio-voice-celery  | {'lang': 'py', 'task': 'app.celery_tasks.clone_voice_task', 'id': 'job_577b84a8c34a', 'shadow': None, 'eta': None, 'expires': None, 'group': None, 'group_index': None, 'retries': 0, 'timelimit': [None, None], 'root_id': 'job_577b84a8c34a', 'parent_id': None, 'argsrepr': "[{'id': 'job_577b84a8c34a', 'mode': 'clone_voice', 'status': 'queued', 'input_file': 'uploads/clone_20251125030033958151.ogg', 'output_file': None, 'text': None, 'source_language': 'pt', 'target_language': None, 'voice_preset': None, 'voice_id': None, 'voice_name': 'Robert', 'voice_description': 'CLONE', 'audio_url': None, 'duration': None, 'file_size_input': None, 'file_size_output': None, 'created_at': datetime.datetime(2025, 11, 25, 3, 0, 33, 958334), 'completed_at': None, 'error_message': None, 'expires_at': datetime.datetime(2025, 11, 26, 3, 0, 33, 958334), 'progress': 0.0, 'openvoice_model': None, 'openvoice_params': None}]", 'kwargsrepr': '{}', 'origin': 'gen1@aa9f855b7893', 'ignore_result': False, 'stamped_headers': None, 'stamps': {}}
audio-voice-celery  |
audio-voice-celery  | The delivery info for this task is:
audio-voice-celery  | {'exchange': '', 'routing_key': 'audio_voice_queue'}
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/usr/local/lib/python3.10/site-packages/celery/worker/consumer/consumer.py", line 658, in on_task_received
audio-voice-celery  |     strategy = strategies[type_]
audio-voice-celery  | KeyError: 'app.celery_tasks.clone_voice_task'
audio-voice-celery  | [2025-11-25 03:02:54,589: ERROR/MainProcess] Received unregistered task of type 'app.celery_tasks.dubbing_task'.
audio-voice-celery  | The message has been ignored and discarded.
audio-voice-celery  |
audio-voice-celery  | Did you remember to import the module containing this task?
audio-voice-celery  | Or maybe you're using relative imports?
audio-voice-celery  |
audio-voice-celery  | Please see
audio-voice-celery  | https://docs.celeryq.dev/en/latest/internals/protocol.html
audio-voice-celery  | for more information.
audio-voice-celery  |
audio-voice-celery  | The full contents of the message body was:
audio-voice-celery  | b'[[{"id": "job_15fa055788da", "mode": "dubbing_with_clone", "status": "queued", "input_file": null, "output_file": null, "text": " Fala meu caro john!, boa noite meu bom, vamos faturar 40 mil reais por m\\u00eas ou n\\u00e3o ?", "source_language": "pt", "target_language": "pt", "voice_preset": "male_deep", "voice_id": "voice_f726fe131962", "voice_name": null, "voice_description": null, "audio_url": null, "duration": null, "file_size_input": null, "file_size_output": null, "created_at": {"__type__": "datetime", "__value__": "2025-11-25T03:02:54.585815"}, "completed_at": null, "error_message": null, "expires_at": {"__type__": "datetime", "__value__": "2025-11-26T03:02:54.585815"}, "progress": 0.0, "openvoice_model": null, "openvoice_params": null}], {}, {"callbacks": null, "errbacks": null, "chain": null, "chord": null}]' (827b)       
audio-voice-celery  |
audio-voice-celery  | The full contents of the message headers:
audio-voice-celery  | {'lang': 'py', 'task': 'app.celery_tasks.dubbing_task', 'id': 'job_15fa055788da', 'shadow': None, 'eta': None, 'expires': None, 'group': None, 'group_index': None, 'retries': 0, 'timelimit': [None, None], 'root_id': 'job_15fa055788da', 'parent_id': None, 'argsrepr': "[{'id': 'job_15fa055788da', 'mode': 'dubbing_with_clone', 'status': 'queued', 'input_file': None, 'output_file': None, 'text': ' Fala meu caro john!, boa noite meu bom, vamos faturar 40 mil reais por mês ou não ?', 'source_language': 'pt', 'target_language': 'pt', 'voice_preset': 'male_deep', 'voice_id': 'voice_f726fe131962', 'voice_name': None, 'voice_description': None, 'audio_url': None, 'duration': None, 'file_size_input': None, 'file_size_output': None, 'created_at': datetime.datetime(2025, 11, 25, 3, 2, 54, 585815), 'completed_at': None, 'error_message': None, 'expires_at': datetime.datetime(2025, 11, 26, 3, 2, 54, 585815), 'progress': 0.0, 'openvoice_model': None, 'openvoice_params': None}]", 'kwargsrepr': '{}', 'origin': 'gen1@aa9f855b7893', 'ignore_result': False, 'stamped_headers': None, 'stamps': {}}    
audio-voice-celery  |
audio-voice-celery  | The delivery info for this task is:
audio-voice-celery  | {'exchange': '', 'routing_key': 'audio_voice_queue'}
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/usr/local/lib/python3.10/site-packages/celery/worker/consumer/consumer.py", line 658, in on_task_received
audio-voice-celery  |     strategy = strategies[type_]
audio-voice-celery  | KeyError: 'app.celery_tasks.dubbing_task'
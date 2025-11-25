audio-voice-api     | 03:55:12 - INFO - 📤 Job job_4d231f19a4c6 sent to Celery: job_4d231f19a4c6
audio-voice-api     | 03:55:12 - INFO - Job created: job_4d231f19a4c6
audio-voice-api     | INFO:     192.168.18.4:64764 - "POST /jobs HTTP/1.1" 200 OK
audio-voice-celery  | [2025-11-25 03:55:12,327: INFO/MainProcess] Task app.celery_tasks.clone_voice_task[job_4d231f19a4c6] received
audio-voice-celery  | [2025-11-25 03:55:12,328: INFO/MainProcess] 🎤 Celery clone voice task started for job job_4d231f19a4c6
audio-voice-celery  | [2025-11-25 03:55:12,328: INFO/MainProcess] Processing voice clone job job_4d231f19a4c6: None
audio-voice-celery  | [2025-11-25 03:55:12,328: INFO/MainProcess] Cloning voice from None language=pt
audio-voice-celery  | [2025-11-25 03:55:12,328: ERROR/MainProcess] Error cloning voice: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  | [2025-11-25 03:55:12,329: ERROR/MainProcess] ❌ Voice clone job job_4d231f19a4c6 failed: OpenVoice error: Voice cloning failed: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType        
audio-voice-celery  | [2025-11-25 03:55:12,329: ERROR/MainProcess] ❌ Celery clone voice task failed: Voice cloning error: OpenVoice error: Voice cloning failed: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 395, in _validate_audio_for_cloning
audio-voice-celery  |     waveform, sample_rate = torchaudio.load(audio_path)
audio-voice-celery  |                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchaudio/_backend/utils.py", line 204, in load      
audio-voice-celery  |     return backend.load(uri, frame_offset, num_frames, normalize, channels_first, format, buffer_size)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchaudio/_backend/ffmpeg.py", line 336, in load     
audio-voice-celery  |     return load_audio(os.path.normpath(uri), frame_offset, num_frames, normalize, channels_first, format)
audio-voice-celery  |                       ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "<frozen posixpath>", line 391, in normpath
audio-voice-celery  | TypeError: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  |
audio-voice-celery  | During handling of the above exception, another exception occurred:
audio-voice-celery  |
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 335, in clone_voice
audio-voice-celery  |     audio_info = self._validate_audio_for_cloning(audio_path)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 424, in _validate_audio_for_cloning
audio-voice-celery  |     raise InvalidAudioException(f"Invalid audio file: {str(e)}")
audio-voice-celery  | app.exceptions.InvalidAudioException: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  |
audio-voice-celery  | During handling of the above exception, another exception occurred:
audio-voice-celery  |
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/processor.py", line 106, in process_clone_job
audio-voice-celery  |     voice_profile = await self.openvoice_client.clone_voice(
audio-voice-celery  |                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 368, in clone_voice
audio-voice-celery  |     raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
audio-voice-celery  | app.exceptions.OpenVoiceException: OpenVoice error: Voice cloning failed: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  |
audio-voice-celery  | During handling of the above exception, another exception occurred:
audio-voice-celery  |
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 95, in _process
audio-voice-celery  |     voice_profile = await processor.process_clone_job(job)
audio-voice-celery  |                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/processor.py", line 141, in process_clone_job
audio-voice-celery  |     raise VoiceCloneException(str(e))
audio-voice-celery  | app.exceptions.VoiceCloneException: Voice cloning error: OpenVoice error: Voice cloning failed: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  | [2025-11-25 03:55:12,330: WARNING/MainProcess] /usr/local/lib/python3.11/dist-packages/pydantic/main.py:528: UserWarning: Pydantic serializer warnings:
audio-voice-celery  |   PydanticSerializationUnexpectedValue(Expected `enum` - serialized value may not be as expected [field_name='status', input_value='failed', input_type=str])
audio-voice-celery  |   return self.__pydantic_serializer__.to_json(
audio-voice-celery  |
audio-voice-celery  | [2025-11-25 03:55:12,335: ERROR/MainProcess] Task app.celery_tasks.clone_voice_task[job_4d231f19a4c6] raised unexpected: VoiceCloneException('Voice cloning error: OpenVoice error: Voice cloning failed: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType')
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 395, in _validate_audio_for_cloning
audio-voice-celery  |     waveform, sample_rate = torchaudio.load(audio_path)
audio-voice-celery  |                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchaudio/_backend/utils.py", line 204, in load      
audio-voice-celery  |     return backend.load(uri, frame_offset, num_frames, normalize, channels_first, format, buffer_size)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchaudio/_backend/ffmpeg.py", line 336, in load     
audio-voice-celery  |     return load_audio(os.path.normpath(uri), frame_offset, num_frames, normalize, channels_first, format)
audio-voice-celery  |                       ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "<frozen posixpath>", line 391, in normpath
audio-voice-celery  | TypeError: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  |
audio-voice-celery  | During handling of the above exception, another exception occurred:
audio-voice-celery  |
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 335, in clone_voice
audio-voice-celery  |     audio_info = self._validate_audio_for_cloning(audio_path)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 424, in _validate_audio_for_cloning
audio-voice-celery  |     raise InvalidAudioException(f"Invalid audio file: {str(e)}")
audio-voice-celery  | app.exceptions.InvalidAudioException: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  |
audio-voice-celery  | During handling of the above exception, another exception occurred:
audio-voice-celery  |
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/processor.py", line 106, in process_clone_job
audio-voice-celery  |     voice_profile = await self.openvoice_client.clone_voice(
audio-voice-celery  |                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/openvoice_client.py", line 368, in clone_voice
audio-voice-celery  |     raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
audio-voice-celery  | app.exceptions.OpenVoiceException: OpenVoice error: Voice cloning failed: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
audio-voice-celery  |
audio-voice-celery  | During handling of the above exception, another exception occurred:
audio-voice-celery  |
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/celery/app/trace.py", line 477, in trace_task
audio-voice-celery  |     R = retval = fun(*args, **kwargs)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/celery/app/trace.py", line 760, in __protected_call__ 
audio-voice-celery  |     return self.run(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 112, in clone_voice_task
audio-voice-celery  |     return run_async_task(_process())
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 35, in run_async_task
audio-voice-celery  |     return loop.run_until_complete(coro)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/lib/python3.11/asyncio/base_events.py", line 654, in run_until_complete
audio-voice-celery  |     return future.result()
audio-voice-celery  |            ^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 95, in _process
audio-voice-celery  |     voice_profile = await processor.process_clone_job(job)
audio-voice-celery  |                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/processor.py", line 141, in process_clone_job
audio-voice-celery  |     raise VoiceCloneException(str(e))
audio-voice-celery  | app.exceptions.VoiceCloneException: Voice cloning error: OpenVoice error: Voice cloning failed: Invalid audio: Invalid audio file: expected str, bytes or os.PathLike object, not NoneType
Attaching to audio-voice-api, audio-voice-celery
audio-voice-api  | Traceback (most recent call last):
audio-voice-api  |   File "/app/run.py", line 10, in <module>
audio-voice-api  |     uvicorn.run(
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run             
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()                                                                                        
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import                                        
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
audio-voice-api  | Traceback (most recent call last):                                                                       
audio-voice-api  |   File "/app/run.py", line 10, in <module>                                                               
audio-voice-api  |     uvicorn.run(                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/main.py", line 593, in run                       
audio-voice-api  |     server.run()                                                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 67, in run                      
audio-voice-api  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())         
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/_compat.py", line 60, in asyncio_run
audio-voice-api  |     return loop.run_until_complete(main)                                                                 
audio-voice-api  |   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete                              
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 71, in serve                    
audio-voice-api  |     await self._serve(sockets)                                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/server.py", line 78, in _serve                   
audio-voice-api  |     config.load()
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/config.py", line 439, in load                    
audio-voice-api  |     self.loaded_app = import_from_string(self.app)                                                       
audio-voice-api  |   File "/usr/local/lib/python3.10/site-packages/uvicorn/importer.py", line 19, in import_from_string     
audio-voice-api  |     module = importlib.import_module(module_str)                                                         
audio-voice-api  |   File "/usr/local/lib/python3.10/importlib/__init__.py", line 126, in import_module                     
audio-voice-api  |     return _bootstrap._gcd_import(name[level:], package, level)                                          
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load                                     
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked                            
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked                                      
audio-voice-api  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module                                
audio-voice-api  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed                           
audio-voice-api  |   File "/app/app/main.py", line 30, in <module>                                                          
audio-voice-api  |     setup_logging("audio-voice", settings['log_level'])                                                  
audio-voice-api  |   File "/app/app/logging_config.py", line 41, in setup_logging                                           
audio-voice-api  |     file_handler = logging.FileHandler(                                                                  
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1169, in __init__                           
audio-voice-api  |     StreamHandler.__init__(self, self._open())                                                           
audio-voice-api  |   File "/usr/local/lib/python3.10/logging/__init__.py", line 1201, in _open                              
audio-voice-api  |     return open_func(self.baseFilename, self.mode,                                                       
audio-voice-api  | PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'                               
dependency failed to start: container audio-voice-api is unhealthy 
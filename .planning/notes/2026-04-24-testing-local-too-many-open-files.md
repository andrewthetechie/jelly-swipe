---
date: "2026-04-24 12:00"
promoted: false
---

while testing the app running locally, I ran into this error ----------------------------------------
Exception occurred during processing of request from ('10.10.0.10', 52017)
----------------------------------------
Exception occurred during processing of request from ('10.10.0.10', 58530)
Traceback (most recent call last):
  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 371, in run_wsgi
  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 347, in execute
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/selectors.py", line 493, in __init__
Traceback (most recent call last):
OSError: [Errno 24] Too many open files
  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 371, in run_wsgi

During handling of the above exception, another exception occurred:

  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 347, in execute
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/selectors.py", line 493, in __init__
Traceback (most recent call last):
OSError: [Errno 24] Too many open files

During handling of the above exception, another exception occurred:

  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/socketserver.py", line 697, in process_request_thread
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/socketserver.py", line 362, in finish_request
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/socketserver.py", line 766, in __init__
  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 399, in handle
Traceback (most recent call last):
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/http/server.py", line 496, in handle
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/http/server.py", line 484, in handle_one_request
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/socketserver.py", line 697, in process_request_thread
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/socketserver.py", line 362, in finish_request
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/socketserver.py", line 766, in __init__
  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 399, in handle
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/http/server.py", line 496, in handle
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/http/server.py", line 484, in handle_one_request
  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 391, in run_wsgi
  File "<frozen importlib._bootstrap>", line 1371, in _find_and_load
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/http/server.py", line 484, in handle_one_request
  File "<frozen importlib._bootstrap>", line 1342, in _find_and_load_unlocked
  File "/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/serving.py", line 391, in run_wsgi
  File "<frozen importlib._bootstrap>", line 938, in _load_unlocked
  File "<frozen importlib._bootstrap>", line 1371, in _find_and_load
  File "<frozen importlib._bootstrap_external>", line 755, in exec_module
  File "<frozen importlib._bootstrap>", line 1342, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 938, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 892, in get_code
  File "<frozen importlib._bootstrap_external>", line 755, in exec_module
  File "<frozen importlib._bootstrap_external>", line 950, in get_data
  File "<frozen importlib._bootstrap_external>", line 892, in get_code
  File "<frozen importlib._bootstrap_external>", line 950, in get_data
OSError: [Errno 24] Too many open files: '/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/debug/__init__.py'
OSError: [Errno 24] Too many open files: '/Users/andrew/.pyenv/versions/3.13/envs/kino-swipe/lib/python3.14/site-packages/werkzeug/debug/__init__.py'. It is possible this is just an issue with it running on my mac, but once that happened no image loaded inside the app and the app no longer functioned so we need to better handle this case.

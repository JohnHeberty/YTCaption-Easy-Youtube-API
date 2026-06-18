@echo off
set PYTHONPATH=%~dp0..
python -m clothes_segmentation.api.server

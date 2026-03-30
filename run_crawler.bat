@echo off
cd /d "C:\Users\user\test_project\biospectator"
python biospectator_crawler.py >> logs\crawler.log 2>&1

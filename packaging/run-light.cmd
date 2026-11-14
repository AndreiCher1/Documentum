@echo off
rem Zapusk Documentum v lyogkom profile (kak na PK s 8 GB): malenkaya model, bez poiska po smyslu.
rem Pered zapuskom zakroyte Documentum, esli on otkryt.
set DOCUMENTUM_PROFILE=light
start "" "%~dp0Documentum.exe"

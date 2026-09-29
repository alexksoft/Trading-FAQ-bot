@echo off
echo === Deploying WhatsApp FAQ Bot ===

set SERVER=opc@129.159.11.42
set KEY=%USERPROFILE%\.ssh\oracle-kiro.key
set REMOTE_DIR=/home/opc/whatsapp-faq
set LOCAL_DIR=%~dp0

echo [1/3] Uploading .env...
scp -i "%KEY%" -o StrictHostKeyChecking=no "%LOCAL_DIR%.env" %SERVER%:%REMOTE_DIR%/.env
if errorlevel 1 ( echo ERROR: Failed to upload .env & exit /b 1 )

echo [2/4] Uploading code...
scp -i "%KEY%" -o StrictHostKeyChecking=no -r "%LOCAL_DIR%app" %SERVER%:%REMOTE_DIR%/
scp -i "%KEY%" -o StrictHostKeyChecking=no -r "%LOCAL_DIR%config" %SERVER%:%REMOTE_DIR%/
scp -i "%KEY%" -o StrictHostKeyChecking=no "%LOCAL_DIR%requirements.txt" %SERVER%:%REMOTE_DIR%/requirements.txt
if errorlevel 1 ( echo ERROR: Failed to upload code & exit /b 1 )

echo [3/4] Uploading Google credentials JSON...
scp -i "%KEY%" -o StrictHostKeyChecking=no "%LOCAL_DIR%config\chatbot-510011-5cddc268bd47.json" %SERVER%:%REMOTE_DIR%/config/chatbot-510011-5cddc268bd47.json
if errorlevel 1 ( echo ERROR: Failed to upload Google credentials & exit /b 1 )

echo [4/4] Installing dependencies and restarting faqbot...
ssh -i "%KEY%" -o StrictHostKeyChecking=no %SERVER% "/home/opc/myenv/bin/pip install -q -r %REMOTE_DIR%/requirements.txt && sudo systemctl restart faqbot && sleep 2 && sudo systemctl status faqbot --no-pager | grep Active"
if errorlevel 1 ( echo ERROR: Failed to restart & exit /b 1 )

echo === Deploy complete ===

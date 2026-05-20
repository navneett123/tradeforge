python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m compileall frontend services
Write-Host "Start services with Docker Compose: docker compose up --build"
Write-Host "Open: http://localhost:8080"

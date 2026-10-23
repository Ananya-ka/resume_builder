.PHONY: run stop restart test

run:
	@./run.sh

stop:
	@echo "Stopping all services..."
	@-lsof -ti :8000 | xargs kill -9 2>/dev/null
	@-lsof -ti :3001 | xargs kill -9 2>/dev/null
	@-pkill -f "celery -A app.worker.tasks" 2>/dev/null
	@-pkill -f "uvicorn app.main:app" 2>/dev/null
	@echo "All services stopped."

restart: stop run

test:
	@cd backend && PATH="/opt/homebrew/bin:/opt/anaconda3/bin:$$PATH" PYTHONPATH=. pytest

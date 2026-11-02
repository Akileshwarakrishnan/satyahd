.PHONY: install test eval redteam run docker clean

install:
	pip install -r requirements.txt
	pip install -e .

test:
	python -m pytest tests/ -v

eval:
	python scripts/eval.py

redteam:
	python scripts/red_team.py --local
	python scripts/red_team.py --local --plugin

smoke:
	python scripts/smoke_test.py

run:
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

docker:
	docker-compose up --build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache

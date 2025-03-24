.PHONY: build build-desktop build-xvfb push push-desktop push-xvfb run run-docker run-desktop run-xvfb all all-desktop all-xvfb setup test test-cov install-test install-dev

# Setup Python environment with uv
setup:
	@echo "Setting up Python environment with uv..."
	@if ! command -v uv &> /dev/null; then \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi
	uv venv --python=python3.12 .venv
	. .venv/bin/activate && uv pip install -r requirements.txt
	. .venv/bin/activate && uv pip install pre-commit watchdog
	. .venv/bin/activate && pre-commit install

dev:
	docker run -e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) \
		-v ${PWD}/operative:/home/operative/.operative/operative \
		-v $(HOME)/.anthropic:/home/operative/.anthropic \
		-p 5900:5900 \
		-p 8501:8501 \
		-p 6080:6080 \
		-p 8080:8080 \
		-it ghcr.io/hanzoai/operative:latest

ghcr-login:
	echo $$GITHUB_PAT | docker login ghcr.io -u $$GITHUB_USERNAME --password-stdin

# Run locally using uv
run:
	uv run -- python3 -m streamlit run operative/operative.py

# Build the Docker images
build: push-xvfb
	docker build -f docker/Dockerfile -t ghcr.io/hanzoai/operative:latest .
build-desktop:
	docker build -f docker/Dockerfile.desktop -t ghcr.io/hanzoai/desktop:latest .
build-xvfb:
	docker build -f docker/Dockerfile.xvfb -t ghcr.io/hanzoai/xvfb:latest .

# Push the Docker images to the registry
push: push-xvfb
	docker push ghcr.io/hanzoai/operative:latest
push-desktop: build-desktop
	docker push ghcr.io/hanzoai/desktop:latest
push-xvfb: build-xvfb
	docker push ghcr.io/hanzoai/xvfb:latest

# Run the Docker containers locally
run-docker:
	docker run -e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) \
		-v $(HOME)/.anthropic:/home/operative/.anthropic \
		-p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
		-it ghcr.io/hanzoai/operative:latest
run-desktop:
	docker run -e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) \
		-v $(HOME)/.anthropic:/home/operative/.anthropic \
		-p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
		-it ghcr.io/hanzoai/desktop:latest
run-xvfb:
	docker run -e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) \
		-v $(HOME)/.anthropic:/home/operative/.anthropic \
		-p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
		-it ghcr.io/hanzoai/xvfb:latest

# Testing targets
install-dev:
	uv venv --python=python3.12 .venv
	. .venv/bin/activate && uv pip install -e ".[dev]"
	. .venv/bin/activate && pre-commit install

install-test:
	uv venv --python=python3.12 .venv
	. .venv/bin/activate && uv pip install -e ".[test]"
	. .venv/bin/activate && uv pip install anthropic>=0.22.0 streamlit>=1.31.0 httpx>=0.27.0

test:
	. .venv/bin/activate && python -m pytest tests/

test-cov:
	. .venv/bin/activate && python -m pytest tests/ --cov=operative --cov-report=term-missing

lint:
	ruff check operative/ tests/

format:
	ruff format operative/ tests/

# Build, push, then run targets
all: build push run-docker
all-desktop: build-desktop push-desktop run-desktop
all-xvfb: build-xvfb push-xvfb run-xvfb

.PHONY: build build-desktop build-xvfb push push-desktop push-xvfb run run-desktop run-xvfb all all-desktop all-xvfb

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
run:
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

# Build, push, then run targets
all: build push run

all-desktop: build-desktop push-desktop run-desktop

all-xvfb: build-xvfb push-xvfb run-xvfb

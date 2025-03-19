.PHONY: build push run all

# Build the Docker image
build:
	docker build -t ghcr.io/hanzoai/operative:latest .

# Push the Docker image to the registry
push:
	docker push ghcr.io/hanzoai/operative:latest

# Run the Docker container locally
run:
	docker run -e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) \
		    		 -v $(HOME)/.anthropic:/home/operative/.anthropic \
					   -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
					   -it ghcr.io/hanzoai/operative:latest

# Build, push, then run
all: build push run

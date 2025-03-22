ARG BASE_IMAGE=ghcr.io/hanzoai/xvfb:latest
FROM ${BASE_IMAGE}

# Setup user
ENV USERNAME=operative
ENV HOME=/home/$USERNAME

# Create user only if it doesn't exist
RUN id -u ${USERNAME} 2>/dev/null || useradd -m -s /bin/bash -d "$HOME" "$USERNAME"

# Ensure home directory exists with proper permissions
RUN mkdir -p $HOME && chown -R $(id -u ${USERNAME}):$(id -g ${USERNAME}) $HOME

# Set sudo permissions
RUN sudo bash -c 'echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers'

USER ${USERNAME}
WORKDIR $HOME

# Install Python 3.12 using uv
ENV UV_PYTHON_VERSION_MAJOR=3
ENV UV_PYTHON_VERSION_MINOR=12
ENV UV_PYTHON_VERSION_PATCH=7
ENV UV_PYTHON_VERSION=$UV_PYTHON_VERSION_MAJOR.$UV_PYTHON_VERSION_MINOR.$UV_PYTHON_VERSION_PATCH

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

ENV PATH="$HOME/.local/bin:$PATH"

# Configure uv
RUN mkdir -p ~/.config/uv && \
    echo '[global]' > ~/.config/uv/config.toml && \
    echo 'disable-pip-version-check = true' >> ~/.config/uv/config.toml

# Copy desktop environment/app files
COPY --chown=$USERNAME:$USERNAME docker/image $HOME/.operative/
COPY --chown=$USERNAME:$USERNAME requirements.txt $HOME/.operative/requirements.txt
COPY --chown=$USERNAME:$USERNAME operative/requirements.txt $HOME/.operative/operative/requirements.txt

# Create virtual environment in project directory
RUN ~/.local/bin/uv venv ~/.operative/.venv && \
    echo 'source ~/.operative/.venv/bin/activate' >> ~/.bashrc

# Install dependencies - use bash explicitly to enable source
RUN /bin/bash -c '. ~/.operative/.venv/bin/activate && \
    ~/.local/bin/uv pip install setuptools==68.0.0 wheel==0.40.0 && \
    ~/.local/bin/uv pip install -r ~/.operative/requirements.txt'

# Copy remaining operative files
COPY --chown=$USERNAME:$USERNAME operative/ $HOME/.operative/operative

ARG DISPLAY_NUM=1
ARG HEIGHT=800
ARG WIDTH=1280
ENV DISPLAY_NUM=$DISPLAY_NUM
ENV DISPLAY=:$DISPLAY_NUM
ENV HEIGHT=$HEIGHT
ENV WIDTH=$WIDTH

# Default endpoints (can be overridden at runtime)
ENV APP_ENDPOINT=operative-app.hanzo.ai
ENV VNC_ENDPOINT=operative-vnc.hanzo.ai
ENV API_ENDPOINT=api.hanzo.ai

RUN chmod +x $HOME/.operative/start_all.sh
ENTRYPOINT [".operative/entrypoint.sh"]

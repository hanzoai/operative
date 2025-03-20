ARG BASE_IMAGE=ghcr.io/hanzoai/xvfb:latest
FROM ${BASE_IMAGE}

# Setup user
ENV USERNAME=operative
ENV HOME=/home/$USERNAME
RUN useradd -m -s /bin/bash -d "$HOME" "$USERNAME"
RUN chown -R ${USERNAME}:${USERNAME} ${HOME}
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER operative
WORKDIR $HOME

# Setup pyenv
RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv && \
    cd ~/.pyenv && src/configure && make -C src && cd .. && \
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc && \
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc

ENV PYENV_ROOT="$HOME/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"
ENV PYENV_VERSION_MAJOR=3
ENV PYENV_VERSION_MINOR=12
ENV PYENV_VERSION_PATCH=7
ENV PYENV_VERSION=$PYENV_VERSION_MAJOR.$PYENV_VERSION_MINOR.$PYENV_VERSION_PATCH

RUN eval "$(pyenv init -)" && \
    pyenv install "$PYENV_VERSION" && \
    pyenv global "$PYENV_VERSION" && \
    pyenv rehash

ENV PATH="$HOME/.pyenv/shims:$HOME/.pyenv/bin:$PATH"

# Only reinstall if requirements.txt changes
COPY --chown=$USERNAME:$USERNAME operative/requirements.txt $HOME/operative/requirements.txt

RUN python -m pip install --upgrade pip==23.1.2 setuptools==68.0.0 wheel==0.40.0 && \
    python -m pip config set global.disable-pip-version-check true && \
    python -m pip install -r "$HOME/operative/requirements.txt"

# Copy desktop environment/app files
COPY --chown=$USERNAME:$USERNAME docker/image $HOME/.operative/
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

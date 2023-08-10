# Starter

## Deployment

Download repository

```bash
git clone https://github.com/Bondifuzz/starter.git
cd starter
```

Build docker image

```bash
docker build -t starter .
```

Run container (locally)

```bash
docker run --net=host --rm -it --name=starter --env-file=.env -v ~/.kube/config:/root/.kube/config starter bash
```

## Local development

### Clone starter repository

All code and scripts are placed to starter repository. Let's clone it.

```bash
git clone https://github.com/Bondifuzz/starter.git
cd starter
```

### Start services starter depends on

Then you should invoke `docker-compose` to start all services starter depends on.

```bash
ln -s local/dotenv .env
ln -s local/docker-compose.yml docker-compose.yml
docker-compose -p starter up -d
```

### Verify access to kubernetes cluster

After that ensure you have an access to local/remote kubernetes cluster and have an appropriate config in `~/.kube` folder. Use commands like `kubectl get namespaces`, `kubectl get pods` to ensure all is ok.

### Run starter

Finally, you can run starter service:

```bash
# Install dependencies
pip3 install -r requirements-dev.txt

# Run service
python3 -m uvicorn \
    --factory starter.app.main:create_app \
    --host 127.0.0.1 \
    --port 8080 \
    --workers 1 \
    --log-config logging.yaml \
    --lifespan on
```

### VSCode extensions

```bash
# Python
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance

# Spell checking
code --install-extension streetsidesoftware.code-spell-checker

# Config
code --install-extension redhat.vscode-yaml
code --install-extension tamasfe.even-better-toml

# Markdown
code --install-extension bierner.markdown-preview-github-styles
code --install-extension yzhang.markdown-all-in-one

# Developer
code --install-extension Gruntfuggly.todo-tree
code --install-extension donjayamanne.githistory
```

### Code documentation

TODO

### Running tests

```bash
# Install dependencies
pip3 install -r requirements-test.txt

# Run unit tests
pytest -vv starter/tests/unit

# Run functional tests
pytest -vv starter/tests/integration
```

### Spell checking

Download cspell and run to check spell in all sources

```bash
sudo apt install nodejs npm
sudo npm install -g cspell
cspell "**/*.{py,md,txt}"
```

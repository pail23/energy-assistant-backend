sudo mkdir -p /data
sudo chown vscode:vscode /data
sudo mkdir -p /config
sudo chown vscode:vscode /config

cp energy_assistant.yaml /config

./scripts/install-client.sh
./scripts/create-dev-db.sh

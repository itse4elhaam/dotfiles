# Install NVM and Node.js (LTS)
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh | bash
export NVM_DIR="$HOME/.nvm"
if [ -d "$NVM_DIR" ] && [ -f "$NVM_DIR/nvm.sh" ]; then
  source "$NVM_DIR/nvm.sh"
fi

node_version_to_install="lts"
nvm install "$node_version_to_install"
nvm use "$node_version_to_install"
nvm alias default "$node_version_to_install"

# Install Bun
curl -fsSL https://bun.sh/install | bash
export PATH="$HOME/.bun/bin:$PATH"

# Install g (GVM)
curl -fsSL https://raw.githubusercontent.com/voidint/g/master/install.sh | bash
export PATH="$HOME/.g/bin:$PATH"
go_version_to_install="lts"
# is this correct?
g install "$go_version_to_install"
g use "$go_version_to_install"
g alias default "$go_version_to_install"


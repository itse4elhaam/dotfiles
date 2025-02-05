#!/bin/bash

# Install LazyGit
LAZYGIT_VERSION=$(curl -s https://api.github.com/repos/jesseduffield/lazygit/releases/latest | jq -r ".tag_name")
curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/download/$LAZYGIT_VERSION/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
tar xf lazygit.tar.gz -C /usr/local/bin lazygit && rm lazygit.tar.gz

# Install Yazi dont think this works though
curl -fsSL https://github.com/sxyazi/yazi/releases/latest/download/yazi-linux.tar.gz | tar xz -C ~/.local/bin

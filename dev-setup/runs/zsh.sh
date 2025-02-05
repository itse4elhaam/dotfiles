#!/bin/bash

# Install and configure Zsh
sudo apt install -y zsh
chsh -s "$(which zsh)"
echo "Zsh installed. Restart shell to apply changes."

# TODO: make this better
cd ~/.dotfiles && stow .

# Prompt user to install JetBrains Mono font
read -rp "Please install the JetBrains Mono font manually. Press ENTER to continue."

# Install Oh-My-Zsh & Powerlevel10k
if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# Install Powerlevel10k theme
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k
source ~/.zshrc

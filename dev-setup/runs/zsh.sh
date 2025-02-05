#!/bin/bash

# Install and configure Zsh
sudo apt install -y zsh
chsh -s "$(which zsh)"
echo "Zsh installed. Restart shell to apply changes."

# TODO: make this better
cd ~/.dotfiles && stow .

# does this work?
mkdir -p ~/.local/share/fonts
cd ~/.local/share/fonts || exit

wget https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip
unzip JetBrainsMono.zip -d JetBrainsMono-NF
rm JetBrainsMono.zip

# Refresh font cache
fc-cache -fv

# Install Oh-My-Zsh & Powerlevel10k
if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# Install Powerlevel10k theme
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k
source ~/.zshrc

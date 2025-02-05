#!/bin/bash
# if system is not ubuntu, exit out

# installs
# install nvm, nvm install lts, nvm use lts and nvm default alias lts
# install nvim - using ppa
# install tmux - using ppa
# install lazygit
# install yazi
# install stow
# install python3 and python-is-python3
# install g (gvm) and set lts as the default alias
# install redis
# install fzf
# install exa
# install xclip
# install bun
# install deno
# install ripgrep
# install jq
# install gcc, build-essentials and other stuff like that which is basic
# install psql and create a user as well with passwords
# install mysql and create a user as well with passwords
# install mongodb


# setup
# create a user named e4elhaam
# clone neovim conf
# install and setup zsh
# warn the user to install the jet brains mono font and continue on pressing enter
# install oh my zsh and powerlevel 10k, also run power level 10k conf
# first mv all dotfiles present in the .dotfiles folder to a bak file and then run stow . in ~/.dotfiles 
# mkdir ~/coding ~/downloads ~/scripts ~/temp
# clone truedevs repo
# open tmux, trigger shift-i and then open neovim in the end

# Ensure the script runs on Ubuntu
if [[ "$(lsb_release -is)" != "Ubuntu" ]]; then
  echo "This script is intended for Ubuntu only. Exiting..."
  exit 1
fi

echo "Welcome to the installation script. Let's start with updates and package installations."


# Install tmux (via PPA)
sudo add-apt-repository -y ppa:pi-rho/dev
sudo apt update && sudo apt install -y tmux

# Install LazyGit
LAZYGIT_VERSION=$(curl -s https://api.github.com/repos/jesseduffield/lazygit/releases/latest | jq -r ".tag_name")
curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/download/$LAZYGIT_VERSION/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
tar xf lazygit.tar.gz -C /usr/local/bin lazygit && rm lazygit.tar.gz

# Install Yazi
curl -fsSL https://github.com/sxyazi/yazi/releases/latest/download/yazi-linux.tar.gz | tar xz -C ~/.local/bin


# Create a new user (if not exists)
if ! id "e4elhaam" &>/dev/null; then
  sudo useradd -m -s /bin/bash e4elhaam
  echo "User 'e4elhaam' created."
fi

# Clone Neovim Configuration
git clone https://github.com/itse4elhaam/nvim-config ~/.config/nvim

# Install and configure Zsh
sudo apt install -y zsh
chsh -s "$(which zsh)"
echo "Zsh installed. Restart shell to apply changes."

# Prompt user to install JetBrains Mono font
read -rp "Please install the JetBrains Mono font manually. Press ENTER to continue."

read -rp "Do you want to go ahead with oh my zsh and other setup, any key to continue"

# Install Oh-My-Zsh & Powerlevel10k
if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# Install Powerlevel10k theme
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k
sed -i 's|ZSH_THEME=.*|ZSH_THEME="powerlevel10k/powerlevel10k"|' ~/.zshrc
source ~/.zshrc

# Backup existing dotfiles and apply stow
mkdir -p ~/.dotfiles_backup
mv ~/.dotfiles/* ~/.dotfiles_backup/
git clone https://github.com/itse4elhaam/dotfiles ~/.dotfiles
cd ~/.dotfiles && stow .

# Create essential directories
mkdir -p ~/coding ~/downloads ~/scripts ~/temp

# Clone TrueDevs repo
git clone https://github.com/truedevs/repo ~/coding/truedevs

# Open Tmux, trigger Plugin Install, then launch Neovim
tmux new-session -d -s setup 'sleep 2; tmux send-keys "prefix I" C-m'
tmux new-session -d -s dev 'nvim'

echo "Installation complete! Restart your terminal to apply all changes."

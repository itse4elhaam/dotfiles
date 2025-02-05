#!/bin/bash

# is this the best way?
sudo add-apt-repository -y ppa:neovim-ppa/unstable
sudo apt update && sudo apt install -y neovim

git clone https://github.com/itse4elhaam/nvim-config ~/.config/nvim

sudo add-apt-repository -y ppa:pi-rho/dev
sudo apt update && sudo apt install -y tmux

# Open Tmux, trigger Plugin Install, then launch Neovim
tmux new-session -d -s setup 'sleep 2; tmux send-keys "prefix I" C-m'
# Clone TrueDevs repo
git clone https://github.com/truedevs/repo ~/coding/truedevs
# TODO: create dotfiles/TrueDevs/nvim tmux sessions
tmux new-session -d -s dev 'nvim'

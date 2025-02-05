#!/bin/bash

# is this the best way?
sudo add-apt-repository -y ppa:neovim-ppa/unstable
sudo apt update && sudo apt install -y neovim

sudo add-apt-repository -y ppa:pi-rho/dev
sudo apt update && sudo apt install -y tmux

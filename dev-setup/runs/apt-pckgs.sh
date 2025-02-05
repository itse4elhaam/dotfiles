#!/bin/bash

# Update and upgrade the system
sudo apt update && sudo apt upgrade -y

 packages=(
  "software-properties-common"
  "curl"
  "git"
  "wget"
  "unzip"
  "build-essential"
  "python3"
  "python-is-python3"
  "redis"
  "fzf"
  "exa"
  "xclip"
  "ripgrep"
  "jq"
  "gcc"
  "make"
  "postgresql"
  "postgresql-contrib"
  "mysql-server"
  "mongodb"
  "stow"
)

sudo apt install -y "${packages[@]}"

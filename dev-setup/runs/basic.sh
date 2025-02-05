#!/bin/bash


# Create a new user (if not exists)
if ! id "e4elhaam" &>/dev/null; then
  sudo useradd -m -s /bin/bash e4elhaam
  echo "User 'e4elhaam' created."
fi

mkdir -p ~/coding ~/downloads ~/scripts ~/temp

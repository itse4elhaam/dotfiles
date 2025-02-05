#!/bin/bash

db_username="elhaam"
db_pw="testpass"

sudo systemctl enable --now postgresql
sudo -u postgres psql -c "CREATE USER $db_username WITH PASSWORD '$db_pw';"
sudo -u postgres psql -c "ALTER USER $db_username CREATEDB;"

sudo systemctl enable --now mysql
sudo mysql -e "CREATE USER '$db_username'@'localhost' IDENTIFIED BY '$db_pw';"
sudo mysql -e "GRANT ALL PRIVILEGES ON *.* TO '$db_username'@'localhost' WITH GRANT OPTION;"

# Setup MongoDB
sudo systemctl enable --now mongodb

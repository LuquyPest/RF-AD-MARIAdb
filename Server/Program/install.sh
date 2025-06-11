# #install SSH
sudo systemctl enable ssh
sudo systemctl start ssh

# Install MariaDB
sudo apt install mariadb-server mariadb-client -y
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Install pip
sudo apt install -y pip

# Install libglib
sudo apt install libglib2.0-dev -y

# Update and install system dependencies
sudo apt-get update && \
sudo apt-get install -y \
    gcc \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    build-essential \
    python3-flask

# Install Python modules globally
sudo pip install Flask==2.0.2 Werkzeug==2.0.3 python-ldap==3.3.1 schedule==1.2.1

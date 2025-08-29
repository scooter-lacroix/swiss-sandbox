#!/bin/bash
# Installation script for Ultimate Swiss Army Knife MCP Server
# This script installs all system dependencies

set -e

echo "================================================"
echo "Ultimate Swiss Army Knife MCP Server Installation"
echo "================================================"

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ -f /etc/debian_version ]; then
        OS="debian"
        PKG_MANAGER="apt-get"
    elif [ -f /etc/redhat-release ]; then
        OS="redhat"
        PKG_MANAGER="dnf"
    elif [ -f /etc/fedora-release ]; then
        OS="fedora"
        PKG_MANAGER="dnf"
    else
        OS="unknown"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    PKG_MANAGER="brew"
else
    OS="unknown"
fi

echo "Detected OS: $OS"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if package is installed
package_installed() {
    local package=$1
    if [ "$OS" == "debian" ]; then
        dpkg -l | grep -q "^ii  $package"
    elif [ "$OS" == "fedora" ] || [ "$OS" == "redhat" ]; then
        rpm -q "$package" >/dev/null 2>&1
    elif [ "$OS" == "macos" ]; then
        brew list "$package" >/dev/null 2>&1
    else
        return 1
    fi
}

# Install system packages based on OS
install_system_deps() {
    echo "Checking and installing system dependencies..."

    if [ "$OS" == "debian" ]; then
        packages="python3 python3-venv python3-pip docker.io docker-compose postgresql postgresql-client redis-server git curl wget build-essential libmagic1 ffmpeg golang-go"
        to_install=""
        for pkg in $packages; do
            if ! package_installed "$pkg"; then
                to_install="$to_install $pkg"
            fi
        done
        if [ -n "$to_install" ]; then
            sudo apt-get update
            sudo apt-get install -y $to_install
        else
            echo "All Debian packages are already installed."
        fi

    elif [ "$OS" == "fedora" ] || [ "$OS" == "redhat" ]; then
        packages="python3 python3-pip docker docker-compose postgresql postgresql-server redis git curl wget gcc gcc-c++ make file-devel ffmpeg golang"
        to_install=""
        for pkg in $packages; do
            if ! package_installed "$pkg"; then
                to_install="$to_install $pkg"
            fi
        done
        if [ -n "$to_install" ]; then
            sudo dnf install -y $to_install
        else
            echo "All Fedora/RHEL packages are already installed."
        fi

    elif [ "$OS" == "macos" ]; then
        # Check if Homebrew is installed
        if ! command_exists brew; then
            echo "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi

        packages="python3 docker docker-compose postgresql redis git libmagic ffmpeg go"
        to_install=""
        for pkg in $packages; do
            if ! brew list "$pkg" >/dev/null 2>&1; then
                to_install="$to_install $pkg"
            fi
        done
        if [ -n "$to_install" ]; then
            brew install $to_install
        else
            echo "All macOS packages are already installed."
        fi
    else
        echo "Unsupported OS. Please install dependencies manually."
        exit 1
    fi
}

# Install Go if not present
install_go() {
    if ! command_exists go; then
        echo "Installing Go..."
        GO_VERSION="1.21.5"
        
        if [ "$OS" == "macos" ]; then
            brew install go
        else
            wget "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"
            sudo tar -C /usr/local -xzf "go${GO_VERSION}.linux-amd64.tar.gz"
            rm "go${GO_VERSION}.linux-amd64.tar.gz"
            
            # Add Go to PATH
            echo 'export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin' >> ~/.bashrc
            export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
        fi
    else
        echo "Go is already installed: $(go version)"
    fi
}

# Install Zoekt
install_zoekt() {
    echo "Installing Zoekt search engine..."
    
    # Ensure Go is available
    if ! command_exists go; then
        echo "Go is required for Zoekt. Installing Go first..."
        install_go
    fi
    
    # Install Zoekt tools
    go install github.com/sourcegraph/zoekt/cmd/zoekt-index@latest
    go install github.com/sourcegraph/zoekt/cmd/zoekt@latest
    go install github.com/sourcegraph/zoekt/cmd/zoekt-webserver@latest
    
    echo "Zoekt installed to ~/go/bin/"
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/go/bin:"* ]]; then
        echo 'export PATH=$PATH:$HOME/go/bin' >> ~/.bashrc
        export PATH=$PATH:$HOME/go/bin
    fi
}

# Setup PostgreSQL
setup_postgresql() {
    echo "Checking and setting up PostgreSQL..."

    if ! command_exists psql; then
        echo "PostgreSQL client not found. Please install PostgreSQL first."
        return 1
    fi

    # Check if PostgreSQL service is running
    if systemctl is-active --quiet postgresql; then
        echo "PostgreSQL service is already running."
    else
        echo "Starting PostgreSQL service..."
        if [ "$OS" == "fedora" ] || [ "$OS" == "redhat" ]; then
            # Check if initialized
            if [ ! -d /var/lib/pgsql/data/base ]; then
                sudo postgresql-setup --initdb --unit postgresql
            fi
            sudo systemctl enable postgresql
            sudo systemctl start postgresql
        elif [ "$OS" == "debian" ]; then
            sudo systemctl enable postgresql
            sudo systemctl start postgresql
        elif [ "$OS" == "macos" ]; then
            brew services start postgresql
        fi
    fi

    # Check if database exists
    if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw ultimate_sandbox; then
        echo "Database 'ultimate_sandbox' already exists."
    else
        sudo -u postgres psql -c "CREATE DATABASE ultimate_sandbox;" 2>/dev/null || echo "Failed to create database (may already exist)"
    fi

    # Check if user exists
    if sudo -u postgres psql -t -c "SELECT 1 FROM pg_roles WHERE rolname='sandbox_user';" | grep -q 1; then
        echo "User 'sandbox_user' already exists."
    else
        sudo -u postgres psql -c "CREATE USER sandbox_user WITH PASSWORD 'sandbox_pass';" 2>/dev/null || echo "Failed to create user"
    fi

    # Grant privileges
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ultimate_sandbox TO sandbox_user;" 2>/dev/null || echo "Failed to grant privileges"

    echo "PostgreSQL setup complete"
}

# Setup Redis
setup_redis() {
    echo "Checking and setting up Redis..."

    if ! command_exists redis-server; then
        echo "Redis server not found. Please install Redis first."
        return 1
    fi

    # Check if Redis service is running
    if systemctl is-active --quiet redis; then
        echo "Redis service is already running."
    else
        echo "Starting Redis service..."
        if [ "$OS" == "macos" ]; then
            brew services start redis
        else
            sudo systemctl enable redis
            sudo systemctl start redis
        fi
    fi

    echo "Redis setup complete"
}

# Setup Docker
setup_docker() {
    echo "Checking and setting up Docker..."

    if ! command_exists docker; then
        echo "Docker is not installed. Please install it first."
        return 1
    fi

    # Check if Docker is running
    if docker info >/dev/null 2>&1; then
        echo "Docker is already running."
    else
        echo "Starting Docker service..."
        if [ "$OS" != "macos" ]; then
            sudo systemctl enable docker
            sudo systemctl start docker
            # Add current user to docker group if not already
            if ! groups $USER | grep -q docker; then
                sudo usermod -aG docker $USER
                echo "Added user to docker group. Please log out and back in for changes to take effect."
            fi
        else
            echo "Please start Docker Desktop on macOS."
        fi
    fi

    echo "Docker setup complete."
}

# Create required directories
create_directories() {
    echo "Creating required directories..."
    
    mkdir -p ~/.ultimate_sandbox/{workspaces,artifacts,search_index,backups,logs}
    mkdir -p ~/go/bin
    
    # Create log directory with proper permissions
    sudo mkdir -p /var/log/ultimate_sandbox
    sudo chown $USER:$USER /var/log/ultimate_sandbox
    
    echo "Directories created"
}

# Main installation flow
main() {
    echo "Starting installation..."
    
    # Install system dependencies
    install_system_deps
    
    # Install uv package manager
    if ! command_exists uv; then
        echo "Installing uv package manager..."
        export UV_INSTALL_DIR=/usr/local && curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="/usr/local/bin:$PATH"
    else
        echo "uv package manager is already installed."
    fi

    # Install nvm and Node.js
    if [ ! -d "$HOME/.nvm" ] || ! command_exists nvm; then
        echo "Installing nvm..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
        echo "nvm is already installed."
    fi

    echo "Setting up Node.js..."
    export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    if ! command_exists node; then
        nvm install --lts
    else
        echo "Node.js is already installed."
    fi

    # Install JavaScript linters globally
    if command_exists npm; then
        echo "Installing JavaScript linters..."
        npm install -g eslint prettier typescript
    else
        echo "npm not found, skipping JavaScript linters installation."
    fi

    # Install Go and Zoekt
    install_go
    install_zoekt
    
    # Setup services
    setup_postgresql
    setup_redis
    setup_docker
    
    # Create directories
    create_directories
    
    echo ""
    echo "================================================"
    echo "System dependencies installation complete!"
    echo "================================================"
    echo ""
    echo "Next steps:"
    echo "1. Log out and back in for Docker group changes"
    echo "2. Activate Python virtual environment:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "3. Install Python dependencies:"
    echo "   pip install -r requirements.txt"
    echo "4. Run the server:"
    echo "   python src/sandbox/ultimate/server.py"
    echo ""
    echo "Zoekt binaries installed to: ~/go/bin/"
    echo "Make sure ~/go/bin is in your PATH"
}

# Run main installation
main

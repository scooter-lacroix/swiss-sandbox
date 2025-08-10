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

# Install system packages based on OS
install_system_deps() {
    echo "Installing system dependencies..."
    
    if [ "$OS" == "debian" ]; then
        sudo apt-get update
        sudo apt-get install -y \
            python3.11 python3.11-venv python3-pip \
            docker.io docker-compose \
            postgresql postgresql-client \
            redis-server \
            git curl wget \
            build-essential \
            libmagic1 \
            ffmpeg \
            golang-go
            
    elif [ "$OS" == "fedora" ] || [ "$OS" == "redhat" ]; then
        sudo dnf install -y \
            python3.11 python3-pip \
            docker docker-compose \
            postgresql postgresql-server \
            redis \
            git curl wget \
            gcc gcc-c++ make \
            file-devel \
            ffmpeg \
            golang
            
    elif [ "$OS" == "macos" ]; then
        # Check if Homebrew is installed
        if ! command_exists brew; then
            echo "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        brew install \
            python@3.11 \
            docker docker-compose \
            postgresql \
            redis \
            git \
            libmagic \
            ffmpeg \
            go
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
    echo "Setting up PostgreSQL..."
    
    if [ "$OS" == "fedora" ] || [ "$OS" == "redhat" ]; then
        # Initialize PostgreSQL on Fedora/RHEL
        sudo postgresql-setup --initdb --unit postgresql
        sudo systemctl enable postgresql
        sudo systemctl start postgresql
    elif [ "$OS" == "debian" ]; then
        sudo systemctl enable postgresql
        sudo systemctl start postgresql
    fi
    
    # Create database and user
    sudo -u postgres psql -c "CREATE DATABASE ultimate_sandbox;" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE USER sandbox_user WITH PASSWORD 'sandbox_pass';" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ultimate_sandbox TO sandbox_user;" 2>/dev/null || true
    
    echo "PostgreSQL setup complete"
}

# Setup Redis
setup_redis() {
    echo "Setting up Redis..."
    
    if [ "$OS" == "macos" ]; then
        brew services start redis
    else
        sudo systemctl enable redis
        sudo systemctl start redis
    fi
    
    echo "Redis setup complete"
}

# Setup Docker
setup_docker() {
    echo "Setting up Docker..."
    
    if [ "$OS" != "macos" ]; then
        # Add current user to docker group
        sudo usermod -aG docker $USER
        
        # Start Docker service
        sudo systemctl enable docker
        sudo systemctl start docker
        
        echo "Docker setup complete. Please log out and back in for group changes to take effect."
    else
        echo "Please ensure Docker Desktop is installed and running on macOS"
    fi
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
    echo "   python3.11 -m venv venv"
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

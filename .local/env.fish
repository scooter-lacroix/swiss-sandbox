if not contains "$HOME/swiss-sandbox/.local" $PATH
    # Prepending path in case a system-installed binary needs to be overridden
    set -x PATH "$HOME/swiss-sandbox/.local" $PATH
end

# naval-cli --no-ascii
# Add deno completions to search path
if [[ ":$FPATH:" != *":/home/$USER/.zsh/completions:"* ]]; then export FPATH="/home/$USER/.zsh/completions:$FPATH"; fi
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

if [ -f ~/.zshenv_local ]; then
  source ~/.zshenv_local
fi
# assuming you cloned zff to ~/zff
if [[ -f ~/zff/zff.sh ]]; then
  source ~/zff/zff.sh
fi

# TODO: move all aliases to a different file
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
plugins=(git zsh-autosuggestions zsh-syntax-highlighting fzf-tab sudo dirhistory zsh-autopair asdf)

if command -v nvim > /dev/null 2>&1; then
  export EDITOR=nvim
else
  export EDITOR=vim
fi

if [ -f "./keys.local/source.sh" ]; then
  source "./keys.local/source.sh"
fi

source $ZSH/oh-my-zsh.sh
# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
# . "$HOME/.cargo/env"

export PATH="$HOME/.nvm/versions/node/v22.17.0/bin:$PATH"
export PATH=$PATH:/home/$USER/.nvm/versions/node/v19.9.0/bin
export PATH="/home/e4elhaam/.bun/bin:$PATH"
export NODE_OPTIONS="--max-old-space-size=8192"
export PATH=$PATH:"$HOME/.nvm"
export PATH=$PATH:"$HOME/.cargo/bin"
export PATH=$PATH:"$HOME/.bun/bin"
export PATH=$PATH:"$HOME/flutter/bin"
export N_PREFIX=$HOME/.
export PATH="$HOME/.wakatime:$PATH"
export PATH="$PATH:/opt/nvim-linux64/bin"
export PATH=$PATH:/usr/local/go/bin
PATH=~/.console-ninja/.bin:$PATH
export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
export PATH="$HOME/downloads/zig-linux-x86_64-0.11.0:$PATH"
export PATH="$PATH:/home/$USER/.local/bin"

export GOPATH=$HOME/go
export PATH=$PATH:$GOROOT/bin:$GOPATH/bin

# === aliases ===
alias napp='ngrok http --url=engaging-grizzly-merry.ngrok-free.app'
alias fd='fdfind'
alias vimdb='nvim -c "DBUI" --cmd "let g:auto_session_enabled = v:false"'
alias vimdbee='nvim -c "lua require("dbee").open()" --cmd "let g:auto_session_enabled = v:false"'
alias grandport='echo $((RANDOM % 1000 + 3000)) | xclip -selection clipboard'
alias ls="exa -a --icons"
alias ll="exa -a --icons --long"
alias rmid="rm *.Identifier"
# Aliases for common Windows utilities - wsl
alias ex='explorer.exe .'
alias notepad='notepad.exe'
alias clip='xcopy'
alias edge='msedge.exe'
# for cd:
alias ..='cd ..'
alias .2='cd ../..'
alias .3='cd ../../..'
alias .4='cd ../../../..'
alias cp="cp -i"
alias mv="mv -i"
# others
# copy cmd from history
alias ccfh="history | tac | fzf --height 40% | awk '{\$1=\"\"; print \$0}' | xclip -selection clipboard"
alias cpth='pwd | tr -d "\n" | xcopy'
alias cwp='echo "\\\\\wsl.localhost\\\Ubuntu${PWD//\//\\\\}" | xcopy'
alias pn=pnpm
alias bn=bun
alias cat="bat"
alias tls="tmux ls"
alias tmuxt="tmux set-option -g status \$(tmux show-option -gqv status | sed 's/on/off/;t;s/off/on/')"
alias oc="code ."
alias tmux="tmux -2"
alias ov="vim .; clear"
alias sp="supabase"
alias xcopy="xclip -selection clipboard"
alias cls='clear'
alias rt='source ~/.zshrc'
alias lgit=lazygit
alias lsql=lazysql
alias gty="ghostty"
alias killport='f() { sudo kill -9 $(sudo lsof -t -i:$1); }; f'
# vim alias
alias vi=vim
alias vim=nvim
alias tai=tmuxai
alias oc="opencode --continue"
ai() {
  sudo apt install "$1" -y
}
nvmiu() {
  nvm install "$1" && nvm use "$1"
}
tmuxai() {
  # colors
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  NC='\033[0m' # no color

 if [[ "$(basename "$PWD")" == "ai" ]]; then
    echo -e "${RED}❌ Cannot run tmuxai inside a directory named 'ai'.${NC}"
    return 1
  fi

  # portable read with prompt
  prompt_confirm() {
    if [ -n "$ZSH_VERSION" ]; then
      read "?$1 " ans
    else
      read -p "$1 " ans
    fi
    [[ "$ans" =~ ^[Yy]$ ]]
  }

  if tmux has-session -t ai 2>/dev/null; then
    echo -e "${YELLOW}⚠️  A tmux session named 'ai' already exists.${NC}"
    if prompt_confirm "👉 Do you want to kill and recreate it? (y/N):"; then
      echo -e "${RED}🗑️  Killing old 'ai' session...${NC}"
      tmux kill-session -t ai
    else
      echo -e "${GREEN}✅ Using existing 'ai' session...${NC}"
      if [ -n "$TMUX" ]; then
        echo -e "${BLUE}🔀 Switching client to 'ai'...${NC}"
        tmux switch-client -t ai
      else
        echo -e "${BLUE}📎 Attaching to 'ai'...${NC}"
        tmux attach -t ai
      fi
      return
    fi
  fi

  echo -e "${BLUE}🚀 Creating new tmux session 'ai'...${NC}"

  tmux new-session -d -s ai -n crush "crush"
  echo -e "   ${GREEN}✓ Window 'crush' created${NC}"

  tmux new-window -t ai -n qwen "qwen"
  echo -e "   ${GREEN}✓ Window 'qwen' created${NC}"

  # gemini window with two panes
  tmux new-window -t ai -n gemini "gemini --model=gemini-2.5-flash"
  tmux split-window -h -t ai:gemini "gemini --model=gemini-2.5-pro"
  tmux select-layout -t ai:gemini even-horizontal
  echo -e "   ${GREEN}✓ Window 'gemini' created with two 50% panes${NC}"

  tmux new-window -t ai -n cursor "cursor-agent"
  echo -e "   ${GREEN}✓ Window 'cursor' created${NC}"

  tmux new-window -t ai -n copilot "copilot"
  echo -e "   ${GREEN}✓ Window 'copilot' created${NC}"

  # jump back to first window (crush)
  tmux select-window -t ai:1
  echo -e "${GREEN}✅ All windows ready! Starting in 'crush'.${NC}"

  if [ -n "$TMUX" ]; then
    echo -e "${BLUE}🔀 Switching client to 'ai'...${NC}"
    tmux switch-client -t ai
  else
    echo -e "${BLUE}📎 Attaching to 'ai'...${NC}"
    tmux attach -t ai
  fi
}
# fzf 
# alias tf='tmux attach-session -t $(tmux list-sessions -F "#{session_name}" | fzf --height 40%)'
alias tf='t'
alias tmuxf='tmux attach-session -t $(tmux list-sessions -F "#{session_name}" | fzf --height 40%)'
alias nvimf='fzf --preview "cat {}" | xargs -r nvim'
alias catf='fzf --height 40% --preview "cat {}"'
alias vimf='fzf --height 40% --preview "cat {}" | xargs -r vim'
alias cdf='cd "$(find . -type d | fzf --height 40%)"'
alias psf="ps aux | fzf --preview 'ps --forest -o pid,cmd --pid=$(echo {} | awk "{print \$2}")' --preview-window=up:3"
# To see if a command is aliased, a file, or a built-in command
alias checkcommand="type -t"
alias openports='netstat -nape --inet'

if grep -qi microsoft /proc/version && [[ $(uname -r) == *microsoft* ]]; then
  alias xdg-open="wslview"
else
  alias xdg-open="xdg-open"
fi


# === alias functions ===
function jpm() {
  if [ -f "yarn.lock" ]; then
    yarn "$@"
  elif [ -f "pnpm-lock.yaml" ]; then
    pnpm "$@"
  elif [ -f "package-lock.json" ]; then
    npm "$@"
  elif [ -f "bun.lockb" ]; then
    bun "$@"
  elif [ -f "deno.lock" ]; then
    deno "$@"
  else
    echo "No known package manager lock file found."
    return 1
  fi
}
function rns() {
    DIR_IN_Q="/home/$USER/.local/share/nvim/sessions"
    content=$(command ls -1 "$DIR_IN_Q")  # Store the output of ls in 'content'
    converted_curr_dir="$(echo "$(pwd)" | sed 's/\//%2F/g; s/\./%2E/g').vim"  # Convert current directory to desired format
    top_match=$(echo "$content" | fzf --filter "$converted_curr_dir" | head -n 1)  # Get the top match using fzf

    # Check if no match was selected
    if [ -z "$top_match" ]; then
        echo "No match found!"
        return 1  # Exit the function if no match was found
    fi

    # Ask for confirmation before deleting
    echo "Are you sure you want to delete $top_match? (y/n)"
    read -r confirmation

    # Confirm deletion
    if [ "$confirmation" != "n" ] || [ "$confirmation" != "N" ] ]; then
        rm -rf "$DIR_IN_Q/$top_match"  # Delete the top match if confirmed
        echo "$DIR_IN_Q/$top_match has been deleted."
    else
        echo "Deletion of $top_match was canceled."
    fi
}

function cmkdir() {
    mkdir -p "$1"         # Create the directory (and parent directories if needed)
    if [ $? -eq 0 ]; then # Check if directory creation was successful
        cd "$1"           # Change into the newly created directory
    else
        echo "Error creating directory"
    fi
}
# used to create a tmux session with automation
function tans() {
    # If a session name is provided, use it
    if [ -n "$1" ]; then
        session_name="$1"
    else
        # Get the current directory
        current_dir=$(pwd)
        # Check if the current directory is the home directory
        if [ "$current_dir" = "$HOME" ]; then
            session_name="~"
        else
            # Get the basename of the current directory
            session_name=$(basename "$current_dir")
        fi
    fi
    # Start a new tmux session with the derived or provided session name
    tmux new-session -A -s "$session_name" -n "$session_name"
}
# Goes up a specified number of directories  (i.e. up 4)
up() {
	local d=""
	limit=$1
	for ((i = 1; i <= limit; i++)); do
		d=$d/..
	done
	d=$(echo $d | sed 's/^\///')
	if [ -z "$d" ]; then
		d=..
	fi
	cd $d
}
# IP address lookup
function whatsmyip () {
    # Internal IP Lookup.
    if command -v ip &> /dev/null; then
        echo -n "Internal IP: "
        ip addr show wlan0 | grep "inet " | awk '{print $2}' | cut -d/ -f1
    else
        echo -n "Internal IP: "
        ifconfig wlan0 | grep "inet " | awk '{print $2}'
    fi
    # External IP Lookup
    echo -n "External IP: "
    curl -s ifconfig.me
}
alias whatismyip="whatsmyip"
# Automatically do an ls after each cd, z, or zoxide
cdandls () {
	if [ -n "$1" ]; then
		builtin cd "$@" && ls
	else
		builtin cd ~ && ls
	fi
}
alias cdls="cdandls"
# Function to insert and execute 'cdi' command silently, lets me search thru my recently opened files
cdi_command() {
  zle -I
  BUFFER='cdi'
  zle accept-line
}

# Bind the Ctrl+f key combination to the cdi_command function
zle -N cdi_command
bindkey '^F' cdi_command
bindkey '^H' backward-kill-word
bindkey '^[[1;6D' emacs-backward-word
bindkey '^[[1;6C' emacs-forward-word
bindkey '^p' history-search-backward
bindkey '^n' history-search-forward

fancy-ctrl-z () {
  if [[ $#BUFFER -eq 0 ]]; then
    BUFFER="fg"
    zle accept-line
  else
    zle push-input
    zle clear-screen
  fi
}
zle -N fancy-ctrl-z
bindkey '^Z' fancy-ctrl-z

autoload -Uz compinit

HISTSIZE=15000
HISTFILE=~/.zsh_history
SAVEHIST=$HISTSIZE
HISTDUP=erase
setopt=appendhistory
setopt sharehistory
setopt hist_ignore_space
setopt hist_ignore_all_dups
setopt hist_ignore_dups
setopt hist_save_no_dups
setopt hist_find_no_dups


export PATH="$HOME/.local/bin:$PATH"
# zstyle ':completion:*' menu select
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' menu no
zstyle ':fzf-tab:complete:cd:*' fzf-preview 'ls --color $realpath'
zstyle ':fzf-tab:complete:__zoxide_z:*' fzf-preview 'ls --color $realpath'

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
eval "$(zoxide init --cmd cd zsh)"

if [ -f /usr/share/doc/fzf/examples/key-bindings.zsh ]; then
  source /usr/share/doc/fzf/examples/key-bindings.zsh
fi

if [ -f /usr/share/doc/fzf/examples/completion.zsh ]; then
  source /usr/share/doc/fzf/examples/completion.zsh
fi

fpath+=${ZSH_CUSTOM:-${ZSH:-~/.oh-my-zsh}/custom}/plugins/zsh-completions/src
fpath+=~/.zfunc

# fnm
FNM_PATH="/home/$USER/.local/share/fnm"
if [ -d "$FNM_PATH" ]; then
  export PATH="/home/$USER/.local/share/fnm:$PATH"
  eval "`fnm env`"
fi

# pnpm
export PNPM_HOME="/home/$USER/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac

export GOPATH="$HOME/go"; export GOROOT="$HOME/.go"; export PATH="$GOPATH/bin:$PATH"; # g-install: do NOT edit, see https://github.com/stefanmaric/g
alias gvm="$GOPATH/bin/g"; # g-install: do NOT edit, see https://github.com/stefanmaric/g
# ~/.tmux/plugins
export PATH=$HOME/.tmux/plugins/tmux-session-wizard/bin:$PATH
# ~/.config/tmux/plugins
export PATH=$HOME/.config/tmux/plugins/tmux-session-wizard/bin:$PATH

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/home/$USER/miniconda3/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/$USER/miniconda3/etc/profile.d/conda.sh" ]; then
        . "/home/$USER/miniconda3/etc/profile.d/conda.sh"
    else
        export PATH="/home/$USER/miniconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<


# bun completions
[ -s "/home/$USER/.bun/_bun" ] && source "/home/$USER/.bun/_bun"

tmux-git-autofetch() {(/home/$USER/.tmux/plugins/tmux-git-autofetch/git-autofetch.tmux --current &)}
add-zsh-hook chpwd tmux-git-autofetch
    

tmux-window-name() {
	($TMUX_PLUGIN_MANAGER_PATH/tmux-window-name/scripts/rename_session_windows.py &)
}

add-zsh-hook chpwd tmux-window-name
# . "/home/$USER/.deno/env"


[ -s "${HOME}/.g/env" ] && \. "${HOME}/.g/env"  # g shell setup

export TERM="xterm-256color"

zff-widget() {
  if [[ -n "$BUFFER" ]]; then
    # Insert path if typed something
    zffi
  else
    # Empty prompt: open file
    zff
    zle reset-prompt
  fi
}
zle -N zff-widget
bindkey '^@' zff-widget # Ctrl + space
# naval-cli --no-ascii

# opencode
export PATH=/home/$USER/.opencode/bin:$PATH

# wtc - worktree code: parallel development with git worktrees
wtc() {
  # colors (properly scoped as local)
  local RED='\033[0;31m'
  local GREEN='\033[0;32m'
  local YELLOW='\033[1;33m'
  local BLUE='\033[0;34m'
  local NC='\033[0m'

  # validate we're in a git repo
  if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Not a git repository${NC}"
    return 1
  fi

  # get branch name from argument or fzf
  local branch_name="$1"
  local force_recreate="$2"
  
  if [[ -z "$branch_name" ]]; then
    # check if fzf is available
    if ! command -v fzf &> /dev/null; then
      echo -e "${RED}❌ fzf is not installed. Provide branch name as argument.${NC}"
      return 1
    fi
    
    echo -e "${BLUE}🔍 Select a branch...${NC}"
    
    # get all branches (local + remote) and let user select
    branch_name=$(git branch -a | \
      sed 's/^[* ]*//g' | \
      sed 's/remotes\/origin\///g' | \
      grep -v 'HEAD ->' | \
      sort -u | \
      fzf --height=40% \
          --border=rounded \
          --prompt="Select branch: " \
          --preview='git log --oneline --graph --date=short --pretty="format:%C(auto)%cd %h%d %s" {} 2>/dev/null | head -50' \
          --preview-window=right:60%:wrap)
    
    # check if user cancelled fzf
    if [[ -z "$branch_name" ]]; then
      echo -e "${YELLOW}⚠️  No branch selected. Cancelled.${NC}"
      return 0
    fi
    
    echo -e "${GREEN}✓ Selected: $branch_name${NC}"
  fi

  # get project name (sanitized for special characters)
  local project_name=$(basename "$(git rev-parse --show-toplevel)" | sed 's/[^a-zA-Z0-9_-]/-/g')
  local original_path=$(git rev-parse --show-toplevel)
  
  # create ~/worktrees if it doesn't exist
  local worktrees_dir="$HOME/worktrees"
  if [[ ! -d "$worktrees_dir" ]]; then
    echo -e "${BLUE}📁 Creating $worktrees_dir${NC}"
    mkdir -p "$worktrees_dir"
  fi

  # prune dead worktrees before creating new ones
  git worktree prune 2>/dev/null
  
  # sanitize branch name comprehensively (handles /, $, :, spaces, special chars)
  local sanitized_branch=$(echo "$branch_name" | sed 's/[^a-zA-Z0-9_-]/-/g')
  local worktree_dir="$worktrees_dir/${project_name}-${sanitized_branch}"
  local session_name="${project_name}-${sanitized_branch}"
  
  # helper function to detect package manager
  _detect_package_manager() {
    local check_path="$1"
    if [[ -f "$check_path/bun.lockb" ]]; then
      echo "bun"
    elif [[ -f "$check_path/pnpm-lock.yaml" ]]; then
      echo "pnpm"
    elif [[ -f "$check_path/yarn.lock" ]]; then
      echo "yarn"
    elif [[ -f "$check_path/package-lock.json" ]]; then
      echo "npm"
    else
      echo ""
    fi
  }
  
  # helper function to setup tmux session (NO 'local' keyword before function!)
  _setup_session() {
    # kill existing session if force recreate requested
    if [[ "$force_recreate" == "--force" ]]; then
      tmux kill-session -t "$session_name" 2>/dev/null
      echo -e "${YELLOW}🔄 Force recreating session...${NC}"
    fi
    
    # create tmux session (if it doesn't exist)
    if ! tmux has-session -t "$session_name" 2>/dev/null; then
      echo -e "${BLUE}🚀 Creating tmux session '$session_name'...${NC}"
      
      # window 1: neovim (check if installed)
      if command -v nvim &> /dev/null; then
        tmux new-session -d -s "$session_name" -n "nvim" -c "$worktree_dir"
        tmux send-keys -t "$session_name:nvim" "nvim" Enter
      else
        tmux new-session -d -s "$session_name" -n "shell" -c "$worktree_dir"
        echo -e "${YELLOW}⚠️  nvim not found, using shell${NC}"
      fi
      
      # window 2: opencode (check if installed)
      if command -v opencode &> /dev/null; then
        tmux new-window -t "$session_name" -n "opencode" -c "$worktree_dir"
        tmux send-keys -t "$session_name:opencode" "opencode" Enter
      fi
      
      # window 3: dev server or shell (don't auto-start dev to avoid race condition)
      local pkg_manager=$(_detect_package_manager "$original_path")
      
      if [[ -n "$pkg_manager" ]]; then
        tmux new-window -t "$session_name" -n "dev" -c "$worktree_dir"
        tmux send-keys -t "$session_name:dev" "# Run when ready: $pkg_manager run dev" Enter
      else
        tmux new-window -t "$session_name" -n "shell" -c "$worktree_dir"
      fi
      
      # select first window
      tmux select-window -t "$session_name:1"
      echo -e "${GREEN}✅ Tmux session ready!${NC}"
    fi
    
    # attach or switch to session
    if [ -n "$TMUX" ]; then
      tmux switch-client -t "$session_name"
    else
      tmux attach -t "$session_name"
    fi
  }
  
  # if worktree directory exists, validate and attach
  if [[ -d "$worktree_dir" ]]; then
    # verify it's a valid tracked worktree
    if git worktree list | grep -q "$worktree_dir"; then
      echo -e "${GREEN}✅ Worktree exists: $worktree_dir${NC}"
      _setup_session
      return
    else
      echo -e "${YELLOW}⚠️  Directory exists but is not a valid worktree. Recreating...${NC}"
      rm -rf "$worktree_dir" 2>/dev/null
      # fall through to creation logic
    fi
  fi

  # create git worktree
  echo -e "${BLUE}🌿 Creating git worktree for branch: $branch_name${NC}"
  
  # check if branch exists (local or remote)
  if git show-ref --verify --quiet "refs/heads/$branch_name" || \
     git show-ref --verify --quiet "refs/remotes/origin/$branch_name"; then
    # branch exists somewhere
    if git show-ref --verify --quiet "refs/heads/$branch_name"; then
      # local branch exists
      if ! git worktree add "$worktree_dir" "$branch_name"; then
        echo -e "${RED}❌ Failed to create worktree${NC}"
        rm -rf "$worktree_dir" 2>/dev/null
        git worktree prune 2>/dev/null
        return 1
      fi
    else
      # only remote branch exists, create tracking branch
      if ! git worktree add -b "$branch_name" "$worktree_dir" "origin/$branch_name"; then
        echo -e "${RED}❌ Failed to create worktree from remote branch${NC}"
        rm -rf "$worktree_dir" 2>/dev/null
        git worktree prune 2>/dev/null
        return 1
      fi
    fi
    echo -e "${GREEN}✓ Worktree created${NC}"
  else
    # branch doesn't exist anywhere, create it from HEAD
    echo -e "${YELLOW}🌱 Creating new branch from current HEAD...${NC}"
    if ! git worktree add -b "$branch_name" "$worktree_dir"; then
      echo -e "${RED}❌ Failed to create worktree${NC}"
      rm -rf "$worktree_dir" 2>/dev/null
      git worktree prune 2>/dev/null
      return 1
    fi
    echo -e "${GREEN}✓ New branch created${NC}"
  fi

  # copy .env files
  echo -e "${BLUE}📋 Copying .env files...${NC}"
  setopt nullglob
  for env_file in "$original_path"/.env*; do
    if [[ -f "$env_file" ]]; then
      cp "$env_file" "$worktree_dir/" 2>/dev/null && echo -e "   ${GREEN}✓ $(basename "$env_file")${NC}"
    fi
  done
  unsetopt nullglob
  
  # detect and install dependencies (synchronously to avoid race condition)
  local pkg_manager=$(_detect_package_manager "$original_path")

  if [[ -n "$pkg_manager" ]]; then
    echo -e "${BLUE}📦 Installing dependencies with $pkg_manager...${NC}"
    (cd "$worktree_dir" && $pkg_manager install)
    echo -e "${GREEN}✓ Dependencies installed${NC}"
  fi

  # setup tmux and attach
  _setup_session
  
  # cleanup helper functions
  unset -f _setup_session _detect_package_manager
}

autoload -Uz edit-command-line

# Create a function to handle double-tab
function double-tab-edit() {
  local now elapsed
  now=$(date +%s%3N)  # current time in milliseconds

  # If last Tab was pressed recently (within 300 ms)
  if [[ -n $LAST_TAB_TIME && $((now - LAST_TAB_TIME)) -lt 300 ]]; then
    zle edit-command-line
    unset LAST_TAB_TIME
  else
    LAST_TAB_TIME=$now
    zle expand-or-complete  # normal Tab behavior
  fi
}

# zle -N double-tab-edit
# bindkey '\t' double-tab-edit

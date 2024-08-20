# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
plugins=(git zsh-autosuggestions zsh-syntax-highlighting fzf-tab sudo dirhistory)

if command -v nvim > /dev/null 2>&1; then
  export EDITOR=nvim
else
  export EDITOR=vim
fi

source $ZSH/oh-my-zsh.sh
# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
. "$HOME/.cargo/env"

export PATH=$PATH:/home/e4elhaam/.nvm/versions/node/v19.9.0/bin
export PATH=$PATH:"$HOME/.nvm"
export PATH=$PATH:"$HOME/.cargo/bin"
export PATH=$PATH:"$HOME/.bun/bin"
export PATH=$PATH:"$HOME/flutter/bin"
export N_PREFIX=$HOME/.
export PATH="$PATH:/opt/nvim-linux64/bin"
export PATH=$PATH:/usr/local/go/bin
PATH=~/.console-ninja/.bin:$PATH
export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
export PATH="$HOME/downloads/zig-linux-x86_64-0.11.0:$PATH"
export PATH="$PATH:/home/e4elhaam/.local/bin"

GOROOT=$(dirname $(dirname $(which go)))
export GOPATH=$HOME/go
export PATH=$PATH:$GOROOT/bin:$GOPATH/bin

# === aliases ===

alias ls="exa -a --icons"
alias ll="exa -a --icons --long"
# Aliases for common Windows utilities - wsl
alias ex='explorer.exe .'
alias notepad='notepad.exe'
alias clip='clip.exe'
alias edge='msedge.exe'
# for cd:
alias ..='cd ..'
alias .2='cd ../..'
alias .3='cd ../../..'
alias .4='cd ../../../..'
alias cp="cp -i"
alias mv="mv -i"
# others
alias cpth='pwd | tr -d "\n" | clip.exe'
alias cwp='echo "\\\\\wsl.localhost\\\Ubuntu${PWD//\//\\\\}" | xcopy'
alias pn=pnpm
alias cat="bat"
alias tls="tmux ls"
alias oc="code ."
alias tmux="tmux -2"
alias ov="vim ."
alias xcopy="xclip -selection clipboard"
alias cls='clear'
alias rt='source ~/.zshrc'
alias lgit=lazygit
# vim alias
alias vi=vim
alias vim=nvim
# fzf 
alias tf='tmux attach-session -t $(tmux list-sessions -F "#{session_name}" | fzf --height 40%)'
alias tmuxf='tmux attach-session -t $(tmux list-sessions -F "#{session_name}" | fzf --height 40%)'
alias nvimf='fzf --preview "cat {}" | xargs -r nvim'
alias catf='fzf --height 40% --preview "cat {}"'
alias vimf='fzf --height 40% --preview "cat {}" | xargs -r vim'
alias cdf='cd "$(find . -type d | fzf --height 40%)"'
alias psf="ps aux | fzf --preview 'ps --forest -o pid,cmd --pid=$(echo {} | awk "{print \$2}")' --preview-window=up:3"
# To see if a command is aliased, a file, or a built-in command
alias checkcommand="type -t"
alias openports='netstat -nape --inet'

# === alias functions ===
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
FNM_PATH="/home/e4elhaam/.local/share/fnm"
if [ -d "$FNM_PATH" ]; then
  export PATH="/home/e4elhaam/.local/share/fnm:$PATH"
  eval "`fnm env`"
fi

# pnpm
export PNPM_HOME="/home/e4elhaam/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac

export GOPATH="$HOME/go"; export GOROOT="$HOME/.go"; export PATH="$GOPATH/bin:$PATH"; # g-install: do NOT edit, see https://github.com/stefanmaric/g
alias gvm="$GOPATH/bin/g"; # g-install: do NOT edit, see https://github.com/stefanmaric/g

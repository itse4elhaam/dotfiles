# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
plugins=(git zsh-autosuggestions zsh-syntax-highlighting fzf-tab sudo dirhistory)
export EDITOR=vim

source $ZSH/oh-my-zsh.sh

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
. "$HOME/.cargo/env"

export PATH=$PATH:"$HOME/.nvm"
export PATH=$PATH:"$HOME/.cargo/bin"
export PATH=$PATH:"$HOME/.bun/bin"
export PATH=$PATH:"$HOME/flutter/bin"
export GOPATH=$HOME/go
export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin
export N_PREFIX=$HOME/.
PATH=~/.console-ninja/.bin:$PATH
export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
export PATH="$HOME/downloads/zig-linux-x86_64-0.11.0:$PATH"
export PATH="$PATH:/home/e4elhaam/.local/bin"

alias ls="exa -a --icons"
alias ll="exa -a --icons --long"

# Aliases for common Windows utilities
alias ex='explorer.exe .'
alias notepad='notepad.exe'
alias edge='msedge.exe'

# for cd:
alias ..='cd ..'
alias .2='cd ../..'
alias .3='cd ../../..'
alias .4='cd ../../../..'

# others
alias cpth='pwd | tr -d "\n" | xclip -selection clipboard'
alias cwp='echo "\\\\\wsl.localhost\\\Ubuntu${PWD//\//\\\\}" | xcopy'
alias ecat='cat <<EOF >>'
alias cat="bat"
alias tls="tmux ls"
alias oc="code ."
alias clp="clip.exe"
alias tmux="tmux -2"

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
function cmkdir() {
    mkdir -p "$1"         # Create the directory (and parent directories if needed)
    if [ $? -eq 0 ]; then # Check if directory creation was successful
        cd "$1"           # Change into the newly created directory
    else
        echo "Error creating directory"
    fi
}
# vim alias
alias nv=nvim
alias nvo="nvim ."
alias envi="cd ~/.config/nvim; nvim ."
alias vi=vim
alias xcopy="xclip -selection clipboard"
alias cls='clear'
alias rt='source ~/.zshrc'

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

alias tmuxf='tmux attach-session -t $(tmux list-sessions -F "#{session_name}" | fzf)'
alias nvimf='fzf --preview "cat {}" | xargs -r nvim'
alias catf='fzf --preview "cat {}"'
alias vimf='fzf --preview "cat {}" | xargs -r vim'
alias cdf='cd "$(find . -type d | fzf)"'

bindkey '^H' backward-kill-word
bindkey '^[[1;6D' emacs-backward-word
bindkey '^[[1;6C' emacs-forward-word

autoload -Uz compinit

HISTSIZE=5000
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

# Worktree dependencies

A Git template installs `post-checkout` in new clones and repositories on this machine. When Git supplies a null old HEAD for a new linked worktree, the hook checks the primary checkout for installed dependencies. Regular branch and file checkouts skip the helper. Worktrunk also runs it on creation so repos with their own Git hook path can use it.

To add the hook to an existing repository, run `~/dotfiles/scripts/worktree-deps install-hook /path/to/repo`. This preserves existing hooks. If the repo overrides `core.hooksPath` or already has a `post-checkout`, have that hook call `"$HOME/dotfiles/.config/git/templates/hooks/post-checkout" "$@"`. Use a T3 Code worktree creation script calling `~/dotfiles/scripts/worktree-deps checkout` if the project's hook directory is generated after checkout.

Keep the primary install current. A worktree can share `node_modules` when the package has a tracked lockfile and its manifests, lockfiles, and runtime settings match the primary checkout. Projects with workspace or local package links keep their installs local. To disable sharing for a repository, run `git config worktreeDeps.share false` there.

If you need to install or update dependencies in a linked worktree, run `~/dotfiles/scripts/worktree-deps install npm ci` from the package directory. Substitute the package manager command you need. This detaches the shared symlink before the install so the primary checkout keeps its own dependencies.

-- Loaded before the user's config; keep desktop drafts out of coding sessions.
vim.g.auto_session_enabled = false
vim.g.auto_save_enabled = false
vim.g.auto_restore_enabled = false
vim.opt.swapfile = false
vim.opt.backup = false
vim.opt.writebackup = false
local wrote = false
local cancelled = false
vim.api.nvim_create_autocmd('CmdlineLeave', {
  callback = function()
    local command = vim.fn.getcmdline():match('^%s*(%S+)') or ''
    if command:match('^q%a*!$') or command:match('^cq') then
      cancelled = true
    end
  end,
})
vim.api.nvim_create_autocmd('BufWritePost', {
  callback = function(args)
    if vim.fn.fnamemodify(args.file, ':p') == vim.env.NVIM_ANYWHERE_DRAFT then wrote = true end
  end,
})
vim.api.nvim_create_autocmd('VimLeavePre', {
  callback = function()
    if wrote and not cancelled and not vim.bo.modified and vim.v.dying == 0
        and (vim.v.exiting == vim.NIL or vim.v.exiting == 0) then
      vim.fn.writefile({'commit'}, vim.env.NVIM_ANYWHERE_COMMIT)
    end
  end,
})
vim.api.nvim_create_autocmd('VimEnter', {
  once = true,
  callback = function()
    pcall(function() require('auto-session').disable_auto_session() end)
    vim.opt_local.wrap = true
    vim.opt_local.linebreak = true
    vim.opt_local.filetype = 'markdown'
  end,
})

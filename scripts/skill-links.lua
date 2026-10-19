local uv = vim.uv or vim.loop
local repo = vim.fn.resolve(vim.fn.expand("~/dotfiles"))
local roots = { repo .. "/.agents/skills", repo .. "/.pi/agent/skills" }

vim.api.nvim_create_autocmd("BufWritePost", {
  group = vim.api.nvim_create_augroup("DotfilesSkillLinks", { clear = true }),
  pattern = { "SKILL.md", "skill.md" },
  callback = function(event)
    local source = vim.fn.fnamemodify(vim.fn.resolve(event.file), ":h")
    local parent = vim.fn.fnamemodify(source, ":h")
    if not vim.tbl_contains(roots, parent) then
      return
    end
    local destination = vim.fn.expand("~/.agents/skills/") .. vim.fn.fnamemodify(source, ":t")
    local existing = uv.fs_lstat(destination)
    if existing then
      if existing.type ~= "link" or uv.fs_realpath(destination) ~= uv.fs_realpath(source) then
        vim.notify("Skill link conflict, preserved: " .. destination, vim.log.levels.WARN)
      end
      return
    end
    vim.fn.mkdir(vim.fn.fnamemodify(destination, ":h"), "p")
    local ok, err = uv.fs_symlink(source, destination)
    if not ok then
      vim.notify("Cannot link skill: " .. tostring(err), vim.log.levels.ERROR)
    end
  end,
})

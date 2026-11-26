-- Neovim's session file restores tabs and windows. Buffer edits need a separate
-- copy so checkpointing never writes a user's working files.
local M = {}

function M.save(path)
  local previous = vim.v.this_session
  local ok, err = pcall(vim.cmd, 'mksession! ' .. vim.fn.fnameescape(path))
  vim.v.this_session = previous
  if not ok then error(err) end
  local edits = {}
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_loaded(buf) and vim.bo[buf].modified and vim.bo[buf].buftype == '' then
      local windows = {}
      for _, win in ipairs(vim.fn.win_findbuf(buf)) do
        local tab = vim.api.nvim_win_get_tabpage(win)
        table.insert(windows, { vim.api.nvim_tabpage_get_number(tab), vim.api.nvim_win_get_number(win),
                              vim.api.nvim_win_get_cursor(win) })
      end
      table.insert(edits, { name = vim.api.nvim_buf_get_name(buf), windows = windows,
        lines = vim.api.nvim_buf_get_lines(buf, 0, -1, true), eol = vim.bo[buf].endofline,
        fileformat = vim.bo[buf].fileformat, filetype = vim.bo[buf].filetype })
    end
  end
  return vim.json.encode(edits)
end

function M.restore(path)
  local edits = vim.json.decode(table.concat(vim.fn.readfile(path), '\n'))
  local tabs = vim.api.nvim_list_tabpages()
  for _, edit in ipairs(edits) do
    local buf = edit.name == '' and vim.api.nvim_create_buf(true, false) or vim.fn.bufadd(edit.name)
    vim.fn.bufload(buf)
    vim.api.nvim_buf_set_lines(buf, 0, -1, true, edit.lines)
    vim.bo[buf].fileformat = edit.fileformat
    vim.bo[buf].endofline = edit.eol
    vim.bo[buf].filetype = edit.filetype
    vim.bo[buf].modified = true
    for _, view in ipairs(edit.windows) do
      local tab = tabs[view[1]]
      local win = tab and vim.api.nvim_tabpage_list_wins(tab)[view[2]]
      if win then
        vim.api.nvim_win_set_buf(win, buf)
        vim.api.nvim_win_set_cursor(win, view[3])
      end
    end
  end
  return 1
end

return M

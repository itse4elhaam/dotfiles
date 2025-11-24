import { tool } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { readFileSync } from "fs"
import { homedir } from "os"
import { join } from "path"

export default tool({
  description: "List all enabled MCP servers with capabilities and detailed documentation from ai-guide.md",
  args: {},
  async execute(args, context) {
    try {
      // Step 1: Parse enabled servers from opencode.json
      const configPath = join(homedir(), ".config/opencode/opencode.json")
      const jqCommand = `jq -r '.mcp | to_entries[] | select(.value.enabled != false) | "\\(.key) (\\(.value.type))"' ${configPath}`
      
      let enabledServers: string
      try {
        enabledServers = execSync(jqCommand, { encoding: "utf-8" }).trim()
      } catch (error) {
        return "Error: Could not parse opencode.json. Ensure jq is installed and the file exists."
      }

      if (!enabledServers) {
        return "No MCP servers are currently enabled in your configuration."
      }

      // Step 2: Read MCP documentation from ai-guide.md
      // Try multiple locations: dotfiles repo, current working directory
      const possiblePaths = [
        join(homedir(), "dotfiles/docs/ai-guide.md"),
        join(process.cwd(), "docs/ai-guide.md"),
        join(homedir(), "workspace/dotfiles/docs/ai-guide.md"),
      ]

      let aiGuideContent: string | null = null
      let aiGuidePath: string | null = null

      for (const path of possiblePaths) {
        try {
          aiGuideContent = readFileSync(path, "utf-8")
          aiGuidePath = path
          break
        } catch {
          // Try next path
          continue
        }
      }

      if (!aiGuideContent) {
        return `Error: Could not find ai-guide.md in any of these locations:
${possiblePaths.map((p) => `  - ${p}`).join("\n")}

The ai-guide.md file contains MCP server documentation needed for this tool.
Please ensure it exists in one of the above locations.`
      }

      // Extract the MCP Servers section
      const mcpSectionMatch = aiGuideContent.match(/## MCP Servers([\s\S]*?)(?=\n##|$)/)
      if (!mcpSectionMatch) {
        return "Error: Could not find '## MCP Servers' section in docs/ai-guide.md"
      }

      const mcpSection = mcpSectionMatch[1]

      // Step 3: Format output
      const serverLines = enabledServers.split("\n")
      const serverNames = serverLines.map((line) => {
        const match = line.match(/^(\S+)/)
        return match ? match[1] : ""
      }).filter(Boolean)

      let output = "# Enabled MCP Servers\n\n"
      output += `Found ${serverNames.length} enabled MCP server(s):\n\n`

      // Categories from ai-guide.md
      const categories = [
        "Documentation & Research",
        "Code Analysis & GitHub",
        "Development Tools",
        "File & System Operations",
        "Utilities",
      ]

      for (const category of categories) {
        const categoryServers = serverNames.filter((name) => {
          // Check if server is mentioned in this category section
          const categoryRegex = new RegExp(
            `### \\*\\*${category}\\*\\*([\\s\\S]*?)(?=\\n### \\*\\*|$)`,
            "i"
          )
          const categoryMatch = mcpSection.match(categoryRegex)
          if (!categoryMatch) return false

          const categoryContent = categoryMatch[1]
          // Check if server name appears in this category (case insensitive)
          return new RegExp(`\\*\\*${name}\\*\\*`, "i").test(categoryContent)
        })

        if (categoryServers.length > 0) {
          output += `## ${category}\n\n`

          for (const serverName of categoryServers) {
            // Extract server details from mcpSection
            const serverRegex = new RegExp(
              `- \\*\\*${serverName}\\*\\*:([^\\n]+)\\n\\s+- Use when:([^\\n]+)\\n\\s+- Example:([^\\n]+)`,
              "i"
            )
            const serverMatch = mcpSection.match(serverRegex)

            if (serverMatch) {
              const purpose = serverMatch[1].trim()
              const useWhen = serverMatch[2].trim()
              const example = serverMatch[3].trim()

              output += `### **${serverName}**\n`
              output += `- **Purpose**: ${purpose}\n`
              output += `- **Use when**: ${useWhen}\n`
              output += `- **Example**: ${example}\n\n`
            } else {
              // Fallback if regex doesn't match
              output += `### **${serverName}**\n`
              output += `- Enabled in configuration\n\n`
            }
          }
        }
      }

      // Step 4: Add usage guidelines
      output += "\n---\n\n"
      output += "## Usage Guidelines\n\n"
      output += "- **Prefer specialized tools**: Use MCP servers over generic bash commands when available\n"
      output += "- **Check enabled status**: Only enabled servers are accessible\n"
      output += "- **Context efficiency**: Use Task tool for exploratory searches to reduce token usage\n"
      output += "- **Parallel execution**: Batch independent MCP calls in a single message\n"

      return output
    } catch (error) {
      return `Error executing list-mcp tool: ${error instanceof Error ? error.message : String(error)}`
    }
  },
})

# Page 6: MCP + Skills Integration

## Rules for qdrant-os

### R-11: Skills and MCP serve different functions
| MCP (Connectivity) | Skills (Knowledge) |
|---|---|
| Connects Claude to Qdrant | Teaches Claude how to use Qdrant effectively |
| Provides real-time data access and tool invocation | Captures workflows and best practices |
| What Claude CAN do | How Claude SHOULD do it |

Never mix these concerns. A skill should not reimplement what the MCP server already does.

### R-12: Skills solve the "now what?" problem
Without skills, users connect to Qdrant MCP but don't know what to do next. They file support tickets asking "how do I do X with your integration." Each conversation starts from scratch.

With skills:
- Pre-built workflows activate automatically when needed
- Consistent, reliable tool usage
- Best practices embedded in every interaction
- Lower learning curve

### R-13: Skills prevent blame-shifting
Users blame the connector when the real issue is workflow guidance. If a user can connect to Qdrant but gets bad results, the problem is usually "they didn't know to apply quantization first" not "the MCP server is broken." Skills fix this by embedding the right sequence of operations.

## How we hit this
- [ ] Every external skill references specific Qdrant MCP tools where applicable
- [ ] No skill reimplements MCP functionality (no raw HTTP calls to Qdrant)
- [ ] Skills reduce support tickets: track which questions disappear after skill deployment
- [ ] Skills activate automatically, users should not need to know they exist

# Page 19: Distribution and Sharing

## Rules for qdrant-os

### R-54: Distribution channels (use all of them)
Skills can be distributed through:

1. **Individual users**: Download folder, zip it, upload via Claude.ai Settings > Capabilities > Skills, or place in Claude Code skills directory
2. **Organization-level**: Admins deploy workspace-wide. Automatic updates. Centralized management.
3. **API**: `/v1/skills` endpoint for programmatic management. `container.skills` parameter in Messages API.

### R-55: qdrant-os distribution strategy
- **qdrant-os (public)**: GitHub repo with installation guide. Users clone and upload.
- **qdrant-os-internal (private)**: Organization-level deployment. Admins push to all team members. Automatic updates on merge.

### R-56: Skills are an open standard
Skills should be portable across tools and platforms. The same skill should work whether you're using Claude or other AI platforms. Note platform-specific features in the `compatibility` field.

### R-57: When to use API vs Claude.ai
| Use Case | Best Surface |
|---|---|
| End users interacting with skills directly | Claude.ai / Claude Code |
| Manual testing and iteration | Claude.ai / Claude Code |
| Individual, ad-hoc workflows | Claude.ai / Claude Code |
| Applications using skills programmatically | API |
| Production deployments at scale | API |
| Automated pipelines and agent systems | API |

For qdrant-os external skills: start with Claude.ai/Code distribution. Move to API when building automated support pipelines.

### R-58: Skills in the API require Code Execution Tool beta
If deploying skills via the API, enable the Code Execution Tool beta for the secure environment skills need to run.

## How we hit this
- [ ] Public repo has clear installation instructions in top-level README
- [ ] Internal repo uses org-level skill deployment
- [ ] Both repos provide zipped releases for easy Claude.ai upload
- [ ] API integration planned for phase 2 (days 31-60)

// deterministic port slot assignment with worktree offsets
// base port range: 4000-4999
// each service gets a slot (0, 1, 2, ...)
// each worktree gets an offset (+100 per worktree index)
// so: service 0 on worktree 0 = 4000, service 0 on worktree 1 = 4100

const BASE_PORT = 4000;
const SLOT_SIZE = 10;     // max 10 services per project
const WORKTREE_OFFSET = 100;
const MAX_PORT = 65535;

export function calculatePort(serviceIndex: number, worktreeIndex: number): number {
  const port = BASE_PORT + (serviceIndex * SLOT_SIZE) + (worktreeIndex * WORKTREE_OFFSET);
  if (port > MAX_PORT) {
    throw new Error(
      `port ${port} exceeds max (65535). ` +
      `service index ${serviceIndex}, worktree index ${worktreeIndex}. ` +
      `reduce concurrent worktrees or services.`
    );
  }
  return port;
}

export async function portAssign(serviceName: string, worktreeIndex: number): Promise<void> {
  if (!serviceName) {
    console.error("error: service name required");
    process.exit(1);
  }

  // deterministic service index from name hash
  const serviceIndex = hashToIndex(serviceName);
  const port = calculatePort(serviceIndex, worktreeIndex);

  console.log(JSON.stringify({
    service: serviceName,
    serviceIndex,
    worktreeIndex,
    port,
  }));
}

// stable hash to small index (0-9)
function hashToIndex(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % SLOT_SIZE;
}

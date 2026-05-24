import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";

import { createMcpExpressApp } from "@modelcontextprotocol/express";
import { NodeStreamableHTTPServerTransport } from "@modelcontextprotocol/node";
import { isInitializeRequest, McpServer } from "@modelcontextprotocol/server";
import type { Request, Response } from "express";
import * as z from "zod/v4";

const HOST = process.env.HOST ?? "127.0.0.1";
const PORT = Number.parseInt(process.env.PORT ?? "2091", 10);
const SERVER_VERSION = "0.1.0";
const DEFAULT_CWD = "/mnt/d/Sandbox";
const AUDIT_PATH = "/mnt/d/Sandbox/asi_kernel/logs/chatgpt-arch-mcp.jsonl";

const SECRET_KEY_RE = /TOKEN|KEY|SECRET|PASSWORD|PASS|AUTH|COOKIE|SESSION|CREDENTIAL/i;

const RunInputSchema = z.object({
  command: z.string().min(1).max(20000),
  cwd: z.string().default(DEFAULT_CWD),
  timeout_ms: z.number().int().positive().max(600000).default(120000),
  max_output_bytes: z.number().int().positive().max(1048576).default(65536),
  stdin: z.string().optional(),
  env: z.record(z.string(), z.string()).optional().default({})
});

type RunInput = z.infer<typeof RunInputSchema>;

type RunResult = {
  commandId: string;
  exitCode: number | null;
  signal: NodeJS.Signals | null;
  stdout: string;
  stderr: string;
  elapsedMs: number;
  cwd: string;
  truncated: boolean;
  stdoutBytes: number;
  stderrBytes: number;
  timedOut: boolean;
  errorClass?: string;
};

function jsonText(value: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(value, null, 2) }]
  };
}

function redactText(input: string): string {
  return input
    .replace(/(Bearer\s+)[A-Za-z0-9._~+/=-]+/gi, "$1[REDACTED]")
    .replace(
      /([A-Za-z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASS|AUTH|COOKIE|SESSION|CREDENTIAL)[A-Za-z0-9_]*\s*=\s*)("[^"]*"|'[^']*'|[^\s]+)/gi,
      "$1[REDACTED]"
    );
}

function buildEnv(userEnv: Record<string, string>): NodeJS.ProcessEnv {
  const safeEnv: NodeJS.ProcessEnv = {
    HOME: process.env.HOME ?? "/home/j",
    PATH: "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    LANG: process.env.LANG ?? "C.UTF-8",
    LC_ALL: process.env.LC_ALL ?? "C.UTF-8",
    TERM: "dumb"
  };

  for (const [key, value] of Object.entries(userEnv)) {
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
      throw new Error(`Invalid env key: ${key}`);
    }
    safeEnv[key] = value;
  }

  return safeEnv;
}

function captureLimited(maxBytes: number) {
  const chunks: Buffer[] = [];
  let totalBytes = 0;
  let truncated = false;

  return {
    push(chunk: Buffer | string) {
      const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      totalBytes += buffer.length;

      const keptBytes = chunks.reduce((sum, item) => sum + item.length, 0);
      const remaining = maxBytes - keptBytes;

      if (remaining > 0) {
        chunks.push(buffer.subarray(0, remaining));
      }

      if (totalBytes > maxBytes) {
        truncated = true;
      }
    },
    text() {
      return Buffer.concat(chunks).toString("utf8");
    },
    bytes() {
      return totalBytes;
    },
    isTruncated() {
      return truncated;
    }
  };
}

async function audit(entry: Record<string, unknown>) {
  const line = JSON.stringify({
    timestamp: new Date().toISOString(),
    ...entry
  });

  await fs.mkdir(path.dirname(AUDIT_PATH), { recursive: true });
  await fs.appendFile(AUDIT_PATH, `${line}\n`, "utf8");
}

function runShell(input: RunInput): Promise<RunResult> {
  const commandId = randomUUID();
  const started = Date.now();
  const stdout = captureLimited(input.max_output_bytes);
  const stderr = captureLimited(input.max_output_bytes);

  return new Promise((resolve) => {
    let settled = false;
    let timedOut = false;

    const child = spawn("bash", ["-lc", input.command], {
      cwd: input.cwd,
      env: buildEnv(input.env),
      detached: true,
      stdio: ["pipe", "pipe", "pipe"]
    });

    const finish = (result: Omit<RunResult, "commandId" | "elapsedMs" | "cwd" | "stdout" | "stderr" | "stdoutBytes" | "stderrBytes" | "truncated" | "timedOut">) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);

      resolve({
        commandId,
        exitCode: result.exitCode,
        signal: result.signal,
        stdout: stdout.text(),
        stderr: stderr.text(),
        elapsedMs: Date.now() - started,
        cwd: input.cwd,
        truncated: stdout.isTruncated() || stderr.isTruncated(),
        stdoutBytes: stdout.bytes(),
        stderrBytes: stderr.bytes(),
        timedOut,
        errorClass: result.errorClass
      });
    };

    const timer = setTimeout(() => {
      timedOut = true;

      if (child.pid) {
        try {
          process.kill(-child.pid, "SIGTERM");
        } catch {
          child.kill("SIGTERM");
        }

        setTimeout(() => {
          if (!settled && child.pid) {
            try {
              process.kill(-child.pid, "SIGKILL");
            } catch {
              child.kill("SIGKILL");
            }
          }
        }, 2000).unref();
      }
    }, input.timeout_ms);

    child.stdout.on("data", (chunk) => stdout.push(chunk));
    child.stderr.on("data", (chunk) => stderr.push(chunk));

    child.on("error", (error) => {
      stderr.push(`${error.name}: ${error.message}`);
      finish({
        exitCode: null,
        signal: null,
        errorClass: error.name
      });
    });

    child.on("close", (exitCode, signal) => {
      finish({
        exitCode,
        signal
      });
    });

    if (input.stdin !== undefined) {
      child.stdin.end(input.stdin);
    } else {
      child.stdin.end();
    }
  });
}

async function shellText(command: string): Promise<string> {
  const result = await runShell({
    command,
    cwd: DEFAULT_CWD,
    timeout_ms: 5000,
    max_output_bytes: 8192,
    env: {}
  });

  return (result.stdout || result.stderr).trim();
}

function makeServer() {
  const server = new McpServer(
    {
      name: "arch-wsl-shell",
      version: SERVER_VERSION
    },
    {
      instructions:
        "Private Arch WSL shell server. Use arch_check for read-only environment checks. Use arch_run only when the user explicitly asks to run a local command."
    }
  );

  server.registerTool(
    "arch_check",
    {
      title: "Arch WSL environment check",
      description: "Read-only check of the Arch WSL environment and server configuration.",
      inputSchema: z.object({}),
      annotations: {
        title: "Arch Check",
        readOnlyHint: true,
        openWorldHint: false,
        destructiveHint: false
      }
    },
    async () => {
      const output = {
        ok: true,
        distro: await shellText("grep '^NAME=' /etc/os-release | cut -d= -f2- | tr -d '\"'"),
        kernel: await shellText("uname -a"),
        cwd: DEFAULT_CWD,
        shell: await shellText("printf '%s' \"${SHELL:-unknown}\""),
        node: await shellText("node -v"),
        npm: await shellText("npm -v"),
        uv: await shellText("uv --version || true"),
        pacman: await shellText("pacman --version | grep -m 1 Pacman || true"),
        serverVersion: SERVER_VERSION,
        host: HOST,
        port: PORT,
        runEnabled: process.env.ARCH_MCP_ENABLE_RUN === "1",
        auditPath: AUDIT_PATH
      };

      await audit({
        tool: "arch_check",
        commandId: null,
        command: null,
        cwd: DEFAULT_CWD,
        exitCode: 0,
        signal: null,
        elapsedMs: null,
        stdoutBytes: JSON.stringify(output).length,
        stderrBytes: 0,
        truncated: false
      });

      return jsonText(output);
    }
  );

  server.registerTool(
    "arch_run",
    {
      title: "Run Arch WSL shell command",
      description:
        "Runs a non-interactive bash -lc command inside Arch WSL. This can modify or delete files. Requires ARCH_MCP_ENABLE_RUN=1 on the server.",
      inputSchema: RunInputSchema,
      annotations: {
        title: "Arch Run",
        readOnlyHint: false,
        openWorldHint: true,
        destructiveHint: true
      }
    },
    async (raw) => {
      const input = RunInputSchema.parse(raw);

      if (process.env.ARCH_MCP_ENABLE_RUN !== "1") {
        const disabled = {
          ok: false,
          error: "arch_run disabled. Start server with ARCH_MCP_ENABLE_RUN=1 to enable shell execution."
        };

        await audit({
          tool: "arch_run",
          commandId: null,
          command: redactText(input.command),
          cwd: input.cwd,
          exitCode: null,
          signal: null,
          elapsedMs: 0,
          stdoutBytes: 0,
          stderrBytes: JSON.stringify(disabled).length,
          truncated: false,
          errorClass: "RunDisabled"
        });

        return {
          ...jsonText(disabled),
          isError: true
        };
      }

      const result = await runShell(input);

      await audit({
        tool: "arch_run",
        commandId: result.commandId,
        command: redactText(input.command),
        cwd: result.cwd,
        exitCode: result.exitCode,
        signal: result.signal,
        elapsedMs: result.elapsedMs,
        stdoutBytes: result.stdoutBytes,
        stderrBytes: result.stderrBytes,
        truncated: result.truncated,
        timedOut: result.timedOut,
        errorClass: result.errorClass,
        envKeys: Object.keys(input.env).map((key) => SECRET_KEY_RE.test(key) ? `${key}=[REDACTED]` : key)
      });

      return jsonText({
        commandId: result.commandId,
        exitCode: result.exitCode,
        signal: result.signal,
        stdout: result.stdout,
        stderr: result.stderr,
        elapsedMs: result.elapsedMs,
        cwd: result.cwd,
        truncated: result.truncated,
        timedOut: result.timedOut
      });
    }
  );

  return server;
}

const app = createMcpExpressApp({ host: HOST });

app.get("/healthz", (_req: Request, res: Response) => {
  res.json({
    ok: true,
    name: "arch-wsl-shell",
    version: SERVER_VERSION
  });
});

app.get("/readyz", async (_req: Request, res: Response) => {
  try {
    await fs.mkdir(path.dirname(AUDIT_PATH), { recursive: true });
    await fs.access(path.dirname(AUDIT_PATH));

    res.json({
      ok: true,
      ready: true,
      auditPath: AUDIT_PATH
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      ready: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
});

const transports: Record<string, NodeStreamableHTTPServerTransport> = {};

async function mcpPostHandler(req: Request, res: Response) {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;

  try {
    let transport: NodeStreamableHTTPServerTransport;

    if (sessionId && transports[sessionId]) {
      transport = transports[sessionId];
    } else if (!sessionId && isInitializeRequest(req.body)) {
      transport = new NodeStreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (newSessionId) => {
          transports[newSessionId] = transport;
        }
      });

      transport.onclose = () => {
        const sid = transport.sessionId;
        if (sid) delete transports[sid];
      };

      const server = makeServer();
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
      return;
    } else if (sessionId) {
      res.status(404).json({
        jsonrpc: "2.0",
        error: { code: -32001, message: "Session not found" },
        id: null
      });
      return;
    } else {
      res.status(400).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "Bad Request: initialize request required" },
        id: null
      });
      return;
    }

    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error("MCP POST error:", error);

    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null
      });
    }
  }
}

async function mcpGetHandler(req: Request, res: Response) {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;

  if (!sessionId) {
    res.status(400).send("Missing session ID");
    return;
  }

  const transport = transports[sessionId];
  if (!transport) {
    res.status(404).send("Session not found");
    return;
  }

  await transport.handleRequest(req, res);
}

async function mcpDeleteHandler(req: Request, res: Response) {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;

  if (!sessionId) {
    res.status(400).send("Missing session ID");
    return;
  }

  const transport = transports[sessionId];
  if (!transport) {
    res.status(404).send("Session not found");
    return;
  }

  await transport.handleRequest(req, res);
}

app.post("/mcp", mcpPostHandler);
app.get("/mcp", mcpGetHandler);
app.delete("/mcp", mcpDeleteHandler);

const httpServer = app.listen(PORT, HOST, () => {
  console.log(`arch-wsl-shell listening at http://${HOST}:${PORT}`);
  console.log(`MCP endpoint: http://${HOST}:${PORT}/mcp`);
  console.log(`arch_run enabled: ${process.env.ARCH_MCP_ENABLE_RUN === "1"}`);
});

process.on("SIGINT", async () => {
  console.log("Shutting down arch-wsl-shell...");

  httpServer.close();

  for (const [sessionId, transport] of Object.entries(transports)) {
    try {
      await transport.close();
      delete transports[sessionId];
    } catch (error) {
      console.error(`Failed to close transport ${sessionId}:`, error);
    }
  }

  process.exit(0);
});



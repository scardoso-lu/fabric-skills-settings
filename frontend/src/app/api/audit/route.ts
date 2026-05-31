/**
 * Server-side audit log sink.
 *
 * The browser calls this endpoint after every write operation. This route
 * emits a structured JSON line to stdout so that systemd/journald captures
 * it automatically when the Next.js process runs under a systemd unit.
 *
 * View with:
 *   journalctl -u <your-unit> -g fabric-audit --output=json
 *   journalctl -u <your-unit> -g fabric-audit -o cat | jq .
 */
import { NextRequest, NextResponse } from "next/server";

const REQUIRED = ["action", "nodeId", "ts"] as const;

export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  for (const field of REQUIRED) {
    if (body[field] === undefined) {
      return NextResponse.json({ error: `missing_field:${field}` }, { status: 400 });
    }
  }

  // stdout → journald.  Use a consistent prefix so grep/journalctl -g works.
  process.stdout.write(
    JSON.stringify({
      msg: "fabric-audit",
      ts: new Date(body.ts as number).toISOString(),
      action: body.action,
      nodeId: body.nodeId,
      nodeKind: body.nodeKind ?? null,
      detail: body.detail ?? null,
    }) + "\n",
  );

  return NextResponse.json({ ok: true });
}

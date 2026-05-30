import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(): Promise<NextResponse> {
  cookies().delete("fab_token");
  return NextResponse.json({ ok: true });
}

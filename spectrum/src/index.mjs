import http from "node:http";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { Spectrum } from "spectrum-ts";
import { effect, imessage } from "spectrum-ts/providers/imessage";

const loudEffect = "com.apple.MobileSMS.expressivesend.loud";

const envPath = resolve(dirname(fileURLToPath(import.meta.url)), "../../.env");
try {
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const separator = trimmed.indexOf("=");
    const key = trimmed.slice(0, separator).trim();
    let value = trimmed.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (key && process.env[key] === undefined) process.env[key] = value;
  }
} catch {
  // A missing .env is fine when the variables are already exported.
}

const projectId = process.env.SPECTRUM_PROJECT_ID;
const projectSecret = process.env.SPECTRUM_PROJECT_SECRET;
const bridgeToken = process.env.SPECTRUM_BRIDGE_TOKEN;
const kinwiseUrl = (process.env.KINWISE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const port = Number(process.env.SPECTRUM_BRIDGE_PORT || 8787);

if (!projectId || !projectSecret || !bridgeToken) {
  console.error("Set SPECTRUM_PROJECT_ID, SPECTRUM_PROJECT_SECRET, and SPECTRUM_BRIDGE_TOKEN.");
  process.exit(1);
}

const app = await Spectrum({
  projectId,
  projectSecret,
  providers: [imessage.config()],
});
const im = imessage(app);
const sentKeys = new Set();

async function openSpace({ spaceId, phone }) {
  if (spaceId) {
    try {
      return await im.space.get(spaceId);
    } catch (error) {
      console.error("Spectrum could not open that conversation", error instanceof Error ? error.message : error);
    }
  }
  if (!phone) return null;
  return im.space.create(await im.user(phone));
}

async function deliver({ spaceId, phone, text, idempotencyKey, notify = false }) {
  if (idempotencyKey && sentKeys.has(idempotencyKey)) {
    return { status: "duplicate" };
  }
  const space = await openSpace({ spaceId, phone });
  if (!space) return { status: "skipped_missing_space" };
  if (notify) {
    try {
      await space.send(effect(text, loudEffect));
    } catch (error) {
      console.error("Loud iMessage failed, sending a normal text", error instanceof Error ? error.message : error);
      await space.send(text);
    }
  } else {
    await space.send(text);
  }
  if (idempotencyKey) sentKeys.add(idempotencyKey);
  return { status: "sent", spaceId: space.id };
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"));
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

http
  .createServer(async (req, res) => {
    if (req.method !== "POST" || req.url !== "/send") {
      res.writeHead(404);
      res.end();
      return;
    }
    if (req.headers.authorization !== `Bearer ${bridgeToken}`) {
      res.writeHead(401);
      res.end();
      return;
    }
    try {
      const body = await readJson(req);
      const result = await deliver(body);
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(result));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "send failed";
      res.writeHead(502, { "content-type": "application/json" });
      res.end(JSON.stringify({ status: "provider_error", detail }));
    }
  })
  .listen(port, "127.0.0.1");

console.log(`Spectrum bridge listening on http://127.0.0.1:${port}`);

for await (const [space, message] of app.messages) {
  if (message.direction === "outbound" || message.content?.type !== "text") continue;
  const senderId = message.sender?.id ?? "";
  if (!senderId) continue;
  try {
    const response = await fetch(`${kinwiseUrl}/api/v1/webhooks/spectrum`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${bridgeToken}`,
      },
      body: JSON.stringify({
        messageId: message.id,
        text: message.content.text,
        senderId,
        spaceId: space.id,
      }),
    });
    if (!response.ok) {
      console.error("Kinwise rejected an iMessage", response.status);
    }
  } catch (error) {
    console.error("Kinwise inbound failed", error instanceof Error ? error.message : error);
  }
}

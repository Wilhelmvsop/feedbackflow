import { timingSafeEqual } from "node:crypto";
import Fastify, { type FastifyInstance, type FastifyServerOptions } from "fastify";
import type { Config } from "./config.js";
import { Dispatcher, type Fetch, type Sleep } from "./dispatcher.js";
import { eventSchema, type FeedbackFlowEvent } from "./events.js";

export interface AppOptions {
  config: Config;
  fetch?: Fetch;
  sleep?: Sleep;
  logger?: FastifyServerOptions["logger"];
}

declare module "fastify" {
  interface FastifyInstance {
    dispatcher: Dispatcher;
  }
}

function tokenMatches(header: string | undefined, expected: string): boolean {
  if (!header?.startsWith("Bearer ")) return false;
  const given = Buffer.from(header.slice("Bearer ".length).trim());
  const wanted = Buffer.from(expected);
  return given.length === wanted.length && timingSafeEqual(given, wanted);
}

export function buildApp({ config, fetch, sleep, logger = false }: AppOptions): FastifyInstance {
  const app = Fastify({ logger, bodyLimit: 64 * 1024 });
  const dispatcher = new Dispatcher(config, app.log, fetch, sleep);
  app.decorate("dispatcher", dispatcher);
  let shuttingDown = false;

  app.addHook("onClose", async () => {
    shuttingDown = true;
    await dispatcher.idle();
  });

  /** Liveness: the process is up and serving. */
  app.get("/healthz", async () => ({ ok: true }));

  /** Readiness: stop receiving traffic while draining on shutdown. */
  app.get("/readyz", async (_request, reply) => {
    if (shuttingDown) return reply.code(503).send({ ok: false, reason: "shutting down" });
    return { ok: true, webhooks: config.webhookUrls.length, ...dispatcher.stats };
  });

  app.post<{ Body: FeedbackFlowEvent }>(
    "/events",
    {
      schema: { body: eventSchema },
      onRequest: async (request, reply) => {
        if (config.ingestToken && !tokenMatches(request.headers.authorization, config.ingestToken)) {
          return reply.code(401).header("WWW-Authenticate", "Bearer").send({ detail: "Invalid token" });
        }
      },
    },
    async (request, reply) => {
      const accepted = dispatcher.enqueue(request.body);
      return reply.code(202).send({ accepted, duplicate: !accepted, targets: config.webhookUrls.length });
    },
  );

  return app;
}
